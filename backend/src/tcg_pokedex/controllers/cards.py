"""Card routes: add, remove or set the owner's copies of one variant of a card."""

from typing import Any

from fastapi import APIRouter, HTTPException, status

from tcg_pokedex.controllers.dependencies import Database, Owner
from tcg_pokedex.models import ownership
from tcg_pokedex.models.ownership import (
    AtMaximumError,
    UnknownCardError,
    UnlistedVariantError,
)
from tcg_pokedex.views.ownership import (
    MAX_QUANTITY,
    CardOwnership,
    QuantityUpdate,
    Variant,
)

UNKNOWN_CARD: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": "The card is not in the catalog"}
}
AT_MAXIMUM: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "description": f"The variant already has {MAX_QUANTITY} copies"
    }
}

router = APIRouter(prefix="/api/cards")


@router.post(
    "/{card_id}/ownership/{variant}/increment",
    responses={**UNKNOWN_CARD, **AT_MAXIMUM},
)
def increment(
    card_id: str, variant: Variant, owner_id: Owner, engine: Database
) -> CardOwnership:
    """Add one copy of the card's variant."""
    try:
        return ownership.increment_quantity(engine, owner_id, card_id, variant)
    except AtMaximumError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Already at the maximum"
        ) from error
    except (UnknownCardError, UnlistedVariantError) as error:
        raise _rejected(error) from error


@router.post("/{card_id}/ownership/{variant}/decrement", responses=UNKNOWN_CARD)
def decrement(
    card_id: str, variant: Variant, owner_id: Owner, engine: Database
) -> CardOwnership:
    """Remove one copy of the card's variant. A variant with none stays at 0."""
    try:
        return ownership.decrement_quantity(engine, owner_id, card_id, variant)
    except (UnknownCardError, UnlistedVariantError) as error:
        raise _rejected(error) from error


@router.put("/{card_id}/ownership/{variant}", responses=UNKNOWN_CARD)
def set_quantity(
    card_id: str,
    variant: Variant,
    body: QuantityUpdate,
    owner_id: Owner,
    engine: Database,
) -> CardOwnership:
    """Record exactly this many copies of the card's variant."""
    try:
        return ownership.set_quantity(engine, owner_id, card_id, variant, body.quantity)
    except (UnknownCardError, UnlistedVariantError) as error:
        raise _rejected(error) from error


def _rejected(error: UnknownCardError | UnlistedVariantError) -> HTTPException:
    if isinstance(error, UnknownCardError):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Unknown card")
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "The card has no such variant"
    )
