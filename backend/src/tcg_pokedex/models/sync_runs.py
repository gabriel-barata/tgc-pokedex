from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import (
    Connection,
    Engine,
    RowMapping,
    func,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from tcg_pokedex.models.base import Base
from tcg_pokedex.views.sync import (
    ImageSyncResult,
    RunCounts,
    RunFailure,
    RunStatus,
    SyncKind,
    SyncResult,
    SyncRun,
    SyncRunEntry,
    SyncStatus,
)

LATEST_RUNS = 20

SYNC_LOCK = 0x74636773
"""The Postgres advisory lock key every sync takes."""

INTERRUPTED = "interrupted: the process running this sync stopped"


class SyncRunRow(Base):
    __tablename__ = "sync_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str]
    source: Mapped[str]
    status: Mapped[str]
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
    duration_ms: Mapped[int | None]
    result: Mapped[dict[str, Any] | None] = mapped_column(postgresql.JSONB)
    error: Mapped[str | None]


def insert_run(engine: Engine, run: SyncRun[Any]) -> None:
    with engine.begin() as connection:
        connection.execute(insert(SyncRunRow).values(_row(run)))


def update_run(engine: Engine, run: SyncRun[Any]) -> None:
    with engine.begin() as connection:
        connection.execute(
            update(SyncRunRow).where(SyncRunRow.id == run.id).values(_row(run))
        )


def get_run[R: BaseModel](
    engine: Engine, run_id: UUID, result: type[R]
) -> SyncRun[R] | None:
    with engine.connect() as connection:
        row = (
            connection.execute(select(SyncRunRow).where(SyncRunRow.id == run_id))
            .mappings()
            .one_or_none()
        )
    return None if row is None else SyncRun[result].model_validate(dict(row))


def sync_status(engine: Engine) -> SyncStatus:
    """The latest runs. A run still marked running while no sync holds the lock was
    interrupted."""
    latest = (
        select(SyncRunRow)
        .order_by(SyncRunRow.started_at.desc(), SyncRunRow.id.desc())
        .limit(LATEST_RUNS)
    )
    with engine.connect() as connection:
        running = _syncs_running(connection)
        rows = list(connection.execute(latest).mappings())
    return SyncStatus(running=running, runs=[_entry(row, running) for row in rows])


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
            update(SyncRunRow)
            .where(SyncRunRow.status == RunStatus.RUNNING)
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


def run_counts(result: SyncResult | ImageSyncResult) -> RunCounts:
    """A catalog run fetches payloads and creates or changes rows; an image run asks for
    files, which are downloaded or unavailable, and writes the downloaded ones."""
    if isinstance(result, SyncResult):
        counts = result.counts
        kinds = (counts.series, counts.sets, counts.cards)
        return RunCounts(
            fetched=sum(kind.fetched for kind in kinds),
            updated=sum(kind.created + kind.updated for kind in kinds),
            failed=counts.sets.failed + counts.cards.failed,
        )
    images = (result.counts.cards, result.counts.artwork)
    return RunCounts(
        fetched=sum(kind.downloaded + kind.unavailable for kind in images),
        updated=sum(kind.downloaded for kind in images),
        failed=sum(kind.failed for kind in images),
    )


def _syncs_running(connection: Connection) -> bool:
    """Whether any sync or set download holds the sync lock."""
    held = text(
        "SELECT EXISTS (SELECT FROM pg_locks WHERE locktype = 'advisory'"
        " AND database = (SELECT oid FROM pg_database"
        " WHERE datname = current_database())"
        " AND classid = 0 AND objid = CAST(:key AS oid) AND objsubid = 1"
        " AND granted)"
    )
    return bool(connection.scalar(held, {"key": SYNC_LOCK}))


def _row(run: SyncRun[Any]) -> dict[str, Any]:
    return {
        **run.model_dump(exclude={"result"}),
        "result": None if run.result is None else run.result.model_dump(mode="json"),
    }


def _entry(row: RowMapping, running: bool) -> SyncRunEntry:
    kind = SyncKind(row["kind"])
    counts, failures = None, []
    if row["result"] is not None:
        result = (
            SyncResult.model_validate(row["result"])
            if kind is SyncKind.CATALOG
            else ImageSyncResult.model_validate(row["result"])
        )
        counts = run_counts(result)
        failures = [
            RunFailure.model_validate(failure.model_dump())
            for failure in result.failures
        ]
    interrupted = row["status"] == RunStatus.RUNNING and not running
    return SyncRunEntry(
        id=row["id"],
        kind=kind,
        status=RunStatus.FAILED if interrupted else RunStatus(row["status"]),
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        duration_ms=row["duration_ms"],
        counts=counts,
        failures=failures,
        error=INTERRUPTED if interrupted else row["error"],
    )
