"""What every sync shares: the run record, its storage, the one-sync-at-a-time lock,
the JSON log and exit codes."""

import json
import logging
import sys
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Connection, Engine, func, insert, select, text, update

from tcg_pokedex.schemas import RunStatus, SyncKind
from tcg_pokedex.tables import sync_runs
from tcg_pokedex.tcgdex import SOURCE

MAX_FAILURES = 100
"""A run's result keeps at most this many failures; its counts stay exact."""

SYNC_LOCK = 0x74636773
"""The Postgres advisory lock key every sync takes."""

INTERRUPTED = "interrupted: the process running this sync stopped"

logger = logging.getLogger("tcg_pokedex")


EXIT_CODES = {RunStatus.SUCCEEDED: 0, RunStatus.PARTIAL: 1, RunStatus.FAILED: 2}


class SyncBusyError(Exception):
    """Another sync holds the sync lock."""


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
    with engine.begin() as connection:
        connection.execute(insert(sync_runs).values(_row(run)))
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
    with engine.begin() as connection:
        connection.execute(
            update(sync_runs).where(sync_runs.c.id == run.id).values(_row(run))
        )
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


def get_run[R: BaseModel](
    engine: Engine, run_id: UUID, result: type[R]
) -> SyncRun[R] | None:
    with engine.connect() as connection:
        row = (
            connection.execute(select(sync_runs).where(sync_runs.c.id == run_id))
            .mappings()
            .one_or_none()
        )
    return None if row is None else SyncRun[result].model_validate(dict(row))


def _row[R: BaseModel](run: SyncRun[R]) -> dict[str, Any]:
    return {
        **run.model_dump(exclude={"result"}),
        "result": None if run.result is None else run.result.model_dump(mode="json"),
    }


def claim_syncs(engine: Engine) -> Connection | None:
    """Take the sync lock alone, or return None while any sync or set download holds it.

    The lock is a session-level Postgres advisory lock on a connection of its own, so
    it ends with that connection or its process. Holding it alone means no sync is
    alive, so runs still marked running are closed as interrupted.
    """
    connection = engine.connect()
    try:
        if not connection.scalar(select(func.pg_try_advisory_lock(SYNC_LOCK))):
            connection.close()
            return None
        connection.execute(
            update(sync_runs)
            .where(sync_runs.c.status == RunStatus.RUNNING)
            .values(status=RunStatus.FAILED, error=INTERRUPTED)
        )
        connection.commit()
    except BaseException:
        release_syncs(connection)
        raise
    return connection


def join_syncs(engine: Engine) -> Connection:
    """Take the sync lock shared with other set downloads, after any running sync."""
    connection = engine.connect()
    try:
        connection.execute(select(func.pg_advisory_lock_shared(SYNC_LOCK)))
        connection.commit()
    except BaseException:
        release_syncs(connection)
        raise
    return connection


def release_syncs(connection: Connection) -> None:
    """Drop the lock's connection, which ends its session and the lock with it."""
    connection.invalidate()
    connection.close()


def syncs_running(connection: Connection) -> bool:
    """Whether any sync or set download holds the sync lock."""
    held = text(
        "SELECT EXISTS (SELECT FROM pg_locks WHERE locktype = 'advisory'"
        " AND database = (SELECT oid FROM pg_database"
        " WHERE datname = current_database())"
        " AND classid = 0 AND objid = CAST(:key AS oid) AND objsubid = 1"
        " AND granted)"
    )
    return bool(connection.scalar(held, {"key": SYNC_LOCK}))


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
