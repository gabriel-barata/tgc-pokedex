from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Engine,
    Exists,
    ForeignKey,
    Row,
    Uuid,
    and_,
    exists,
    select,
    update,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from tcg_pokedex.models.base import Base
from tcg_pokedex.models.catalog import Card, Series, Set, card_count
from tcg_pokedex.models.images import SetArtwork
from tcg_pokedex.models.tracking import TrackedSet
from tcg_pokedex.views.images import ArtworkKind
from tcg_pokedex.views.ownership import (
    MAX_QUANTITY,
    CardOwnership,
    SetCompletion,
    SetOwnership,
    Variant,
    VariantQuantity,
)
from tcg_pokedex.views.sets import SeriesEntry, SetEntry


class UnknownCardError(Exception):
    """The card is not in the catalog."""


class UnlistedVariantError(Exception):
    """The card does not list the variant."""


class AtMaximumError(Exception):
    """The variant already has `MAX_QUANTITY` copies."""


class Ownership(Base):
    __tablename__ = "ownership"
    __table_args__ = (
        CheckConstraint(
            f"quantity BETWEEN 0 AND {MAX_QUANTITY}", name="quantity_in_range"
        ),
    )

    owner_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("owners.id"), primary_key=True
    )
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    variant: Mapped[str] = mapped_column(primary_key=True)
    quantity: Mapped[int]


KEY = [Ownership.owner_id, Ownership.card_id, Ownership.variant]


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


def list_series(
    engine: Engine, owner_id: UUID, downloading: frozenset[str]
) -> list[SeriesEntry]:
    """Every set grouped by series, newest release first, with the owner's tracking."""
    statement = (
        select(
            Set.id,
            Set.name,
            Set.series_id,
            Series.name.label("series_name"),
            Set.release_date,
            Set.official_count,
            Set.total_count,
            _has_artwork(ArtworkKind.LOGO).label("has_logo"),
            _has_artwork(ArtworkKind.SYMBOL).label("has_symbol"),
            exists()
            .where(TrackedSet.owner_id == owner_id, TrackedSet.set_id == Set.id)
            .label("tracked"),
        )
        .join_from(Set, Series)
        .order_by(Set.release_date.desc(), Set.id.desc())
    )
    owned = (
        select(
            Card.set_id, Card.id, Card.variants, Ownership.variant, Ownership.quantity
        )
        .join_from(Ownership, Card)
        .where(Ownership.owner_id == owner_id, Ownership.quantity > 0)
    )
    with engine.connect() as connection:
        rows = connection.execute(statement).all()
        owned_rows = connection.execute(owned).all()
    set_of = {row.id: row.set_id for row in owned_rows}
    by_set: dict[str, list[CardOwnership]] = {}
    for card in _card_ownerships(owned_rows):
        by_set.setdefault(set_of[card.card_id], []).append(card)
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


def set_ownership(engine: Engine, owner_id: UUID, set_id: str) -> SetOwnership | None:
    """Every card of the set with the owner's quantity per variant and its flags.

    None when the set is not in the catalog.
    """
    counts = select(Set.official_count, Set.total_count).where(Set.id == set_id)
    statement = (
        select(Card.id, Card.variants, Ownership.variant, Ownership.quantity)
        .select_from(Card)
        .outerjoin(
            Ownership,
            and_(Ownership.card_id == Card.id, Ownership.owner_id == owner_id),
        )
        .where(Card.set_id == set_id)
        .order_by(Card.id)
    )
    with engine.connect() as connection:
        printed = connection.execute(counts).first()
        if printed is None:
            return None
        rows = connection.execute(statement).all()
    card_ownerships = _card_ownerships(rows)
    return SetOwnership(
        set_id=set_id,
        completion=_completion(
            card_count(printed.official_count, printed.total_count), card_ownerships
        ),
        cards=card_ownerships,
    )


def increment_quantity(
    engine: Engine, owner_id: UUID, card_id: str, variant: Variant
) -> CardOwnership:
    """Add one copy of the card's variant; raises `AtMaximumError` at the maximum."""
    statement = (
        postgresql.insert(Ownership)
        .values(owner_id=owner_id, card_id=card_id, variant=variant.value, quantity=1)
        .on_conflict_do_update(
            index_elements=KEY,
            set_={"quantity": Ownership.quantity + 1},
            where=Ownership.quantity < MAX_QUANTITY,
        )
        .returning(Ownership.quantity)
    )
    written, result = _write(engine, owner_id, card_id, variant, statement)
    if not written:
        raise AtMaximumError
    return result


def decrement_quantity(
    engine: Engine, owner_id: UUID, card_id: str, variant: Variant
) -> CardOwnership:
    """Remove one copy of the card's variant. A variant with none stays at 0."""
    statement = (
        update(Ownership)
        .where(
            Ownership.owner_id == owner_id,
            Ownership.card_id == card_id,
            Ownership.variant == variant.value,
            Ownership.quantity > 0,
        )
        .values(quantity=Ownership.quantity - 1)
        .returning(Ownership.quantity)
    )
    return _write(engine, owner_id, card_id, variant, statement)[1]


def set_quantity(
    engine: Engine, owner_id: UUID, card_id: str, variant: Variant, quantity: int
) -> CardOwnership:
    """Record exactly `quantity` copies of the card's variant."""
    statement = postgresql.insert(Ownership).values(
        owner_id=owner_id, card_id=card_id, variant=variant.value, quantity=quantity
    )
    statement = statement.on_conflict_do_update(
        index_elements=KEY, set_={"quantity": statement.excluded.quantity}
    ).returning(Ownership.quantity)
    return _write(engine, owner_id, card_id, variant, statement)[1]


def _write(
    engine: Engine,
    owner_id: UUID,
    card_id: str,
    variant: Variant,
    statement: Any,
) -> tuple[bool, CardOwnership]:
    """Run one write on a variant the card lists, in one transaction.

    Returns whether it changed a row, and the card's ownership afterwards.
    """
    with engine.begin() as connection:
        listed = connection.scalar(select(Card.variants).where(Card.id == card_id))
        if listed is None:
            raise UnknownCardError
        if variant.value not in listed:
            raise UnlistedVariantError
        written = connection.execute(statement).first() is not None
        rows = connection.execute(
            select(Ownership.variant, Ownership.quantity).where(
                Ownership.owner_id == owner_id, Ownership.card_id == card_id
            )
        ).all()
    stored = {Variant(row.variant): row.quantity for row in rows}
    return written, card_ownership(card_id, [Variant(name) for name in listed], stored)


def _has_artwork(kind: ArtworkKind) -> Exists:
    return exists().where(SetArtwork.set_id == Set.id, SetArtwork.kind == kind.value)


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
