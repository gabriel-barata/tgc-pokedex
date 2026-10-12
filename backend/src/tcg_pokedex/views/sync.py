"""Sync runs as the API, the `tcg` command and the run table see them."""

from datetime import UTC, datetime
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
"""The provider name stored on every row and run fetched from TCGdex."""

MAX_FAILURES = 100
"""A run's result keeps at most this many failures; its counts stay exact."""


class SyncKind(StrEnum):
    CATALOG = "catalog"
    IMAGES = "images"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


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


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Failure(_Model):
    kind: Literal["set", "card"]
    provider_id: str
    reason: str


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


class ImageFailure(_Model):
    kind: Literal["card", "logo", "symbol"]
    provider_id: str
    reason: str


class ImageCounts(_Model):
    downloaded: int = Field(ge=0)
    cached: int = Field(ge=0)
    unavailable: int = Field(ge=0)
    failed: int = Field(ge=0)


class ImageSyncCounts(_Model):
    cards: ImageCounts
    artwork: ImageCounts


class ImageSyncResult(_Model):
    """`set_id` is set only on a run started by tracking that set."""

    set_id: str | None
    counts: ImageSyncCounts
    failures: tuple[ImageFailure, ...] = Field(max_length=MAX_FAILURES)


class SyncRun[R: BaseModel](BaseModel):
    """One execution of a sync. Its JSON form is also the command's output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    kind: SyncKind
    source: str = SOURCE
    status: RunStatus
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    result: R | None = None
    error: str | None = None

    @field_validator("started_at", "finished_at")
    @classmethod
    def _in_utc(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None
