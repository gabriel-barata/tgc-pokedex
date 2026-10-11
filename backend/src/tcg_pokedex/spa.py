from pathlib import PurePosixPath

from starlette import status
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

API_PREFIX = "api"


def is_client_route(path: str) -> bool:
    """A path the SPA's router handles: not under /api and not a file name."""
    route = PurePosixPath(path)
    return route.parts[:1] != (API_PREFIX,) and "." not in route.name


class SpaStaticFiles(StaticFiles):
    """Serves the built SPA, falling back to index.html for client-side routes.

    index.html is sent with Cache-Control: no-cache, so a new deploy's asset
    names are picked up on the next page load.
    """

    def __init__(self, directory: str) -> None:
        super().__init__(directory=directory, html=True)

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            not_found = exc.status_code == status.HTTP_404_NOT_FOUND
            if not (not_found and is_client_route(path)):
                raise
            response = await super().get_response("index.html", scope)
        if response.media_type == "text/html":
            response.headers["Cache-Control"] = "no-cache"
        return response
