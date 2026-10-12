"""API request and response models, and the enums the routes take as path values."""

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
