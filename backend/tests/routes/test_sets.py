"""Set tracking routes on `create_app`, real Postgres and recorded TCGdex answers."""

from collections.abc import Iterator
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient
from pydantic import PostgresDsn
from sqlalchemy import Engine, select

from tcg_pokedex.app import create_app
from tcg_pokedex.config import Settings
from tcg_pokedex.tables import sync_runs
from tests.helpers import FixtureRoutes, card_row, english, image, seed, set_row

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
def client(
    database_url: str, engine: Engine, tmp_path: Path, served: FixtureRoutes
) -> Iterator[TestClient]:
    seed(
        engine,
        [set_row()],
        [
            card_row(image_url=PT_001),
            card_row(id="sv01-002", image_url=None),
            card_row(id="sv01-003", image_url=None),
        ],
    )
    settings = Settings(
        database_url=PostgresDsn(database_url), image_dir=tmp_path / "images"
    )
    app = create_app(settings, tcgdex_transport=httpx2.MockTransport(served))
    with TestClient(app) as test_client:
        yield test_client


def test_tracking_a_set_downloads_its_images_once(
    client: TestClient, served: FixtureRoutes, engine: Engine
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
    assert client.put("/api/sets/sv01/tracking").json()["downloading"] is False
    assert len(served.requests) == downloads
    assert client.get("/api/images/cards/sv01-002/large").status_code == 200
    with engine.connect() as connection:
        runs = connection.execute(select(sync_runs.c.kind, sync_runs.c.status)).all()
    assert [tuple(run) for run in runs] == [("images", "succeeded")]


def test_untracking_keeps_the_cached_images(client: TestClient) -> None:
    client.put("/api/sets/sv01/tracking")

    untracked = client.delete("/api/sets/sv01/tracking")
    untracked_again = client.delete("/api/sets/sv01/tracking")

    assert untracked.json()["tracked"] is False
    assert untracked_again.status_code == 200
    assert client.get("/api/images/cards/sv01-001/small").status_code == 200


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_an_unknown_set_is_not_found(client: TestClient, method: str) -> None:
    assert client.request(method, "/api/sets/xy1/tracking").status_code == 404
