"""Sync run records, shared by every sync: kinds, statuses and the status rule.

Pure: no I/O and no clock. A run is a Pydantic model generic over its result, so the
stored shape is defined once and validated both when written and when read.
"""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from tcg_pokedex.tcgdex import SOURCE

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


def run_status(*, aborted: bool, failed: int) -> RunStatus:
    """An aborted run failed; otherwise any failed item makes it partial."""
    if aborted:
        return RunStatus.FAILED
    return RunStatus.PARTIAL if failed else RunStatus.SUCCEEDED


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
