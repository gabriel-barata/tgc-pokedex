"""Sync routes: the latest sync runs, and "Sincronizar agora"."""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import Connection, Engine, RowMapping, select

from tcg_pokedex.db import get_engine
from tcg_pokedex.schemas import (
    RunCounts,
    RunFailure,
    RunStatus,
    SyncKind,
    SyncRunEntry,
    SyncStatus,
)
from tcg_pokedex.services.catalog_sync import SyncResult
from tcg_pokedex.services.full_sync import sync_all
from tcg_pokedex.services.image_sync import ImageSyncResult
from tcg_pokedex.services.sync_runs import (
    INTERRUPTED,
    claim_syncs,
    release_syncs,
    syncs_running,
)
from tcg_pokedex.tables import sync_runs
from tcg_pokedex.tcgdex import Tcgdex

LATEST_RUNS = 20

BUSY: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {"description": "Another sync is running"}
}

router = APIRouter(prefix="/api/sync")

DB = Annotated[Engine, Depends(get_engine)]


@router.get("")
def get_sync_status(engine: DB) -> SyncStatus:
    return _sync_status(engine)


@router.post("", status_code=status.HTTP_202_ACCEPTED, responses=BUSY)
def sync_now(engine: DB, request: Request, background: BackgroundTasks) -> SyncStatus:
    """Start the catalog sync, then the image sync, in the background."""
    lock = claim_syncs(engine)
    if lock is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Another sync is running")
    background.add_task(_sync_all, request, lock)
    return _sync_status(engine)


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


def _sync_status(engine: Engine) -> SyncStatus:
    """A run still marked running while no sync holds the lock was interrupted."""
    with engine.connect() as connection:
        running = syncs_running(connection)
        rows = _latest_runs(connection)
    return SyncStatus(running=running, runs=[_entry(row, running) for row in rows])


def _latest_runs(connection: Connection) -> list[RowMapping]:
    statement = (
        select(sync_runs)
        .order_by(sync_runs.c.started_at.desc(), sync_runs.c.id.desc())
        .limit(LATEST_RUNS)
    )
    return list(connection.execute(statement).mappings())


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


def _sync_all(request: Request, lock: Connection) -> None:
    state = request.app.state
    try:
        with Tcgdex(transport=state.tcgdex_transport) as tcgdex:
            sync_all(state.engine, tcgdex, state.settings.image_dir)
    finally:
        release_syncs(lock)
