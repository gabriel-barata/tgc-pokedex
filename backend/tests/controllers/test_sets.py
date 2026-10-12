"""Set routes on `create_app`, real Postgres and recorded TCGdex answers."""

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import PostgresDsn
from sqlalchemy import Engine, insert, select

from tcg_pokedex.app import create_app
from tcg_pokedex.config import Settings
from tcg_pokedex.jobs.set_download import DownloadRegistry
from tcg_pokedex.models.catalog import Card, Series, Set
from tcg_pokedex.models.images import SetArtwork
from tcg_pokedex.models.owner import HOUSEHOLD_OWNER_ID, Owner
from tcg_pokedex.models.sync_runs import SyncRunRow
from tcg_pokedex.models.tracking import TrackedSet
from tcg_pokedex.views.ownership import Variant
from tcg_pokedex.views.sync import SOURCE
from tests.helpers import (
    OTHER_OWNER_ID,
    SEEDED_AT,
    FixtureRoutes,
    card_row,
    english,
    image,
    own,
    seed,
    set_row,
)

PT_001 = "https://assets.tcgdex.net/pt/sv/sv01/001"
EN_002 = "https://assets.tcgdex.net/en/swsh/swshp/SWSH032"
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


@pytest.fixture
def owned_client(client: TestClient, engine: Engine) -> TestClient:
    """The client, with more sv01 cards and a small sv02 set owned by the household
    and another owner.

    sv02 prints 2 cards and has a third beyond the printed count.
    """
    with engine.begin() as connection:
        connection.execute(
            insert(Set),
            {
                **set_row(
                    id="sv02",
                    name="Evoluções em Paldea",
                    release_date=date(2023, 6, 9),
                    official_count=2,
                    total_count=3,
                ),
                **PROVENANCE,
            },
        )
        connection.execute(
            insert(Card),
            [
                {**card_row(id=card_id, set_id=set_id, variants=variants), **PROVENANCE}
                for card_id, set_id, variants in [
                    ("sv01-004", "sv01", ["normal"]),
                    ("sv01-005", "sv01", ["holo"]),
                    ("sv01-006", "sv01", ["normal", "reverse"]),
                    ("sv01-199", "sv01", ["normal", "reverse"]),
                    ("sv02-001", "sv02", ["normal", "reverse"]),
                    ("sv02-002", "sv02", ["normal"]),
                    ("sv02-003", "sv02", ["holo"]),
                ]
            ],
        )
        connection.execute(insert(Owner).values(id=OTHER_OWNER_ID, name="Outra"))
    for card_id, variant, quantity in [
        ("sv01-002", "normal", 2),
        ("sv01-003", "reverse", 1),
        ("sv01-004", "normal", 1),
        ("sv01-005", "holo", 1),
        ("sv01-006", "normal", 1),
        ("sv01-006", "reverse", 1),
        ("sv01-199", "reverse", 2),
        ("sv02-001", "normal", 1),
        ("sv02-002", "normal", 1),
        ("sv02-003", "holo", 1),
    ]:
        own(engine, card_id, variant, quantity)
    own(engine, "sv01-001", "normal", 5, owner_id=OTHER_OWNER_ID)
    own(engine, "sv01-005", "holo", 3, owner_id=OTHER_OWNER_ID)
    return client


SV01_COMPLETION = {"owned": 6, "so_normal": 1, "total": 198, "complete": False}
SV02_COMPLETION = {"owned": 2, "so_normal": 1, "total": 2, "complete": True}


def none_of(total: int) -> dict[str, Any]:
    return {"owned": 0, "so_normal": 0, "total": total, "complete": False}


def card(card_id: str, owned: bool, missing: bool, **quantities: int) -> dict[str, Any]:
    return {
        "card_id": card_id,
        "variants": [
            {"variant": variant, "quantity": quantity}
            for variant, quantity in quantities.items()
        ],
        "owned": owned,
        "wanted_version_missing": missing,
    }


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
        runs = connection.execute(select(SyncRunRow.kind, SyncRunRow.status)).all()
    assert [tuple(run) for run in runs] == [("images", "succeeded")]


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_an_unknown_set_is_not_found(client: TestClient, method: str) -> None:
    assert client.request(method, "/api/sets/xy1/tracking").status_code == 404


def test_sets_are_listed_by_series_newest_first_with_the_owners_tracking(
    app: FastAPI, client: TestClient, engine: Engine
) -> None:
    with engine.begin() as connection:
        connection.execute(
            insert(Series).values(id="me", name="Megaevolução", **PROVENANCE)
        )
        connection.execute(
            insert(Set),
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
        connection.execute(insert(Owner).values(id=OTHER_OWNER_ID, name="Outra"))
        connection.execute(
            insert(TrackedSet),
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
            insert(SetArtwork).values(set_id="sv01", kind="logo", **PROVENANCE)
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
                    "completion": none_of(88),
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
                    "completion": none_of(198),
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
                    "completion": none_of(198),
                },
            ],
        },
    ]


def test_a_sets_ownership_lists_every_card_with_its_quantities_and_flags(
    owned_client: TestClient,
) -> None:
    read = owned_client.get("/api/sets/sv01/ownership")

    assert read.status_code == 200
    assert read.json() == {
        "set_id": "sv01",
        "completion": SV01_COMPLETION,
        "cards": [
            card("sv01-001", False, False, normal=0, reverse=0),
            card("sv01-002", True, True, normal=2, reverse=0),
            card("sv01-003", True, False, normal=0, reverse=1),
            card("sv01-004", True, False, normal=1),
            card("sv01-005", True, False, holo=1),
            card("sv01-006", True, False, normal=1, reverse=1),
            card("sv01-199", True, False, normal=0, reverse=2),
        ],
    }
    assert owned_client.get("/api/sets/xy1/ownership").status_code == 404


def test_completion_is_the_same_on_the_set_read_and_the_sets_list(
    owned_client: TestClient,
) -> None:
    expected = {"sv01": SV01_COMPLETION, "sv02": SV02_COMPLETION}

    listed = {
        entry["id"]: entry["completion"]
        for group in owned_client.get("/api/sets").json()
        for entry in group["sets"]
    }
    read = {
        set_id: owned_client.get(f"/api/sets/{set_id}/ownership").json()["completion"]
        for set_id in expected
    }

    assert listed == expected
    assert read == expected
