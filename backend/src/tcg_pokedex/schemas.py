"""API request and response models, and the enums the routes take as path values."""

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CardSize(StrEnum):
    SMALL = "small"
    LARGE = "large"


class ArtworkKind(StrEnum):
    LOGO = "logo"
    SYMBOL = "symbol"


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
