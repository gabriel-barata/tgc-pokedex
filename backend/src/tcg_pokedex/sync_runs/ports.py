from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from tcg_pokedex.sync_runs.domain import SyncRun


class SyncRunRepository(Protocol):
    """Our own store of sync run records, one per run of any sync."""

    def start_run[R: BaseModel](self, run: SyncRun[R]) -> None:
        """Insert an open run record and commit it."""
        ...

    def finish_run[R: BaseModel](self, run: SyncRun[R]) -> None:
        """Update a run record to its closed state."""
        ...

    def get_run[R: BaseModel](self, run_id: UUID, result: type[R]) -> SyncRun[R] | None:
        """The stored run, its result validated as `result`, or None."""
        ...
