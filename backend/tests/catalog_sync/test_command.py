"""End to end: `tcg sync catalog` in-process on Postgres and the recorded fixtures."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx2
import pytest
from pydantic import PostgresDsn
from sqlalchemy import select

from tcg_pokedex.catalog_sync.adapters import tables
from tcg_pokedex.catalog_sync.command import run_catalog_sync
from tcg_pokedex.catalog_sync.domain import SyncResult
from tcg_pokedex.clock.fake import FakeClock
from tcg_pokedex.config import Settings
from tcg_pokedex.database import create_database_engine
from tcg_pokedex.migrations import upgrade_to_head
from tcg_pokedex.sync_runs.adapters.postgres import PostgresSyncRunRepository
from tcg_pokedex.sync_runs.domain import RunStatus, SyncRun
from tests.tcgdex.fixtures import (
    HAPPY,
    INDEX_DOWN,
    WITH_FAILURES,
    FixtureRoutes,
    Reply,
    SleepRecorder,
)

START = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Outcome:
    exit_code: int
    stdout: str
    log: list[dict[str, Any]]

    @property
    def run(self) -> SyncRun[SyncResult]:
        return SyncRun[SyncResult].model_validate_json(self.stdout)


@pytest.fixture
def database_url(empty_database_url: str) -> str:
    upgrade_to_head(empty_database_url)
    return empty_database_url


def sync(
    capsys: pytest.CaptureFixture[str],
    database_url: str,
    routes: Mapping[str, Sequence[Reply]] = HAPPY,
) -> Outcome:
    capsys.readouterr()
    exit_code = run_catalog_sync(
        Settings(database_url=PostgresDsn(database_url)),
        FakeClock(START),
        transport=httpx2.MockTransport(FixtureRoutes(routes)),
        sleep=SleepRecorder(),
    )
    captured = capsys.readouterr()
    log = [json.loads(line) for line in captured.err.splitlines()]
    return Outcome(exit_code, captured.out, log)


def test_a_first_run_stores_the_catalog_prints_the_run_and_exits_0(
    capsys: pytest.CaptureFixture[str], database_url: str
) -> None:
    outcome = sync(capsys, database_url)

    assert outcome.exit_code == 0
    run = outcome.run
    assert run.status is RunStatus.SUCCEEDED
    assert [line["event"] for line in outcome.log] == [
        "sync.run.started",
        "sync.run.finished",
    ]
    engine = create_database_engine(database_url)
    try:
        with engine.connect() as connection:
            cards = connection.execute(select(tables.cards)).mappings().all()
        stored_run = PostgresSyncRunRepository(engine).get_run(run.id, SyncResult)
    finally:
        engine.dispose()
    assert {card["id"]: card["variants"] for card in cards} == {
        "sv01-001": ["normal", "reverse"],
        "sv01-002": ["normal", "reverse"],
    }
    assert {(card["source"], card["fetched_at"]) for card in cards} == {
        ("tcgdex", START)
    }
    assert stored_run == run


def test_failures_make_a_partial_run_that_exits_1(
    capsys: pytest.CaptureFixture[str], database_url: str
) -> None:
    outcome = sync(capsys, database_url, WITH_FAILURES)

    assert outcome.exit_code == 1
    assert outcome.run.status is RunStatus.PARTIAL
    assert outcome.run.result is not None
    assert [f.provider_id for f in outcome.run.result.failures] == ["sv01-002", "sv02"]


def test_an_unavailable_index_exits_2(
    capsys: pytest.CaptureFixture[str], database_url: str
) -> None:
    outcome = sync(capsys, database_url, INDEX_DOWN)

    assert outcome.exit_code == 2
    assert outcome.run.status is RunStatus.FAILED


def test_an_unreachable_store_exits_2_and_logs_the_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome = sync(capsys, "postgresql+psycopg://x:x@127.0.0.1:1/x")

    assert outcome.exit_code == 2
    assert outcome.stdout == ""
    assert [line["event"] for line in outcome.log] == ["sync.run.error"]
