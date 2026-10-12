"""What every sync shares: the run record's lifecycle, the JSON log and exit codes."""

import json
import logging
import sys
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import Engine

from tcg_pokedex.models.sync_runs import insert_run, update_run
from tcg_pokedex.views.sync import RunStatus, SyncKind, SyncRun

logger = logging.getLogger("tcg_pokedex")

EXIT_CODES = {RunStatus.SUCCEEDED: 0, RunStatus.PARTIAL: 1, RunStatus.FAILED: 2}


class SyncBusyError(Exception):
    """Another sync holds the sync lock."""


def run_status(*, aborted: bool, failed: int) -> RunStatus:
    """An aborted run failed; otherwise any failed item makes it partial."""
    if aborted:
        return RunStatus.FAILED
    return RunStatus.PARTIAL if failed else RunStatus.SUCCEEDED


def start_run[R: BaseModel](
    engine: Engine,
    kind: SyncKind,
    started_at: datetime,
    result: type[R],
    **fields: object,
) -> SyncRun[R]:
    """Record an open run, committed before the sync writes anything."""
    run = SyncRun[result](
        id=uuid4(), kind=kind, status=RunStatus.RUNNING, started_at=started_at
    )
    insert_run(engine, run)
    log("sync.run.started", run_id=str(run.id), kind=kind.value, **fields)
    return run


def close_run[R: BaseModel](
    run: SyncRun[R],
    *,
    status: RunStatus,
    result: R,
    error: str | None,
    finished_at: datetime,
) -> SyncRun[R]:
    return run.model_copy(
        update={
            "status": status,
            "finished_at": finished_at,
            "duration_ms": (finished_at - run.started_at) // timedelta(milliseconds=1),
            "result": result,
            "error": error,
        }
    )


def finish_run[R: BaseModel](engine: Engine, run: SyncRun[R]) -> SyncRun[R]:
    """Store the closed run and log it."""
    update_run(engine, run)
    counts: object = getattr(run.result, "counts", None)
    log(
        "sync.run.finished",
        run_id=str(run.id),
        status=run.status.value,
        duration_ms=run.duration_ms,
        counts=counts.model_dump(mode="json")
        if isinstance(counts, BaseModel)
        else None,
        error=run.error,
    )
    return run


def log(event: str, **fields: object) -> None:
    logger.info(event, extra={"fields": fields})


class JsonLineFormatter(logging.Formatter):
    """One JSON object per record: `event`, `level`, `time` and the record's fields."""

    def format(self, record: logging.LogRecord) -> str:
        fields: dict[str, object] = record.__dict__.get("fields", {})
        return json.dumps(
            {
                "event": record.getMessage(),
                "level": record.levelname,
                "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
                **fields,
            },
            ensure_ascii=False,
        )


@contextmanager
def json_lines_on_stderr() -> Generator[None]:
    """Send the app's log only to stderr, as JSON lines, while the block runs."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonLineFormatter())
    previous_level, previous_propagate = logger.level, logger.propagate
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        yield
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate


def report_runs(sync: Callable[[], Sequence[SyncRun[Any]]]) -> int:
    """Run syncs, print each closed run as a JSON line, and return the worst exit code.

    The app's log goes only to stderr, as JSON lines. When another sync holds the lock,
    or a run record cannot be created or closed, it prints nothing, logs
    `sync.run.error` and returns 2.
    """
    with json_lines_on_stderr():
        try:
            runs = sync()
        except Exception as error:
            logger.error("sync.run.error", extra={"fields": {"error": str(error)}})
            return EXIT_CODES[RunStatus.FAILED]
    for run in runs:
        print(run.model_dump_json())
    return max(EXIT_CODES[run.status] for run in runs)
