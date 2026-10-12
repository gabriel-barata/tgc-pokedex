"""Set tracking routes on `create_app`, real Postgres and recorded TCGdex answers."""

from collections.abc import Iterator, Mapping, Sequence
from datetime import date
from pathlib import Path
from uuid import UUID

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import PostgresDsn
from sqlalchemy import Engine, insert, select

from tcg_pokedex.app import create_app
from tcg_pokedex.config import Settings
from tcg_pokedex.routes.sets import DownloadRegistry, card_ownership
from tcg_pokedex.tables import (
    HOUSEHOLD_OWNER_ID,
    owners,
    series,
    set_artwork,
    sets,
    sync_runs,
    tracked_sets,
)
from tcg_pokedex.tcgdex import SOURCE, Variant
from tests.helpers import (
    SEEDED_AT,
    FixtureRoutes,
    card_row,
    english,
    image,
    seed,
    set_row,
)

PT_001 = "https://assets.tcgdex.net/pt/sv/sv01/001"
EN_002 = "https://assets.tcgdex.net/en/swsh/swshp/SWSH032"
OTHER_OWNER_ID = UUID("00000000-0000-4000-8000-000000000002")
PROVENANCE = {"source": SOURCE, "fetched_at": SEEDED_AT}
N, R, H = Variant.NORMAL, Variant.REVERSE, Variant.HOLO


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
def app(
    database_url: str, engine: Engine, tmp_path: Path, served: FixtureRoutes
) -> FastAPI:
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
    return create_app(settings, tcgdex_transport=httpx2.MockTransport(served))


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
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


def test_sets_are_listed_by_series_newest_first_with_the_owners_tracking(
    app: FastAPI, client: TestClient, engine: Engine
) -> None:
    with engine.begin() as connection:
        connection.execute(
            insert(series).values(id="me", name="Megaevolução", **PROVENANCE)
        )
        connection.execute(
            insert(sets),
            [
                {**set_row(id=set_id, release_date=released, **more), **PROVENANCE}
                for set_id, released, more in [
                    ("sv02", date(2023, 6, 9), {"name": "Evoluções em Paldea"}),
                    (
                        "mep",
                        date(2025, 9, 26),
                        {
                            "series_id": "me",
                            "name": "MEP Black Star Promos",
                            "official_count": 0,
                            "total_count": 88,
                        },
                    ),
                ]
            ],
        )
        connection.execute(insert(owners).values(id=OTHER_OWNER_ID, name="Outra"))
        connection.execute(
            insert(tracked_sets),
            [
                {
                    "owner_id": HOUSEHOLD_OWNER_ID,
                    "set_id": "sv01",
                    "tracked_at": SEEDED_AT,
                },
                {"owner_id": OTHER_OWNER_ID, "set_id": "sv02", "tracked_at": SEEDED_AT},
            ],
        )
        connection.execute(
            insert(set_artwork).values(set_id="sv01", kind="logo", **PROVENANCE)
        )
    registry: DownloadRegistry = app.state.registry
    registry.start("mep")

    listed = client.get("/api/sets")

    assert listed.status_code == 200
    assert listed.json() == [
        {
            "id": "me",
            "name": "Megaevolução",
            "sets": [
                {
                    "id": "mep",
                    "name": "MEP Black Star Promos",
                    "release_date": "2025-09-26",
                    "card_count": 88,
                    "has_logo": False,
                    "has_symbol": False,
                    "tracked": False,
                    "downloading": True,
                }
            ],
        },
        {
            "id": "sv",
            "name": "Escarlate e Violeta",
            "sets": [
                {
                    "id": "sv02",
                    "name": "Evoluções em Paldea",
                    "release_date": "2023-06-09",
                    "card_count": 198,
                    "has_logo": False,
                    "has_symbol": False,
                    "tracked": False,
                    "downloading": False,
                },
                {
                    "id": "sv01",
                    "name": "Escarlate e Violeta",
                    "release_date": "2023-03-31",
                    "card_count": 198,
                    "has_logo": True,
                    "has_symbol": False,
                    "tracked": True,
                    "downloading": False,
                },
            ],
        },
    ]


@pytest.mark.parametrize(
    ("listed", "stored", "quantities", "owned", "wanted_version_missing"),
    [
        ([N, R], {}, [(N, 0), (R, 0)], False, False),
        ([N], {N: 1}, [(N, 1)], True, False),
        ([N, R], {N: 2}, [(N, 2), (R, 0)], True, True),
        ([N, R], {R: 1}, [(N, 0), (R, 1)], True, False),
        ([N, R], {N: 3, R: 1}, [(N, 3), (R, 1)], True, False),
        ([H], {H: 1}, [(H, 1)], True, False),
        ([N], {N: 1, R: 3}, [(N, 1)], True, False),
    ],
)
def test_card_ownership_follows_the_rules_table(
    listed: Sequence[Variant],
    stored: Mapping[Variant, int],
    quantities: list[tuple[Variant, int]],
    owned: bool,
    wanted_version_missing: bool,
) -> None:
    result = card_ownership("sv01-001", listed, stored)

    assert result.model_dump(mode="json") == {
        "card_id": "sv01-001",
        "variants": [
            {"variant": variant.value, "quantity": quantity}
            for variant, quantity in quantities
        ],
        "owned": owned,
        "wanted_version_missing": wanted_version_missing,
    }
