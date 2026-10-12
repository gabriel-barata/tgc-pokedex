"""End to end: `tcg sync catalog` in-process on Postgres and the recorded fixtures."""

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
import pytest
from pydantic import PostgresDsn
from sqlalchemy import Engine, select

from tcg_pokedex.catalog_sync.adapters import tables
from tcg_pokedex.catalog_sync.adapters.postgres import PostgresCatalogRepository
from tcg_pokedex.catalog_sync.command import run_catalog_sync
from tcg_pokedex.catalog_sync.domain import (
    CardCounts,
    Failure,
    KindCounts,
    RunStatus,
    SetCounts,
    SyncRun,
)
from tcg_pokedex.clock.fake import FakeClock
from tcg_pokedex.config import Settings
from tcg_pokedex.database import create_database_engine
from tcg_pokedex.migrations import upgrade_to_head
from tests.catalog_sync.tcgdex_fixtures import (
    HAPPY,
    HAPPY_CARD_IDS,
    INDEX_DOWN,
    WITH_FAILURES,
    FixtureRoutes,
    Raise,
    Reply,
    SleepRecorder,
)

START = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Outcome:
    exit_code: int
    stdout: str
    log: list[dict[str, Any]]
    routes: FixtureRoutes

    @property
    def run(self) -> SyncRun:
        return SyncRun.model_validate_json(self.stdout)


@pytest.fixture
def database_url(empty_database_url: str) -> str:
    upgrade_to_head(empty_database_url)
    return empty_database_url


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    engine = create_database_engine(database_url)
    yield engine
    engine.dispose()


def sync(
    capsys: pytest.CaptureFixture[str],
    database_url: str,
    table: Mapping[str, Sequence[Reply | Raise]] = HAPPY,
    clock: FakeClock | None = None,
) -> Outcome:
    routes = FixtureRoutes(table)
    capsys.readouterr()
    exit_code = run_catalog_sync(
        Settings(database_url=PostgresDsn(database_url)),
        clock or FakeClock(START),
        transport=httpx2.MockTransport(routes),
        sleep=SleepRecorder(),
    )
    captured = capsys.readouterr()
    log = [json.loads(line) for line in captured.err.splitlines()]
    return Outcome(exit_code, captured.out, log, routes)


def rows(engine: Engine, table: Any) -> dict[str, dict[str, Any]]:
    with engine.connect() as connection:
        result = connection.execute(select(table)).mappings().all()
    return {row["id"]: dict(row) for row in result}


def test_a_first_run_populates_the_catalog_and_exits_0(
    capsys: pytest.CaptureFixture[str], database_url: str
) -> None:
    outcome = sync(capsys, database_url)

    assert outcome.exit_code == 0
    assert len(outcome.stdout.strip().splitlines()) == 1
    run = outcome.run
    assert run.status is RunStatus.SUCCEEDED
    assert run.result is not None
    assert run.result.counts.series == KindCounts(
        fetched=3, created=3, updated=0, unchanged=0
    )
    assert run.result.counts.sets == SetCounts(
        fetched=4, created=4, updated=0, unchanged=0, skipped=1, failed=0
    )
    assert run.result.counts.cards == CardCounts(
        fetched=14, created=14, updated=0, unchanged=0, failed=0
    )


def test_the_stored_rows_match_the_corpus(
    capsys: pytest.CaptureFixture[str], database_url: str, engine: Engine
) -> None:
    sync(capsys, database_url)

    series = rows(engine, tables.series)
    sets = rows(engine, tables.sets)
    cards = rows(engine, tables.cards)
    assert set(series) == {"xy", "swsh", "sv"}
    assert set(sets) == {"xy0", "swshp", "swsh4.5", "sv01"}
    assert set(cards) == set(HAPPY_CARD_IDS)
    assert cards["sv01-001"]["variants"] == ["normal", "reverse"]
    assert cards["sv01-001"]["set_id"] == "sv01"
    assert cards["swshp-SWSH158"]["collector_number"] == "SWSH158"
    assert cards["swshp-SWSH158"]["variants"] == ["holo"]
    assert cards["swshp-SWSH032"]["image_url"] is None
    assert cards["xy0-1"]["rarity"] is None
    assert cards["xy0-1"]["image_url"] == "https://assets.tcgdex.net/pt/xy/xy0/1"
    assert sets["swsh4.5"]["name"] == "Destinos Brilhantes"
    assert sets["xy0"]["logo_url"] is None
    assert sets["sv01"]["series_id"] == "sv"
    assert series["swsh"]["name"] == "Espada e Escudo"
    for table in (series, sets, cards):
        for row in table.values():
            assert row["source"] == "tcgdex"
            assert row["fetched_at"] == START


def test_the_run_record_matches_the_printed_run(
    capsys: pytest.CaptureFixture[str], database_url: str, engine: Engine
) -> None:
    outcome = sync(capsys, database_url)

    stored = PostgresCatalogRepository(engine).get_run(outcome.run.id)

    assert stored == outcome.run
    assert outcome.run.finished_at == START
    assert outcome.run.duration_ms == 0


def test_no_pocket_endpoint_is_requested(
    capsys: pytest.CaptureFixture[str], database_url: str
) -> None:
    outcome = sync(capsys, database_url)

    assert "series/sv" in outcome.routes.paths
    assert not [path for path in outcome.routes.paths if "tcgp" in path or "A1" in path]


