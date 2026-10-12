from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx2
from fastapi import FastAPI

from tcg_pokedex.config import Settings
from tcg_pokedex.db import create_database_engine
from tcg_pokedex.routes import health, images, sets
from tcg_pokedex.routes.sets import DownloadRegistry
from tcg_pokedex.spa import SpaStaticFiles


def create_app(
    settings: Settings | None = None,
    tcgdex_transport: httpx2.BaseTransport | None = None,
) -> FastAPI:
    """Build the app. uvicorn's --factory calls it with no arguments.

    `tcgdex_transport` is a test seam for the TCGdex requests of image downloads.
    """
    settings = settings or Settings()
    engine = create_database_engine(str(settings.database_url))

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        yield
        engine.dispose()

    show_docs = settings.environment == "dev"
    app = FastAPI(
        title="TCG Pokédex",
        docs_url="/docs" if show_docs else None,
        redoc_url="/redoc" if show_docs else None,
        openapi_url="/openapi.json" if show_docs else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.registry = DownloadRegistry()
    app.state.tcgdex_transport = tcgdex_transport
    app.include_router(health.router)
    app.include_router(sets.router)
    app.include_router(images.router)
    if settings.spa_dir is not None:
        app.mount("/", SpaStaticFiles(str(settings.spa_dir)), name="spa")
    return app
