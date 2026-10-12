"""Image routes. Images are served from files only, never from the provider."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import FileResponse

from tcg_pokedex.jobs.image_store import artwork_path, card_path
from tcg_pokedex.views.images import ArtworkKind, CardSize

CACHE_CONTROL = "public, max-age=604800"
IMAGE: dict[int | str, dict[str, Any]] = {
    status.HTTP_200_OK: {"content": {"image/webp": {}}},
    status.HTTP_304_NOT_MODIFIED: {"description": "The cached copy is current"},
    status.HTTP_404_NOT_FOUND: {"description": "The image is not cached"},
}

router = APIRouter(prefix="/api/images")


@router.get("/cards/{card_id}/{size}", response_class=FileResponse, responses=IMAGE)
def card_image(card_id: str, size: CardSize, request: Request) -> Response:
    image_dir: Path = request.app.state.settings.image_dir
    return _serve(card_path(image_dir, card_id, size), request)


@router.get("/sets/{set_id}/{kind}", response_class=FileResponse, responses=IMAGE)
def set_artwork(set_id: str, kind: ArtworkKind, request: Request) -> Response:
    image_dir: Path = request.app.state.settings.image_dir
    return _serve(artwork_path(image_dir, set_id, kind), request)


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
