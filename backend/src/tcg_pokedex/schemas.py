"""API request and response models, and the enums the routes take as path values."""

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tcg_pokedex.tables import MAX_QUANTITY


class CardSize(StrEnum):
    SMALL = "small"
    LARGE = "large"


class ArtworkKind(StrEnum):
    LOGO = "logo"
    SYMBOL = "symbol"


class Variant(StrEnum):
    """A printing a card exists in. Declaration order is the canonical storage order."""

    NORMAL = "normal"
    REVERSE = "reverse"
    HOLO = "holo"
    FIRST_EDITION = "first_edition"
    W_PROMO = "w_promo"


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]


class SetTracking(BaseModel):
    """A set's tracking state for one owner, and its image progress."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    set_id: str
    tracked: bool
    total_cards: int = Field(ge=0)
    cached: int = Field(ge=0)
    unavailable: int = Field(ge=0)
    downloading: bool


class SetEntry(BaseModel):
    """A set as one owner sees it. `has_logo` and `has_symbol` mean cached."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    release_date: date
    card_count: int = Field(ge=0)
    has_logo: bool
    has_symbol: bool
    tracked: bool
    downloading: bool


class SeriesEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    sets: list[SetEntry]


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


class QuantityUpdate(BaseModel):
    """The number of copies to record for one variant of a card."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    quantity: int = Field(ge=0, le=MAX_QUANTITY)
