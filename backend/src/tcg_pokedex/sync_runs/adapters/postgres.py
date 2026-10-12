from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Engine, insert, select, update

from tcg_pokedex.sync_runs.adapters.tables import sync_runs
from tcg_pokedex.sync_runs.domain import SyncRun


class PostgresSyncRunRepository:
    """SyncRunRepository on Postgres. Each call is its own committed transaction."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def start_run[R: BaseModel](self, run: SyncRun[R]) -> None:
        with self._engine.begin() as connection:
            connection.execute(insert(sync_runs).values(_run_row(run)))

    def finish_run[R: BaseModel](self, run: SyncRun[R]) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                update(sync_runs).where(sync_runs.c.id == run.id).values(_run_row(run))
            )

    def get_run[R: BaseModel](self, run_id: UUID, result: type[R]) -> SyncRun[R] | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(select(sync_runs).where(sync_runs.c.id == run_id))
                .mappings()
                .one_or_none()
            )
        return None if row is None else SyncRun[result].model_validate(dict(row))


def _run_row[R: BaseModel](run: SyncRun[R]) -> dict[str, Any]:
    return {
        "id": run.id,
        "kind": run.kind.value,
        "source": run.source,
        "status": run.status.value,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "duration_ms": run.duration_ms,
        "result": None if run.result is None else run.result.model_dump(mode="json"),
        "error": run.error,
    }
