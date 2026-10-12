from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Engine, delete, exists, func, select
from sqlalchemy.dialects import postgresql

from tcg_pokedex.catalog_sync.adapters.tables import cards, sets
from tcg_pokedex.image_cache.adapters.tables import (
    card_images,
    set_artwork,
    tracked_sets,
)
from tcg_pokedex.image_cache.domain import (
    ArtworkKind,
    ArtworkToFetch,
    CardToResolve,
    Language,
    SetTracking,
    StoredCardImage,
)
from tcg_pokedex.tcgdex import SOURCE

CATALOG_ORDER = (sets.c.release_date, sets.c.id)


class PostgresImageCacheRepository:
    """ImageCacheRepository on Postgres. Each write is one committed transaction."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def set_exists(self, set_id: str) -> bool:
        with self._engine.connect() as connection:
            return bool(connection.scalar(select(exists().where(sets.c.id == set_id))))

    def track(self, owner_id: UUID, set_id: str, at: datetime) -> bool:
        statement = (
            postgresql.insert(tracked_sets)
            .values(owner_id=owner_id, set_id=set_id, tracked_at=at)
            .on_conflict_do_nothing()
            .returning(tracked_sets.c.set_id)
        )
        with self._engine.begin() as connection:
            return connection.execute(statement).first() is not None

    def untrack(self, owner_id: UUID, set_id: str) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                delete(tracked_sets).where(
                    tracked_sets.c.owner_id == owner_id,
                    tracked_sets.c.set_id == set_id,
                )
            )

    def progress(self, owner_id: UUID, set_id: str) -> SetTracking:
        counts = (
            select(
                func.count(cards.c.id),
                func.count(card_images.c.language),
                func.count(card_images.c.card_id) - func.count(card_images.c.language),
            )
            .select_from(cards.outerjoin(card_images))
            .where(cards.c.set_id == set_id)
        )
        tracked = select(
            exists().where(
                tracked_sets.c.owner_id == owner_id, tracked_sets.c.set_id == set_id
            )
        )
        with self._engine.connect() as connection:
            total, cached, unavailable = connection.execute(counts).one()
            is_tracked = bool(connection.scalar(tracked))
        return SetTracking(
            set_id=set_id,
            tracked=is_tracked,
            total_cards=total,
            cached=cached,
            unavailable=unavailable,
            downloading=False,
        )

    def tracked_set_ids(self) -> list[str]:
        statement = (
            select(sets.c.id)
            .where(exists().where(tracked_sets.c.set_id == sets.c.id))
            .order_by(*CATALOG_ORDER)
        )
        with self._engine.connect() as connection:
            return list(connection.scalars(statement))

    def cards_to_resolve(self, set_id: str) -> list[CardToResolve]:
        statement = (
            select(
                cards.c.id,
                cards.c.image_url,
                card_images.c.language,
                card_images.c.fetched_at,
            )
            .select_from(cards.outerjoin(card_images))
            .where(cards.c.set_id == set_id)
            .order_by(cards.c.id)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).all()
        return [
            CardToResolve(
                card_id=card_id,
                pt_image_url=image_url,
                stored=None
                if fetched_at is None
                else StoredCardImage(
                    language=None if language is None else Language(language),
                    fetched_at=fetched_at,
                ),
            )
            for card_id, image_url, language, fetched_at in rows
        ]

    def save_card_images(
        self, rows: Sequence[tuple[str, Language | None]], fetched_at: datetime
    ) -> None:
        if not rows:
            return
        statement = postgresql.insert(card_images)
        with self._engine.begin() as connection:
            connection.execute(
                statement.on_conflict_do_update(
                    index_elements=[card_images.c.card_id],
                    set_={
                        "language": statement.excluded.language,
                        "source": statement.excluded.source,
                        "fetched_at": statement.excluded.fetched_at,
                    },
                ),
                [
                    {
                        "card_id": card_id,
                        "language": None if language is None else language.value,
                        "source": SOURCE,
                        "fetched_at": fetched_at,
                    }
                    for card_id, language in rows
                ],
            )

    def artwork_to_fetch(self) -> list[ArtworkToFetch]:
        with self._engine.connect() as connection:
            catalog = connection.execute(
                select(sets.c.id, sets.c.logo_url, sets.c.symbol_url).order_by(
                    *CATALOG_ORDER
                )
            ).all()
            cached = {
                (set_id, kind)
                for set_id, kind in connection.execute(
                    select(set_artwork.c.set_id, set_artwork.c.kind)
                )
            }
        return [
            ArtworkToFetch(
                set_id=set_id,
                kind=kind,
                url=logo_url if kind is ArtworkKind.LOGO else symbol_url,
                cached=(set_id, kind.value) in cached,
            )
            for set_id, logo_url, symbol_url in catalog
            for kind in ArtworkKind
        ]

    def save_artwork(
        self, set_id: str, kind: ArtworkKind, fetched_at: datetime
    ) -> None:
        statement = postgresql.insert(set_artwork).values(
            set_id=set_id, kind=kind.value, source=SOURCE, fetched_at=fetched_at
        )
        with self._engine.begin() as connection:
            connection.execute(
                statement.on_conflict_do_update(
                    index_elements=[set_artwork.c.set_id, set_artwork.c.kind],
                    set_={"source": SOURCE, "fetched_at": fetched_at},
                )
            )