def test_the_run_start_and_end_are_logged_as_json_lines(
    capsys: pytest.CaptureFixture[str], database_url: str
) -> None:
    outcome = sync(capsys, database_url)

    run = outcome.run
    assert [line["event"] for line in outcome.log] == [
        "sync.run.started",
        "sync.run.finished",
    ]
    started, finished = outcome.log
    assert started["level"] == "INFO"
    assert datetime.fromisoformat(started["time"]).tzinfo is not None
    assert started["run_id"] == str(run.id)
    assert started["kind"] == "catalog"
    assert finished["status"] == "succeeded"
    assert finished["duration_ms"] == 0
    assert run.result is not None
    assert finished["counts"] == run.result.counts.model_dump(mode="json")
    assert finished["error"] is None


def without_fetch_time(table: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        row_id: {
            column: value for column, value in row.items() if column != "fetched_at"
        }
        for row_id, row in table.items()
    }


def test_a_second_run_changes_nothing_but_the_fetch_time(
    capsys: pytest.CaptureFixture[str], database_url: str, engine: Engine
) -> None:
    clock = FakeClock(START)
    sync(capsys, database_url, clock=clock)
    first = [
        rows(engine, table) for table in (tables.series, tables.sets, tables.cards)
    ]
    clock.advance(timedelta(hours=1))

    outcome = sync(capsys, database_url, clock=clock)

    assert outcome.exit_code == 0
    run = outcome.run
    assert run.result is not None
    counts = run.result.counts
    for kind in (counts.series, counts.sets, counts.cards):
        assert (kind.created, kind.updated) == (0, 0)
        assert kind.unchanged == kind.fetched
    assert (counts.series.fetched, counts.sets.fetched, counts.cards.fetched) == (
        3,
        4,
        14,
    )
    second = [
        rows(engine, table) for table in (tables.series, tables.sets, tables.cards)
    ]
    assert [without_fetch_time(table) for table in second] == [
        without_fetch_time(table) for table in first
    ]
    for table in second:
        for row in table.values():
            assert row["fetched_at"] == START + timedelta(hours=1)
    with engine.connect() as connection:
        runs = connection.execute(select(tables.sync_runs)).mappings().all()
    assert len(runs) == 2
    assert all(row["finished_at"] is not None for row in runs)


def test_failures_make_a_partial_run_that_exits_1(
    capsys: pytest.CaptureFixture[str], database_url: str, engine: Engine
) -> None:
    outcome = sync(capsys, database_url, WITH_FAILURES)

    assert outcome.exit_code == 1
    run = outcome.run
    assert run.status is RunStatus.PARTIAL
    assert run.error is None
    assert run.result is not None
    assert run.result.failures == (
        Failure(kind="set", provider_id="sv02", reason="HTTP 500 after 3 attempts"),
        Failure(
            kind="card",
            provider_id="fail01-001",
            reason="invalid payload: name: Field required",
        ),
        Failure(kind="card", provider_id="fail01-002", reason="no variants"),
        Failure(kind="card", provider_id="fail01-003", reason="HTTP 404"),
    )
    assert run.result.counts.sets == SetCounts(
        fetched=5, created=5, updated=0, unchanged=0, skipped=1, failed=1
    )
    assert run.result.counts.cards == CardCounts(
        fetched=15, created=15, updated=0, unchanged=0, failed=3
    )
    assert PostgresCatalogRepository(engine).get_run(run.id) == run
    cards = rows(engine, tables.cards)
    assert set(cards) == {*HAPPY_CARD_IDS, "fail01-004"}
    assert set(rows(engine, tables.sets)) == {
        "xy0",
        "swshp",
        "swsh4.5",
        "sv01",
        "fail01",
    }
    failure_lines = [line for line in outcome.log if line["event"] == "sync.failure"]
    assert len(failure_lines) == 4
    assert {line["provider_id"] for line in failure_lines} == {
        "sv02",
        "fail01-001",
        "fail01-002",
        "fail01-003",
    }


def test_an_unavailable_index_fails_the_run_writes_nothing_and_exits_2(
    capsys: pytest.CaptureFixture[str], database_url: str, engine: Engine
) -> None:
    outcome = sync(capsys, database_url, INDEX_DOWN)

    assert outcome.exit_code == 2
    run = outcome.run
    assert run.status is RunStatus.FAILED
    assert run.error == "HTTP 500 after 3 attempts"
    assert run.result is not None
    assert run.result.counts.cards == CardCounts(
        fetched=0, created=0, updated=0, unchanged=0, failed=0
    )
    for table in (tables.series, tables.sets, tables.cards):
        assert rows(engine, table) == {}
    assert PostgresCatalogRepository(engine).get_run(run.id) == run
    assert outcome.routes.paths == ["series"] * 3


def test_an_unreachable_store_exits_2_without_contacting_the_provider(
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome = sync(capsys, "postgresql+psycopg://x:x@127.0.0.1:1/x")

    assert outcome.exit_code == 2
    assert outcome.stdout == ""
    assert [line["event"] for line in outcome.log] == ["sync.run.error"]
    assert outcome.log[0]["error"]
    assert outcome.routes.requests == []


def test_a_run_record_that_cannot_be_closed_exits_2(
    capsys: pytest.CaptureFixture[str],
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_finish_run(_self: PostgresCatalogRepository, _run: SyncRun) -> None:
        raise RuntimeError("store went away")

    monkeypatch.setattr(PostgresCatalogRepository, "finish_run", broken_finish_run)

    outcome = sync(capsys, database_url)

    assert outcome.exit_code == 2
    assert outcome.stdout == ""
    assert outcome.log[-1]["event"] == "sync.run.error"
    assert outcome.log[-1]["error"] == "store went away"
