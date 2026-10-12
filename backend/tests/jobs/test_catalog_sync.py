"""`tcg sync catalog` in-process, on real Postgres and recorded TCGdex answers."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
import pytest
from pydantic import PostgresDsn
from sqlalchemy import Engine, select

from tcg_pokedex.cli import run_sync
from tcg_pokedex.config import Settings
from tcg_pokedex.jobs.catalog_sync import (
    CardCounts,
    Failure,
    KindCounts,
    ResultBuilder,
    SetCounts,
    SyncResult,
)
from tcg_pokedex.models.catalog import Card, Set
from tcg_pokedex.models.sync_runs import get_run
from tcg_pokedex.views.sync import RunStatus, SyncRun
from tests.helpers import (
    FIXTURES,
    HAPPY,
    FixtureRoutes,
    Reply,
    SleepRecorder,
    failing,
    ok,
)

START = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
LATER = START + timedelta(hours=1)

WITH_FAILURES: Mapping[str, Sequence[Reply]] = {
    **HAPPY,
    "series/sv": ok("series/sv.with-failures.json"),
    "sets/sv02": failing(500),
    "cards/sv01-002": (Reply(404),),
}


@dataclass(frozen=True)
class Outcome:
    exit_code: int
    stdout: str
    log: list[dict[str, Any]]
    served: FixtureRoutes

    @property
    def run(self) -> SyncRun[SyncResult]:
        return SyncRun[SyncResult].model_validate_json(self.stdout)


def sync(
    capsys: pytest.CaptureFixture[str],
    database_url: str,
    routes: Mapping[str, Sequence[Reply]] = HAPPY,
    at: datetime = START,
) -> Outcome:
    capsys.readouterr()
    served = FixtureRoutes(routes)
    exit_code = run_sync(
        "catalog",
        Settings(database_url=PostgresDsn(database_url)),
        now=lambda: at,
        transport=httpx2.MockTransport(served),
        sleep=SleepRecorder(),
    )
    captured = capsys.readouterr()
    log = [json.loads(line) for line in captured.err.splitlines()]
    return Outcome(exit_code, captured.out, log, served)


def test_a_first_run_stores_the_physical_catalog_and_exits_0(
    capsys: pytest.CaptureFixture[str], database_url: str, engine: Engine
) -> None:
    outcome = sync(capsys, database_url)

    assert outcome.exit_code == 0
    run = outcome.run
    assert run.status is RunStatus.SUCCEEDED
    assert run.result is not None
    assert run.result.counts.series == KindCounts(
        fetched=1, created=1, updated=0, unchanged=0
    )
    assert run.result.counts.cards == CardCounts(
        fetched=2, created=2, updated=0, unchanged=0, failed=0
    )
    assert not [url for url in outcome.served.urls() if "tcgp" in url[-5:]]
    assert [line["event"] for line in outcome.log] == [
        "sync.run.started",
        "sync.run.finished",
    ]
    with engine.connect() as connection:
        stored = connection.execute(select(Card)).mappings().all()
    assert {card["id"]: card["variants"] for card in stored} == {
        "sv01-001": ["normal", "reverse"],
        "sv01-002": ["normal", "reverse"],
    }
    assert {(card["source"], card["fetched_at"]) for card in stored} == {
        ("tcgdex", START)
    }
    assert get_run(engine, run.id, SyncResult) == run


def test_a_second_run_updates_changed_rows_only(
    capsys: pytest.CaptureFixture[str], database_url: str, engine: Engine
) -> None:
    sync(capsys, database_url)
    renamed = json.loads((FIXTURES / "tcgdex/cards/sv01-001.json").read_bytes())
    renamed["name"] = "Pineco Renomeado"

    outcome = sync(
        capsys,
        database_url,
        {**HAPPY, "cards/sv01-001": (Reply(body=json.dumps(renamed).encode()),)},
        at=LATER,
    )

    assert outcome.run.result is not None
    assert outcome.run.result.counts.cards == CardCounts(
        fetched=2, created=0, updated=1, unchanged=1, failed=0
    )
    assert outcome.run.result.counts.sets == SetCounts(
        fetched=1, created=0, updated=0, unchanged=1, skipped=0, failed=0
    )
    with engine.connect() as connection:
        names = {
            row.id: row.name for row in connection.execute(select(Card.id, Card.name))
        }
    assert names == {"sv01-001": "Pineco Renomeado", "sv01-002": "Heracross"}


def test_failures_make_a_partial_run_that_exits_1(
    capsys: pytest.CaptureFixture[str], database_url: str, engine: Engine
) -> None:
    outcome = sync(capsys, database_url, WITH_FAILURES)

    assert outcome.exit_code == 1
    assert outcome.run.status is RunStatus.PARTIAL
    assert outcome.run.result is not None
    assert outcome.run.result.failures == (
        Failure(kind="card", provider_id="sv01-002", reason="HTTP 404"),
        Failure(kind="set", provider_id="sv02", reason="HTTP 500 after 3 attempts"),
    )
    assert [line["event"] for line in outcome.log].count("sync.failure") == 2
    with engine.connect() as connection:
        assert list(connection.scalars(select(Card.id))) == ["sv01-001"]


def test_an_unavailable_index_fails_the_run_before_any_write(
    capsys: pytest.CaptureFixture[str], database_url: str, engine: Engine
) -> None:
    outcome = sync(capsys, database_url, {"series": failing(500)})

    assert outcome.exit_code == 2
    assert outcome.run.status is RunStatus.FAILED
    assert outcome.run.error == "HTTP 500 after 3 attempts"
    with engine.connect() as connection:
        assert list(connection.scalars(select(Set.id))) == []


def test_an_unreachable_store_exits_2_and_logs_the_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome = sync(capsys, "postgresql+psycopg://x:x@127.0.0.1:1/x")

    assert outcome.exit_code == 2
    assert outcome.stdout == ""
    assert [line["event"] for line in outcome.log] == ["sync.run.error"]


def test_a_result_keeps_the_first_100_failures_but_counts_them_all() -> None:
    builder = ResultBuilder()
    assert builder.status() is RunStatus.SUCCEEDED

    for n in range(105):
        builder.fail(Failure(kind="card", provider_id=f"c{n}", reason="HTTP 404"))
    result = builder.build()

    assert builder.status() is RunStatus.PARTIAL
    assert [f.provider_id for f in result.failures] == [f"c{n}" for n in range(100)]
    assert result.counts.cards.failed == 105
    builder.abort()
    assert builder.status() is RunStatus.FAILED
