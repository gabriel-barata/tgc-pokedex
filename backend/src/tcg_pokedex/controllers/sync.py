"""Sync routes: the latest sync runs, and "Sincronizar agora"."""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from sqlalchemy import Connection

from tcg_pokedex.controllers.dependencies import Database
from tcg_pokedex.jobs.full_sync import sync_all
from tcg_pokedex.models.sync_runs import claim_syncs, release_syncs, sync_status
from tcg_pokedex.providers.tcgdex import Tcgdex
from tcg_pokedex.views.sync import SyncStatus

BUSY: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {"description": "Another sync is running"}
}

router = APIRouter(prefix="/api/sync")


@router.get("")
def get_sync_status(engine: Database) -> SyncStatus:
    return sync_status(engine)


@router.post("", status_code=status.HTTP_202_ACCEPTED, responses=BUSY)
def sync_now(
    engine: Database, request: Request, background: BackgroundTasks
) -> SyncStatus:
    """Start the catalog sync, then the image sync, in the background."""
    lock = claim_syncs(engine)
    if lock is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Another sync is running")
    background.add_task(_sync_all, request, lock)
    return sync_status(engine)


def _sync_all(request: Request, lock: Connection) -> None:
    state = request.app.state
    try:
        with Tcgdex(transport=state.tcgdex_transport) as tcgdex:
            sync_all(state.engine, tcgdex, state.settings.image_dir)
    finally:
        release_syncs(lock)
