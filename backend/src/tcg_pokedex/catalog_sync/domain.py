"""Catalog-sync domain: the catalog entities, the run record and the sync rules.

Pure: no I/O and no clock. The run record and its result are Pydantic models so their
shape is defined once and validated both when written and when read.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

SOURCE = "tcgdex"
"""Where every catalog row comes from. Stored on each row by the repository."""

POCKET_SERIES_ID = "tcgp"
MAX_FAILURES = 100


class Variant(StrEnum):
    """A printing a card exists in. Declaration order is the canonical storage order."""

    NORMAL = "normal"
    REVERSE = "reverse"
    HOLO = "holo"
    FIRST_EDITION = "first_edition"
    W_PROMO = "w_promo"


def is_pocket_series(series_id: str) -> bool:
    """TCG Pocket sets are never synced. This is the only definition of the rule."""
    return series_id == POCKET_SERIES_ID


@dataclass(frozen=True)
class Series:
    id: str
    name: str


@dataclass(frozen=True)
class CardSet:
    id: str
    series_id: str
    name: str
    release_date: date
    official_count: int
    total_count: int
    logo_url: str | None
    symbol_url: str | None


@dataclass(frozen=True)
class Card:
    id: str
    set_id: str
    collector_number: str
    name: str
    rarity: str | None
    illustrator: str | None
    image_url: str | None
    variants: frozenset[Variant]

    def __post_init__(self) -> None:
        if not self.variants:
            raise ValueError("a card needs at least one variant")


@dataclass(frozen=True)
class SetListing:
    """One set as the provider returns it: the set, its series and its card ids."""

    card_set: CardSet
    series: Series
    card_ids: tuple[str, ...]


@dataclass(frozen=True)
class Fetched[T]:
    """A stored row with the time it was last fetched."""

    value: T
    fetched_at: datetime


@dataclass(frozen=True)
class StoredCatalog:
    """What the store already holds for one set, its series and its cards."""

    series: Fetched[Series] | None
    card_set: Fetched[CardSet] | None
    cards: Mapping[str, Fetched[Card]]


@dataclass(frozen=True)
class SetBatch:
    """One set's write. `series` is None when this run already wrote it."""

    series: Series | None
    card_set: CardSet
    cards: tuple[Card, ...]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Failure(_Model):
    kind: Literal["set", "card"]
    provider_id: str
    reason: str


class SyncKind(StrEnum):
    CATALOG = "catalog"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class KindCounts(_Model):
    """`fetched` counts valid payloads received and stored."""

    fetched: int = Field(ge=0)
    created: int = Field(ge=0)
    updated: int = Field(ge=0)
    unchanged: int = Field(ge=0)

    @model_validator(mode="after")
    def _fetched_is_the_sum(self) -> Self:
        if self.fetched != self.created + self.updated + self.unchanged:
            raise ValueError("fetched must equal created + updated + unchanged")
        return self


class SetCounts(KindCounts):
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)


class CardCounts(KindCounts):
    failed: int = Field(ge=0)


class SyncCounts(_Model):
    series: KindCounts
    sets: SetCounts
    cards: CardCounts


class SyncResult(_Model):
    counts: SyncCounts
    failures: tuple[Failure, ...] = Field(max_length=MAX_FAILURES)


class SyncRun(_Model):
    """One execution of a sync. Its JSON form is also the command's output."""

    id: UUID
    kind: SyncKind
    source: str = SOURCE
    status: RunStatus
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    result: SyncResult | None = None
    error: str | None = None

    @field_validator("started_at", "finished_at")
    @classmethod
    def _in_utc(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None
