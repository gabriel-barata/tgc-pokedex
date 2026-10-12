from fastapi.testclient import TestClient
from pydantic import PostgresDsn

from tcg_pokedex.app import create_app
from tcg_pokedex.config import Settings

UNREACHABLE_DATABASE_URL = "postgresql+psycopg://nobody:nothing@127.0.0.1:1/nowhere"


def test_healthz_returns_ok_when_the_database_is_reachable(postgres_url: str) -> None:
    settings = Settings(database_url=PostgresDsn(postgres_url))

    with TestClient(create_app(settings)) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_healthz_returns_503_when_the_database_is_unreachable() -> None:
    settings = Settings(database_url=PostgresDsn(UNREACHABLE_DATABASE_URL))

    with TestClient(create_app(settings)) as client:
        response = client.get("/healthz")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
