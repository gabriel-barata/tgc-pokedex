from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from tcg_pokedex.config import Settings
from tcg_pokedex.database import create_database_engine
from tcg_pokedex.health.api.routes import router as health_router
from tcg_pokedex.spa import SpaStaticFiles


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. uvicorn's --factory calls it with no arguments."""
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
    app.state.engine = engine
    app.include_router(health_router)
    if settings.spa_dir is not None:
        app.mount("/", SpaStaticFiles(str(settings.spa_dir)), name="spa")
    return app
