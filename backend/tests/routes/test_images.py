from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tcg_pokedex.app import create_app
from tcg_pokedex.config import Settings
from tcg_pokedex.services.image_sync import write_file
from tests.helpers import PIXEL


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    image_dir = tmp_path / "images"
    write_file(image_dir / "cards" / "sv01-001", "small", PIXEL)
    write_file(image_dir / "sets" / "sv01", "logo", PIXEL)
    with TestClient(create_app(Settings(image_dir=image_dir))) as test_client:
        yield test_client


@pytest.mark.parametrize(
    "path", ["/api/images/cards/sv01-001/small", "/api/images/sets/sv01/logo"]
)
def test_cached_images_are_served_with_long_lived_cache_headers(
    client: TestClient, path: str
) -> None:
    served = client.get(path)
    revalidated = client.get(path, headers={"If-None-Match": served.headers["etag"]})

    assert served.status_code == 200
    assert served.content == PIXEL
    assert served.headers["content-type"] == "image/webp"
    assert served.headers["cache-control"] == "public, max-age=604800"
    assert revalidated.status_code == 304


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/api/images/cards/sv01-001/large", 404),
        ("/api/images/cards/%2E%2E/small", 404),
        ("/api/images/cards/sv01-001/medium", 422),
        ("/api/images/sets/sv01/symbol", 404),
    ],
)
def test_uncached_or_invalid_images_are_refused(
    client: TestClient, path: str, status: int
) -> None:
    assert client.get(path).status_code == status
