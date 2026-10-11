from fastapi import FastAPI

from tcg_pokedex.health.api.routes import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="TCG Pokédex")
    app.include_router(health_router)
    return app
