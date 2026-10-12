"""Set routes: list every set, track and untrack one, read its image progress and
the owner's ownership of its cards."""

import threading
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import Engine, Exists, Row, and_, delete, exists, func, select
from sqlalchemy.dialects import postgresql

from tcg_pokedex.db import get_engine
from tcg_pokedex.schemas import (
    ArtworkKind,
    CardOwnership,
    SeriesEntry,
    SetCompletion,
    SetEntry,
    SetOwnership,
    SetTracking,
    Variant,
    VariantQuantity,
)
from tcg_pokedex.services.image_sync import sync_images
from tcg_pokedex.services.sync_runs import join_syncs, release_syncs
from tcg_pokedex.tables import (
    HOUSEHOLD_OWNER_ID,
    card_images,
    cards,
    ownership,
    series,
    set_artwork,
    sets,
    tracked_sets,
)
from tcg_pokedex.tcgdex import Tcgdex

UNKNOWN_SET: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": "The set is not in the catalog"}
}

router = APIRouter(prefix="/api/sets")


class DownloadRegistry:
    """The sets whose track-triggered download runs in this process. Thread-safe."""

    def __init__(self) -> None:
        self._running: set[str] = set()
        self._lock = threading.Lock()

    def start(self, set_id: str) -> bool:
        """Mark the set's download as running; False when it already was."""
        with self._lock:
            if set_id in self._running:
                return False
            self._running.add(set_id)
            return True

    def finish(self, set_id: str) -> None:
        with self._lock:
            self._running.discard(set_id)

    def is_running(self, set_id: str) -> bool:
        with self._lock:
            return set_id in self._running

    def running(self) -> frozenset[str]:
        with self._lock:
            return frozenset(self._running)


def get_owner_id() -> UUID:
    """The owner the API acts as. Profiles (PTCG-031) replace only this."""
    return HOUSEHOLD_OWNER_ID


Owner = Annotated[UUID, Depends(get_owner_id)]
DB = Annotated[Engine, Depends(get_engine)]


@router.get("")
def list_sets(owner_id: Owner, engine: DB, request: Request) -> list[SeriesEntry]:
    """Every set grouped by series, newest release first, with the owner's tracking."""
    statement = (
        select(
            sets.c.id,
            sets.c.name,
            sets.c.series_id,
            series.c.name.label("series_name"),
            sets.c.release_date,
            sets.c.official_count,
            sets.c.total_count,
            _has_artwork(ArtworkKind.LOGO).label("has_logo"),
            _has_artwork(ArtworkKind.SYMBOL).label("has_symbol"),
            exists()
            .where(
                tracked_sets.c.owner_id == owner_id,
                tracked_sets.c.set_id == sets.c.id,
            )
            .label("tracked"),
        )
        .join_from(sets, series)
        .order_by(sets.c.release_date.desc(), sets.c.id.desc())
    )
    owned = (
        select(
            cards.c.set_id,
            cards.c.id,
            cards.c.variants,
            ownership.c.variant,
            ownership.c.quantity,
        )
        .join_from(ownership, cards)
        .where(ownership.c.owner_id == owner_id, ownership.c.quantity > 0)
    )
    with engine.connect() as connection:
        rows = connection.execute(statement).all()
        owned_rows = connection.execute(owned).all()
    set_of = {row.id: row.set_id for row in owned_rows}
    by_set: dict[str, list[CardOwnership]] = {}
    for card in _card_ownerships(owned_rows):
        by_set.setdefault(set_of[card.card_id], []).append(card)
    registry: DownloadRegistry = request.app.state.registry
    downloading = registry.running()
    by_series: dict[tuple[str, str], list[SetEntry]] = {}
    for row in rows:
        total = card_count(row.official_count, row.total_count)
        by_series.setdefault((row.series_id, row.series_name), []).append(
            SetEntry(
                id=row.id,
                name=row.name,
                release_date=row.release_date,
                card_count=total,
                has_logo=row.has_logo,
                has_symbol=row.has_symbol,
                tracked=row.tracked,
                downloading=row.id in downloading,
                completion=_completion(total, by_set.get(row.id, [])),
            )
        )
    return [
        SeriesEntry(id=series_id, name=name, sets=entries)
        for (series_id, name), entries in by_series.items()
    ]


def card_count(official: int, total: int) -> int:
    """The printed set size; sets with none printed (promos) count every card.

    Variants never count apart: the catalog holds one card per number.
    """
    return official or total


def set_completion(total: int, owned: int, so_normal: int) -> SetCompletion:
    """A set is complete when every counted card is owned, "só normal" ones included.

    Placeholder until PTCG-039: `owned` is capped at `total` and `so_normal` at the
    capped `owned`, so owned cards beyond the printed count are not counted apart.
    """
    counted = min(owned, total)
    return SetCompletion(
        owned=counted,
        so_normal=min(so_normal, counted),
        total=total,
        complete=total > 0 and counted == total,
    )


def card_ownership(
    card_id: str, listed: Sequence[Variant], stored: Mapping[Variant, int]
) -> CardOwnership:
    """The card's quantity per listed variant, and whether it is owned.

    Owning any listed variant owns the card. The wanted version is missing when only
    Normal is owned and the card lists another variant. Unlisted variants are ignored.
    """
    variants = [
        VariantQuantity(variant=variant, quantity=stored.get(variant, 0))
        for variant in listed
    ]
    held = {entry.variant for entry in variants if entry.quantity > 0}
    return CardOwnership(
        card_id=card_id,
        variants=variants,
        owned=bool(held),
        wanted_version_missing=held == {Variant.NORMAL} and len(listed) > 1,
    )


