"""End to end: the tracking and image routes on `create_app`, real Postgres, temp
image directory and recorded TCGdex answers.

sv01 holds a pt card, a card with only an English image and a card with neither.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient
from pydantic import PostgresDsn
from sqlalchemy import select

from tcg_pokedex.app import create_app
from tcg_pokedex.catalog_sync.adapters.postgres import PostgresCatalogRepository
from tcg_pokedex.catalog_sync.domain import SetBatch
from tcg_pokedex.config import Settings
from tcg_pokedex.database import create_database_engine
from tcg_pokedex.migrations import upgrade_to_head
from tcg_pokedex.sync_runs.adapters.tables import sync_runs
from tests.catalog_sync.builders import make_card, make_series, make_set
from tests.image_cache.assets import PIXEL, english, image
from tests.tcgdex.fixtures import FixtureRoutes

AT = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
PT_001 = "https://assets.tcgdex.net/pt/sv/sv01/001"
EN_002 = "https://assets.tcgdex.net/en/swsh/swshp/SWSH032"


@pytest.fixture
def served() -> FixtureRoutes:
    return FixtureRoutes(
        {
            **image(PT_001),
            **english("sv01-002", "swshp-SWSH032.json"),
            **image(EN_002),
            **english("sv01-003"),
        }
    )


@pytest.fixture
def database_url(empty_database_url: str) -> str:
    upgrade_to_head(empty_database_url)
    engine = create_database_engine(empty_database_url)
    cards = (
        make_card(image_url=PT_001),
        make_card(id="sv01-002", image_url=None),
        make_card(id="sv01-003", image_url=None),
    )
    try:
        PostgresCatalogRepository(engine).save_set(
            SetBatch(series=make_series(), card_set=make_set(), cards=cards), AT
        )
    finally:
        engine.dispose()
    return empty_database_url


@pytest.fixture
def client(
    database_url: str, tmp_path: Path, served: FixtureRoutes
) -> Iterator[TestClient]:
    settings = Settings(
        database_url=PostgresDsn(database_url), image_dir=tmp_path / "images"
    )
    app = create_app(settings, image_transport=httpx2.MockTransport(served))
    with TestClient(app) as test_client:
        yield test_client


def recorded_runs(database_url: str) -> list[tuple[str, str]]:
    engine = create_database_engine(database_url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(select(sync_runs.c.kind, sync_runs.c.status))
            return [(kind, status) for kind, status in rows]
    finally:
        engine.dispose()


def test_tracking_a_set_downloads_its_images_and_serves_them_locally(
    client: TestClient, served: FixtureRoutes, database_url: str
) -> None:
    tracked = client.put("/api/sets/sv01/tracking")

    assert tracked.status_code == 200
    assert tracked.json() == {
        "set_id": "sv01",
        "tracked": True,
        "total_cards": 3,
        "cached": 0,
        "unavailable": 0,
        "downloading": True,
    }
    progress = client.get("/api/sets/sv01/tracking").json()
    assert (progress["cached"], progress["unavailable"]) == (2, 1)
    assert progress["downloading"] is False
    downloads = len(served.requests)
    for card_id in ("sv01-001", "sv01-002"):
        for size in ("small", "large"):
            served_image = client.get(f"/api/images/cards/{card_id}/{size}")
            assert served_image.status_code == 200
            assert served_image.headers["content-type"] == "image/webp"
            assert served_image.headers["cache-control"] == "public, max-age=604800"
            assert served_image.content == PIXEL
    etag = client.get("/api/images/cards/sv01-001/small").headers["etag"]
    revalidated = client.get(
        "/api/images/cards/sv01-001/small", headers={"If-None-Match": etag}
    )
    assert revalidated.status_code == 304
    assert client.put("/api/sets/sv01/tracking").json()["downloading"] is False
    assert len(served.requests) == downloads
    assert recorded_runs(database_url) == [("images", "succeeded")]


@pytest.mark.parametrize(
    ("method", "path", "status"),
    [
        ("GET", "/api/images/cards/sv01-003/small", 404),
        ("GET", "/api/images/cards/%2E%2E/small", 404),
        ("GET", "/api/images/cards/sv01-001/medium", 422),
        ("GET", "/api/images/sets/sv01/logo", 404),
        ("GET", "/api/sets/xy1/tracking", 404),
        ("PUT", "/api/sets/xy1/tracking", 404),
    ],
)
def test_unknown_or_uncached_resources_are_refused(
    client: TestClient, method: str, path: str, status: int
) -> None:
    assert client.request(method, path).status_code == status
