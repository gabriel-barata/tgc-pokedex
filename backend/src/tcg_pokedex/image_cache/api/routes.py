"""Tracking and image routes. Images are served from files only, never the provider."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import Engine

from tcg_pokedex.clock.ports import Clock
from tcg_pokedex.database import get_engine
from tcg_pokedex.image_cache.adapters.files import FileImageStore
from tcg_pokedex.image_cache.adapters.postgres import PostgresImageCacheRepository
from tcg_pokedex.image_cache.adapters.tcgdex import TcgdexImageProvider
from tcg_pokedex.image_cache.domain import ArtworkKind, CardSize, SetTracking
from tcg_pokedex.image_cache.registry import DownloadRegistry
from tcg_pokedex.image_cache.service import ImageSyncPorts, sync_images
from tcg_pokedex.owners.domain import HOUSEHOLD_OWNER_ID
from tcg_pokedex.sync_runs.adapters.postgres import PostgresSyncRunRepository

CACHE_CONTROL = "public, max-age=604800"
UNKNOWN_SET: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": "The set is not in the catalog"}
}
IMAGE: dict[int | str, dict[str, Any]] = {
    status.HTTP_200_OK: {"content": {"image/webp": {}}},
    status.HTTP_304_NOT_MODIFIED: {"description": "The cached copy is current"},
    status.HTTP_404_NOT_FOUND: {"description": "The image is not cached"},
}

router = APIRouter(prefix="/api")


@dataclass(frozen=True)
class ImageCache:
    """What the image routes share, built once by `create_app`."""

    engine: Engine
    store: FileImageStore
    registry: DownloadRegistry
    clock: Clock
    open_provider: Callable[[], TcgdexImageProvider]


def get_image_cache(request: Request) -> ImageCache:
    image_cache: ImageCache = request.app.state.image_cache
    return image_cache


def get_owner_id() -> UUID:
    """The owner the API acts as. Profiles (PTCG-031) replace only this."""
    return HOUSEHOLD_OWNER_ID


def get_repository(
    engine: Annotated[Engine, Depends(get_engine)],
) -> PostgresImageCacheRepository:
    return PostgresImageCacheRepository(engine)


Cache = Annotated[ImageCache, Depends(get_image_cache)]
Owner = Annotated[UUID, Depends(get_owner_id)]
Repository = Annotated[PostgresImageCacheRepository, Depends(get_repository)]


@router.get("/sets/{set_id}/tracking", responses=UNKNOWN_SET)
def get_tracking(
    set_id: str, owner_id: Owner, repository: Repository, cache: Cache
) -> SetTracking:
    return _tracking(repository, cache, owner_id, set_id)


@router.put("/sets/{set_id}/tracking", responses=UNKNOWN_SET)
def track_set(
    set_id: str,
    owner_id: Owner,
    repository: Repository,
    cache: Cache,
    background: BackgroundTasks,
) -> SetTracking:
    """Track the set and, when it was untracked, download its images afterwards."""
    _require_set(repository, set_id)
    newly_tracked = repository.track(owner_id, set_id, cache.clock.now())
    if newly_tracked and cache.registry.start(set_id):
        background.add_task(_download_set, cache, set_id)
    return _tracking(repository, cache, owner_id, set_id)


@router.get(
    "/images/cards/{card_id}/{size}", response_class=FileResponse, responses=IMAGE
)
def card_image(
    card_id: str, size: CardSize, request: Request, cache: Cache
) -> Response:
    return _serve(cache.store.card_path(card_id, size), request)


@router.get(
    "/images/sets/{set_id}/{kind}", response_class=FileResponse, responses=IMAGE
)
def set_artwork(
    set_id: str, kind: ArtworkKind, request: Request, cache: Cache
) -> Response:
    return _serve(cache.store.artwork_path(set_id, kind), request)


def _require_set(repository: PostgresImageCacheRepository, set_id: str) -> None:
    if not repository.set_exists(set_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown set")


def _tracking(
    repository: PostgresImageCacheRepository,
    cache: ImageCache,
    owner_id: UUID,
    set_id: str,
) -> SetTracking:
    _require_set(repository, set_id)
    progress = repository.progress(owner_id, set_id)
    return progress.model_copy(
        update={"downloading": cache.registry.is_running(set_id)}
    )


def _download_set(cache: ImageCache, set_id: str) -> None:
    try:
        with cache.open_provider() as provider:
            ports = ImageSyncPorts(
                provider=provider,
                store=cache.store,
                repository=PostgresImageCacheRepository(cache.engine),
                runs=PostgresSyncRunRepository(cache.engine),
            )
            sync_images(ports, cache.clock, set_id=set_id)
    finally:
        cache.registry.finish(set_id)


def _serve(path: Path | None, request: Request) -> Response:
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not cached")
    response = FileResponse(
        path,
        media_type="image/webp",
        headers={"Cache-Control": CACHE_CONTROL},
        stat_result=path.stat(),
    )
    etag = response.headers["etag"]
    if request.headers.get("if-none-match") == etag:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={"ETag": etag, "Cache-Control": CACHE_CONTROL},
        )
    return response
