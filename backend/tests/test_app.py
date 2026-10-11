import pytest
from fastapi.testclient import TestClient

from tcg_pokedex.app import create_app
from tcg_pokedex.config import Settings

API_DOCS_PATHS = ["/docs", "/redoc", "/openapi.json"]


@pytest.mark.parametrize("path", API_DOCS_PATHS)
def test_dev_serves_api_docs(path: str) -> None:
    client = TestClient(create_app(Settings(environment="dev")))

    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", API_DOCS_PATHS)
def test_prod_hides_api_docs(path: str) -> None:
    client = TestClient(create_app(Settings(environment="prod")))

    assert client.get(path).status_code == 404