@router.get("/{set_id}/ownership", responses=UNKNOWN_SET)
def get_ownership(set_id: str, owner_id: Owner, engine: DB) -> SetOwnership:
    """Every card of the set with the owner's quantity per variant and its flags."""
    counts = select(sets.c.official_count, sets.c.total_count).where(
        sets.c.id == set_id
    )
    statement = (
        select(cards.c.id, cards.c.variants, ownership.c.variant, ownership.c.quantity)
        .select_from(
            cards.outerjoin(
                ownership,
                and_(
                    ownership.c.card_id == cards.c.id,
                    ownership.c.owner_id == owner_id,
                ),
            )
        )
        .where(cards.c.set_id == set_id)
        .order_by(cards.c.id)
    )
    with engine.connect() as connection:
        printed = connection.execute(counts).first()
        if printed is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown set")
        rows = connection.execute(statement).all()
    card_ownerships = _card_ownerships(rows)
    return SetOwnership(
        set_id=set_id,
        completion=_completion(
            card_count(printed.official_count, printed.total_count), card_ownerships
        ),
        cards=card_ownerships,
    )


@router.get("/{set_id}/tracking", responses=UNKNOWN_SET)
def get_tracking(
    set_id: str, owner_id: Owner, engine: DB, request: Request
) -> SetTracking:
    return _tracking(engine, request, owner_id, set_id)


@router.put("/{set_id}/tracking", responses=UNKNOWN_SET)
def track_set(
    set_id: str,
    owner_id: Owner,
    engine: DB,
    request: Request,
    background: BackgroundTasks,
) -> SetTracking:
    """Track the set and, when it was untracked, download its images afterwards."""
    _require_set(engine, set_id)
    statement = (
        postgresql.insert(tracked_sets)
        .values(owner_id=owner_id, set_id=set_id, tracked_at=datetime.now(UTC))
        .on_conflict_do_nothing()
        .returning(tracked_sets.c.set_id)
    )
    with engine.begin() as connection:
        newly_tracked = connection.execute(statement).first() is not None
    registry: DownloadRegistry = request.app.state.registry
    if newly_tracked and registry.start(set_id):
        background.add_task(_download_set, request, set_id)
    return _tracking(engine, request, owner_id, set_id)


@router.delete("/{set_id}/tracking", responses=UNKNOWN_SET)
def untrack_set(
    set_id: str, owner_id: Owner, engine: DB, request: Request
) -> SetTracking:
    """Untrack the set. Its cached images stay, and a running download goes on."""
    _require_set(engine, set_id)
    with engine.begin() as connection:
        connection.execute(
            delete(tracked_sets).where(
                tracked_sets.c.owner_id == owner_id, tracked_sets.c.set_id == set_id
            )
        )
    return _tracking(engine, request, owner_id, set_id)


def _has_artwork(kind: ArtworkKind) -> Exists:
    return exists().where(
        set_artwork.c.set_id == sets.c.id, set_artwork.c.kind == kind.value
    )


def _card_ownerships(rows: Iterable[Row[*tuple[Any, ...]]]) -> list[CardOwnership]:
    """Group `id, variants, variant, quantity` rows per card, in first-seen order."""
    listed: dict[str, list[Variant]] = {}
    stored: dict[str, dict[Variant, int]] = {}
    for row in rows:
        listed.setdefault(row.id, [Variant(name) for name in row.variants])
        quantities = stored.setdefault(row.id, {})
        if row.variant is not None:
            quantities[Variant(row.variant)] = row.quantity
    return [
        card_ownership(card_id, variants, stored[card_id])
        for card_id, variants in listed.items()
    ]


def _completion(total: int, card_ownerships: Iterable[CardOwnership]) -> SetCompletion:
    owned = [card for card in card_ownerships if card.owned]
    so_normal = sum(card.wanted_version_missing for card in owned)
    return set_completion(total, len(owned), so_normal)


def _require_set(engine: Engine, set_id: str) -> None:
    with engine.connect() as connection:
        if not connection.scalar(select(exists().where(sets.c.id == set_id))):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown set")


def _tracking(
    engine: Engine, request: Request, owner_id: UUID, set_id: str
) -> SetTracking:
    _require_set(engine, set_id)
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
    with engine.connect() as connection:
        total, cached, unavailable = connection.execute(counts).one()
        is_tracked = bool(connection.scalar(tracked))
    registry: DownloadRegistry = request.app.state.registry
    return SetTracking(
        set_id=set_id,
        tracked=is_tracked,
        total_cards=total,
        cached=cached,
        unavailable=unavailable,
        downloading=registry.is_running(set_id),
    )


def _download_set(request: Request, set_id: str) -> None:
    """Download the set's images once no full sync runs; set downloads run together."""
    state = request.app.state
    try:
        lock = join_syncs(state.engine)
        try:
            with Tcgdex(transport=state.tcgdex_transport) as tcgdex:
                sync_images(
                    state.engine, tcgdex, state.settings.image_dir, set_id=set_id
                )
        finally:
            release_syncs(lock)
    finally:
        state.registry.finish(set_id)
