"""API request and response models, and the enums the routes take as path values."""

from datetime import date
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

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


class SyncKind(StrEnum):
    CATALOG = "catalog"
    IMAGES = "images"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


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


class SetCompletion(BaseModel):
    """How many of a set's cards the owner has, and how many only in Normal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    owned: int = Field(ge=0)
    so_normal: int = Field(ge=0)
    total: int = Field(ge=0)
    complete: bool


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
    completion: SetCompletion


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


class RunCounts(BaseModel):
    """Items a run fetched from the provider, changed in our store, and failed on."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fetched: int = Field(ge=0)
    updated: int = Field(ge=0)
    failed: int = Field(ge=0)


class RunFailure(BaseModel):
    """One item a run failed on: its kind, its provider id and why."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str
    provider_id: str
    reason: str


class SyncRunEntry(BaseModel):
    """A sync run. `counts` is None until it ends; `failures` keeps the first 100."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    kind: SyncKind
    status: RunStatus
    started_at: AwareDatetime
    finished_at: AwareDatetime | None
    duration_ms: int | None = Field(ge=0)
    counts: RunCounts | None
    failures: list[RunFailure]
    error: str | None


class SyncStatus(BaseModel):
    """Whether a sync or set download runs now, and the latest runs, newest first."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    running: bool
    runs: list[SyncRunEntry]
