"""Set routes: list every set, track and untrack one, read its image progress and
the owner's ownership of its cards."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from sqlalchemy import Engine

from tcg_pokedex.controllers.dependencies import Database, Owner
from tcg_pokedex.jobs.set_download import DownloadRegistry, download_set
from tcg_pokedex.models import ownership, tracking
from tcg_pokedex.models.catalog import set_exists
from tcg_pokedex.views.ownership import SetOwnership
from tcg_pokedex.views.sets import SeriesEntry, SetTracking

UNKNOWN_SET: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": "The set is not in the catalog"}
}

router = APIRouter(prefix="/api/sets")


@router.get("")
def list_sets(owner_id: Owner, engine: Database, request: Request) -> list[SeriesEntry]:
    """Every set grouped by series, newest release first, with the owner's tracking."""
    registry: DownloadRegistry = request.app.state.registry
    return ownership.list_series(engine, owner_id, registry.running())


@router.get("/{set_id}/ownership", responses=UNKNOWN_SET)
def get_ownership(set_id: str, owner_id: Owner, engine: Database) -> SetOwnership:
    """Every card of the set with the owner's quantity per variant and its flags."""
    result = ownership.set_ownership(engine, owner_id, set_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown set")
    return result


@router.get("/{set_id}/tracking", responses=UNKNOWN_SET)
def get_tracking(
    set_id: str, owner_id: Owner, engine: Database, request: Request
) -> SetTracking:
    return _tracking(engine, request, owner_id, set_id)


@router.put("/{set_id}/tracking", responses=UNKNOWN_SET)
def track_set(
    set_id: str,
    owner_id: Owner,
    engine: Database,
    request: Request,
    background: BackgroundTasks,
) -> SetTracking:
    """Track the set and, when it was untracked, download its images afterwards."""
    _require_set(engine, set_id)
    newly_tracked = tracking.track_set(engine, owner_id, set_id, datetime.now(UTC))
    state = request.app.state
    if newly_tracked and state.registry.start(set_id):
        background.add_task(
            download_set,
            engine,
            state.registry,
            state.settings.image_dir,
            state.tcgdex_transport,
            set_id,
        )
    return _tracking(engine, request, owner_id, set_id)


@router.delete("/{set_id}/tracking", responses=UNKNOWN_SET)
def untrack_set(
    set_id: str, owner_id: Owner, engine: Database, request: Request
) -> SetTracking:
    """Untrack the set. Its cached images stay, and a running download goes on."""
    _require_set(engine, set_id)
    tracking.untrack_set(engine, owner_id, set_id)
    return _tracking(engine, request, owner_id, set_id)


def _require_set(engine: Engine, set_id: str) -> None:
    if not set_exists(engine, set_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown set")


def _tracking(
    engine: Engine, request: Request, owner_id: UUID, set_id: str
) -> SetTracking:
    _require_set(engine, set_id)
    registry: DownloadRegistry = request.app.state.registry
    return tracking.set_tracking(
        engine, owner_id, set_id, downloading=registry.is_running(set_id)
    )
