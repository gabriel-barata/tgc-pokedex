from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Engine, ForeignKey, Text, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from tcg_pokedex.models.base import Base
from tcg_pokedex.models.catalog import CATALOG_ORDER, Card, Set
from tcg_pokedex.views.images import ArtworkKind
from tcg_pokedex.views.sync import SOURCE


class CardImage(Base):
    __tablename__ = "card_images"
    __table_args__ = (
        CheckConstraint("language IN ('pt', 'en')", name="language_known"),
    )

    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    language: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime]


class SetArtwork(Base):
    __tablename__ = "set_artwork"
    __table_args__ = (CheckConstraint("kind IN ('logo', 'symbol')", name="kind_known"),)

    set_id: Mapped[str] = mapped_column(ForeignKey("sets.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime]


def cards_with_image_language(
    engine: Engine, set_id: str
) -> list[tuple[str, str | None, str | None]]:
    """The set's cards, by id, as `(card id, pt image url, stored image language)`."""
    statement = (
        select(Card.id, Card.image_url, CardImage.language)
        .select_from(Card)
        .outerjoin(CardImage)
        .where(Card.set_id == set_id)
        .order_by(Card.id)
    )
    with engine.connect() as connection:
        return [(row[0], row[1], row[2]) for row in connection.execute(statement)]


def save_card_images(engine: Engine, rows: list[dict[str, Any]]) -> None:
    """Upsert `card_id, language, fetched_at` rows, stamped with the provider."""
    statement = postgresql.insert(CardImage)
    with engine.begin() as connection:
        connection.execute(
            statement.on_conflict_do_update(
                index_elements=[CardImage.card_id],
                set_={
                    "language": statement.excluded.language,
                    "source": statement.excluded.source,
                    "fetched_at": statement.excluded.fetched_at,
                },
            ),
            [{**row, "source": SOURCE} for row in rows],
        )


def artwork_sources(engine: Engine) -> list[tuple[str, str | None, str | None]]:
    """Every set as `(id, logo url, symbol url)`, in catalog order."""
    statement = select(Set.id, Set.logo_url, Set.symbol_url).order_by(*CATALOG_ORDER)
    with engine.connect() as connection:
        return [(row[0], row[1], row[2]) for row in connection.execute(statement)]


def cached_artwork(engine: Engine) -> set[tuple[str, str]]:
    """The `(set id, kind)` pairs whose artwork is stored."""
    with engine.connect() as connection:
        return {
            (row[0], row[1])
            for row in connection.execute(select(SetArtwork.set_id, SetArtwork.kind))
        }


def save_artwork(
    engine: Engine, set_id: str, kind: ArtworkKind, fetched_at: datetime
) -> None:
    statement = postgresql.insert(SetArtwork).values(
        set_id=set_id, kind=kind.value, source=SOURCE, fetched_at=fetched_at
    )
    with engine.begin() as connection:
        connection.execute(
            statement.on_conflict_do_update(
                index_elements=[SetArtwork.set_id, SetArtwork.kind],
                set_={"source": SOURCE, "fetched_at": fetched_at},
            )
        )
