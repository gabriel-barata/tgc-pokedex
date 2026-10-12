"""Sync routes on `create_app`, real Postgres and recorded TCGdex answers."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient
from pydantic import PostgresDsn
from sqlalchemy import Engine, insert

from tcg_pokedex.app import create_app
from tcg_pokedex.config import Settings
from tcg_pokedex.schemas import RunStatus, SyncKind
from tcg_pokedex.services.sync_runs import INTERRUPTED, claim_syncs, release_syncs
from tcg_pokedex.tables import sync_runs
from tests.helpers import HAPPY, PIXEL, FixtureRoutes, Reply, ok

START = datetime(2026, 10, 12, 4, 0, tzinfo=UTC)


@pytest.fixture
def client(database_url: str, tmp_path: Path) -> Iterator[TestClient]:
    served = FixtureRoutes(
        {
            **HAPPY,
            "series/sv": ok("series/sv.with-failures.json"),
            "sets/sv02": (Reply(404),),
            "cards/sv01-002": (Reply(404),),
            "https://assets.tcgdex.net/pt/sv/sv01/logo.webp": (Reply(body=PIXEL),),
            "https://assets.tcgdex.net/univ/sv/sv01/symbol.webp": (Reply(body=PIXEL),),
        }
    )
    settings = Settings(
        database_url=PostgresDsn(database_url), image_dir=tmp_path / "images"
    )
    app = create_app(settings, tcgdex_transport=httpx2.MockTransport(served))
    with TestClient(app) as test_client:
        yield test_client


def store_running_runs(engine: Engine, count: int) -> None:
    """Runs left running by a dead process, one minute apart, oldest first."""
    with engine.begin() as connection:
        connection.execute(
            insert(sync_runs),
            [
                {
                    "id": uuid4(),
                    "kind": SyncKind.CATALOG,
                    "source": "tcgdex",
                    "status": RunStatus.RUNNING,
                    "started_at": START + timedelta(minutes=minute),
                }
                for minute in range(count)
            ],
        )


def test_sync_now_runs_the_catalog_then_the_images_and_lists_them(
    client: TestClient,
) -> None:
    started = client.post("/api/sync")

    assert started.status_code == 202
    assert started.json()["running"] is True
    status = client.get("/api/sync").json()
    assert status["running"] is False
    runs = status["runs"]
    assert [(run["kind"], run["status"]) for run in runs] == [
        ("images", "succeeded"),
        ("catalog", "partial"),
    ]
    images, catalog = runs
    assert images["counts"] == {"fetched": 2, "updated": 2, "failed": 0}
    assert images["failures"] == []
    assert catalog["counts"] == {"fetched": 3, "updated": 3, "failed": 2}
    assert catalog["failures"] == [
        {"kind": "card", "provider_id": "sv01-002", "reason": "HTTP 404"},
        {"kind": "set", "provider_id": "sv02", "reason": "HTTP 404"},
    ]
    assert catalog["error"] is None
    assert catalog["duration_ms"] >= 0
    assert catalog["finished_at"] is not None


def test_sync_now_is_rejected_while_another_sync_runs(
    client: TestClient, engine: Engine
) -> None:
    lock = claim_syncs(engine)
    assert lock is not None
    try:
        status = client.get("/api/sync").json()
        rejected = client.post("/api/sync")
    finally:
        release_syncs(lock)

    assert status == {"running": True, "runs": []}
    assert rejected.status_code == 409
    assert client.get("/api/sync").json() == {"running": False, "runs": []}


def test_the_20_latest_runs_are_listed_and_dead_ones_show_as_interrupted(
    client: TestClient, engine: Engine
) -> None:
    store_running_runs(engine, 21)

    runs = client.get("/api/sync").json()["runs"]

    assert len(runs) == 20
    assert runs[0]["started_at"] == "2026-10-12T04:20:00Z"
    assert runs[-1]["started_at"] == "2026-10-12T04:01:00Z"
    assert {(run["status"], run["error"]) for run in runs} == {("failed", INTERRUPTED)}
    assert all(run["counts"] is None and run["failures"] == [] for run in runs)
