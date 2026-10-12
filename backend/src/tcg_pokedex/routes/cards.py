"""Card routes: add, remove or set the owner's copies of one variant of a card."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Engine, Executable, select, update
from sqlalchemy.dialects import postgresql

from tcg_pokedex.routes.sets import DB, Owner, card_ownership
from tcg_pokedex.schemas import CardOwnership, QuantityUpdate, Variant
from tcg_pokedex.tables import MAX_QUANTITY, cards, ownership

UNKNOWN_CARD: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": "The card is not in the catalog"}
}
AT_MAXIMUM: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "description": f"The variant already has {MAX_QUANTITY} copies"
    }
}
KEY = [ownership.c.owner_id, ownership.c.card_id, ownership.c.variant]

router = APIRouter(prefix="/api/cards")


@router.post(
    "/{card_id}/ownership/{variant}/increment",
    responses={**UNKNOWN_CARD, **AT_MAXIMUM},
)
def increment(
    card_id: str, variant: Variant, owner_id: Owner, engine: DB
) -> CardOwnership:
    """Add one copy of the card's variant."""
    statement = (
        postgresql.insert(ownership)
        .values(owner_id=owner_id, card_id=card_id, variant=variant.value, quantity=1)
        .on_conflict_do_update(
            index_elements=KEY,
            set_={"quantity": ownership.c.quantity + 1},
            where=ownership.c.quantity < MAX_QUANTITY,
        )
        .returning(ownership.c.quantity)
    )
    written, result = _write(engine, owner_id, card_id, variant, statement)
    if not written:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already at the maximum")
    return result


@router.post("/{card_id}/ownership/{variant}/decrement", responses=UNKNOWN_CARD)
def decrement(
    card_id: str, variant: Variant, owner_id: Owner, engine: DB
) -> CardOwnership:
    """Remove one copy of the card's variant. A variant with none stays at 0."""
    statement = (
        update(ownership)
        .where(
            ownership.c.owner_id == owner_id,
            ownership.c.card_id == card_id,
            ownership.c.variant == variant.value,
            ownership.c.quantity > 0,
        )
        .values(quantity=ownership.c.quantity - 1)
        .returning(ownership.c.quantity)
    )
    return _write(engine, owner_id, card_id, variant, statement)[1]


@router.put("/{card_id}/ownership/{variant}", responses=UNKNOWN_CARD)
def set_quantity(
    card_id: str,
    variant: Variant,
    body: QuantityUpdate,
    owner_id: Owner,
    engine: DB,
) -> CardOwnership:
    """Record exactly this many copies of the card's variant."""
    statement = postgresql.insert(ownership).values(
        owner_id=owner_id,
        card_id=card_id,
        variant=variant.value,
        quantity=body.quantity,
    )
    statement = statement.on_conflict_do_update(
        index_elements=KEY, set_={"quantity": statement.excluded.quantity}
    ).returning(ownership.c.quantity)
    return _write(engine, owner_id, card_id, variant, statement)[1]


def _write(
    engine: Engine,
    owner_id: UUID,
    card_id: str,
    variant: Variant,
    statement: Executable,
) -> tuple[bool, CardOwnership]:
    """Run one write on a variant the card lists, in one transaction.

    Returns whether it changed a row, and the card's ownership afterwards.
    """
    with engine.begin() as connection:
        listed = connection.scalar(
            select(cards.c.variants).where(cards.c.id == card_id)
        )
        if listed is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown card")
        if variant.value not in listed:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "The card has no such variant"
            )
        written = connection.execute(statement).first() is not None
        rows = connection.execute(
            select(ownership.c.variant, ownership.c.quantity).where(
                ownership.c.owner_id == owner_id, ownership.c.card_id == card_id
            )
        ).all()
    stored = {Variant(row.variant): row.quantity for row in rows}
    return written, card_ownership(card_id, [Variant(name) for name in listed], stored)
