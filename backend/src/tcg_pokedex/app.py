from fastapi import FastAPI

from tcg_pokedex.config import Settings
from tcg_pokedex.health.api.routes import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. uvicorn's --factory calls it with no arguments."""
    settings = settings or Settings()
    show_docs = settings.environment == "dev"
    app = FastAPI(
        title="TCG Pokédex",
        docs_url="/docs" if show_docs else None,
        redoc_url="/redoc" if show_docs else None,
        openapi_url="/openapi.json" if show_docs else None,
    )
    app.include_router(health_router)
    return app
