from uuid import UUID

from pydantic import BaseModel

from tcg_pokedex.sync_runs.domain import SyncRun


class InMemorySyncRunRepository:
    """SyncRunRepository keeping each run's JSON form, as the real store does."""

    def __init__(self) -> None:
        self._runs: dict[UUID, str] = {}

    def start_run[R: BaseModel](self, run: SyncRun[R]) -> None:
        self._runs[run.id] = run.model_dump_json()

    def finish_run[R: BaseModel](self, run: SyncRun[R]) -> None:
        self._runs[run.id] = run.model_dump_json()

    def get_run[R: BaseModel](self, run_id: UUID, result: type[R]) -> SyncRun[R] | None:
        stored = self._runs.get(run_id)
        return None if stored is None else SyncRun[result].model_validate_json(stored)
