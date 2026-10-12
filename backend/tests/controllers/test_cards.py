"""Ownership write routes on `create_app` and real Postgres."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import PostgresDsn
from sqlalchemy import Engine, insert, select

from tcg_pokedex.app import create_app
from tcg_pokedex.config import Settings
from tcg_pokedex.models.owner import HOUSEHOLD_OWNER_ID, Owner
from tcg_pokedex.models.ownership import Ownership
from tests.helpers import (
    OTHER_OWNER_ID,
    card_row,
    own,
    seed,
    set_row,
)

CARD = "/api/cards/sv01-001/ownership"
OTHERS = (OTHER_OWNER_ID, "sv01-001", "normal", 5)


@pytest.fixture
def app(database_url: str, engine: Engine, tmp_path: Path) -> FastAPI:
    seed(
        engine,
        [set_row()],
        [card_row(), card_row(id="sv01-002", variants=["normal"])],
    )
    with engine.begin() as connection:
        connection.execute(insert(Owner).values(id=OTHER_OWNER_ID, name="Outra"))
    own(engine, "sv01-001", "normal", 5, owner_id=OTHER_OWNER_ID)
    settings = Settings(
        database_url=PostgresDsn(database_url), image_dir=tmp_path / "images"
    )
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def stored(engine: Engine) -> set[tuple[UUID, str, str, int]]:
    with engine.connect() as connection:
        rows = connection.execute(
            select(
                Ownership.owner_id,
                Ownership.card_id,
                Ownership.variant,
                Ownership.quantity,
            )
        ).all()
    return {(row.owner_id, row.card_id, row.variant, row.quantity) for row in rows}


def mine(card_id: str, variant: str, quantity: int) -> tuple[UUID, str, str, int]:
    return (HOUSEHOLD_OWNER_ID, card_id, variant, quantity)


def card(normal: int, reverse: int, owned: bool, missing: bool) -> dict[str, Any]:
    return {
        "card_id": "sv01-001",
        "variants": [
            {"variant": "normal", "quantity": normal},
            {"variant": "reverse", "quantity": reverse},
        ],
        "owned": owned,
        "wanted_version_missing": missing,
    }


def test_incrementing_a_variant_of_an_untracked_set_records_one_copy(
    client: TestClient, engine: Engine
) -> None:
    incremented = client.post(f"{CARD}/reverse/increment")

    assert incremented.status_code == 200
    assert incremented.json() == card(0, 1, owned=True, missing=False)
    assert stored(engine) == {OTHERS, mine("sv01-001", "reverse", 1)}


def test_decrementing_removes_one_copy_and_stops_at_zero(
    client: TestClient, engine: Engine
) -> None:
    own(engine, "sv01-001", "normal", 2)

    decremented = client.post(f"{CARD}/normal/decrement")
    at_zero = client.post(f"{CARD}/reverse/decrement")

    assert decremented.status_code == 200
    assert decremented.json() == card(1, 0, owned=True, missing=True)
    assert at_zero.status_code == 200
    assert at_zero.json() == card(1, 0, owned=True, missing=True)
    assert stored(engine) == {OTHERS, mine("sv01-001", "normal", 1)}


@pytest.mark.parametrize("quantity", [0, 999])
def test_setting_a_quantity_stores_exactly_that_value(
    client: TestClient, engine: Engine, quantity: int
) -> None:
    own(engine, "sv01-001", "normal", 3)

    updated = client.put(f"{CARD}/normal", json={"quantity": quantity})

    assert updated.status_code == 200
    assert updated.json() == card(quantity, 0, owned=quantity > 0, missing=quantity > 0)
    assert stored(engine) == {OTHERS, mine("sv01-001", "normal", quantity)}


@pytest.mark.parametrize(
    ("method", "path", "body", "status"),
    [
        ("PUT", f"{CARD}/normal", {"quantity": -1}, 422),
        ("PUT", f"{CARD}/normal", {"quantity": 1000}, 422),
        ("POST", f"{CARD}/normal/increment", None, 409),
        ("POST", f"{CARD}/holo/increment", None, 422),
        ("PUT", f"{CARD}/holo", {"quantity": 1}, 422),
        ("POST", f"{CARD}/shiny/increment", None, 422),
        ("POST", "/api/cards/nope/ownership/normal/increment", None, 404),
    ],
)
def test_rejected_changes_leave_every_quantity_unchanged(
    client: TestClient,
    engine: Engine,
    *,
    method: str,
    path: str,
    body: dict[str, int] | None,
    status: int,
) -> None:
    own(engine, "sv01-001", "normal", 999)

    rejected = client.request(method, path, json=body)

    assert rejected.status_code == status
    assert stored(engine) == {OTHERS, mine("sv01-001", "normal", 999)}
