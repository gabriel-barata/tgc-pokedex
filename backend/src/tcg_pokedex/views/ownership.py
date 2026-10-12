from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

MAX_QUANTITY = 999
"""The most copies of one card variant an owner can record."""


class Variant(StrEnum):
    """A printing a card exists in. Declaration order is the canonical storage order."""

    NORMAL = "normal"
    REVERSE = "reverse"
    HOLO = "holo"
    FIRST_EDITION = "first_edition"
    W_PROMO = "w_promo"


class SetCompletion(BaseModel):
    """How many of a set's cards the owner has, and how many only in Normal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    owned: int = Field(ge=0)
    so_normal: int = Field(ge=0)
    total: int = Field(ge=0)
    complete: bool


class VariantQuantity(BaseModel):
    """How many copies of one variant of a card the owner has."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    variant: Variant
    quantity: int = Field(ge=0, le=MAX_QUANTITY)


class CardOwnership(BaseModel):
    """A card's quantity per listed variant, in canonical order, and its flags."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    card_id: str
    variants: list[VariantQuantity]
    owned: bool
    wanted_version_missing: bool


class SetOwnership(BaseModel):
    """Every card of a set, by card id, with the owner's quantities and flags."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    set_id: str
    completion: SetCompletion
    cards: list[CardOwnership]


class QuantityUpdate(BaseModel):
    """The number of copies to record for one variant of a card."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    quantity: int = Field(ge=0, le=MAX_QUANTITY)
