from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import PostgresDsn

from tcg_pokedex.app import create_app
from tcg_pokedex.config import Settings

INDEX_HTML = '<!doctype html><div id="root"></div>'
APP_JS = "console.log('app');"
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://nobody:nothing@127.0.0.1:1/nowhere"


@pytest.fixture
def spa_dir(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text(INDEX_HTML)
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text(APP_JS)
    return tmp_path


@pytest.fixture
def client(spa_dir: Path) -> TestClient:
    settings = Settings(
        environment="prod",
        database_url=PostgresDsn(UNREACHABLE_DATABASE_URL),
        spa_dir=spa_dir,
    )
    return TestClient(create_app(settings))


def test_serves_the_index_page_at_the_root(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.text == INDEX_HTML
    assert response.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize("path", ["/sets", "/sets/sv08", "/assets"])
def test_serves_the_index_page_for_client_side_routes(
    client: TestClient, path: str
) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert response.text == INDEX_HTML
    assert response.headers["cache-control"] == "no-cache"


def test_serves_built_assets(client: TestClient) -> None:
    response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert response.text == APP_JS
    assert "cache-control" not in response.headers


@pytest.mark.parametrize("path", ["/assets/missing.js", "/favicon.ico"])
def test_missing_files_are_not_found(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("path", ["/api", "/api/cards", "/api/sets/sv08"])
def test_unknown_api_paths_are_not_found(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_api_routes_take_precedence_over_the_spa(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.json() == {"status": "degraded", "database": "unavailable"}


def test_does_not_serve_the_spa_without_a_spa_dir() -> None:
    client = TestClient(create_app(Settings()))

    assert client.get("/").status_code == 404
