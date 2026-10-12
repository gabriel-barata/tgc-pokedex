"""`tcg sync all` and the one-sync-at-a-time lock, on real Postgres and recorded
TCGdex answers."""

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx2
import pytest
from pydantic import PostgresDsn
from sqlalchemy import Engine, insert, select

from tcg_pokedex.cli import run_sync
from tcg_pokedex.config import Settings
from tcg_pokedex.schemas import RunStatus, SyncKind
from tcg_pokedex.services.sync_runs import (
    INTERRUPTED,
    claim_syncs,
    join_syncs,
    release_syncs,
)
from tcg_pokedex.tables import sync_runs
from tests.helpers import (
    HAPPY,
    PIXEL,
    FixtureRoutes,
    Reply,
    SleepRecorder,
    failing,
)

START = datetime(2026, 10, 12, 4, 0, tzinfo=UTC)
SV01_ARTWORK: Mapping[str, Sequence[Reply]] = {
    "https://assets.tcgdex.net/pt/sv/sv01/logo.webp": (Reply(body=PIXEL),),
    "https://assets.tcgdex.net/univ/sv/sv01/symbol.webp": (Reply(body=PIXEL),),
}


def command(
    capsys: pytest.CaptureFixture[str],
    database_url: str,
    image_dir: Path,
    target: str,
    routes: Mapping[str, Sequence[Reply]],
) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    """Run `tcg sync <target>`; return its exit code, stdout runs and stderr log."""
    capsys.readouterr()
    exit_code = run_sync(
        target,
        Settings(database_url=PostgresDsn(database_url), image_dir=image_dir),
        now=lambda: START,
        transport=httpx2.MockTransport(FixtureRoutes(routes)),
        sleep=SleepRecorder(),
    )
    captured = capsys.readouterr()
    runs = [json.loads(line) for line in captured.out.splitlines()]
    log = [json.loads(line) for line in captured.err.splitlines()]
    return exit_code, runs, log


def stored_runs(engine: Engine) -> list[tuple[str, str]]:
    with engine.connect() as connection:
        rows = connection.execute(
            select(sync_runs.c.kind, sync_runs.c.status).order_by(
                sync_runs.c.started_at, sync_runs.c.kind
            )
        ).all()
    return [(row.kind, row.status) for row in rows]


def test_sync_all_runs_the_catalog_then_the_images(
    capsys: pytest.CaptureFixture[str],
    database_url: str,
    engine: Engine,
    tmp_path: Path,
) -> None:
    exit_code, runs, _ = command(
        capsys, database_url, tmp_path, "all", {**HAPPY, **SV01_ARTWORK}
    )

    assert exit_code == 0
    assert [(run["kind"], run["status"]) for run in runs] == [
        ("catalog", "succeeded"),
        ("images", "succeeded"),
    ]
    assert runs[1]["result"]["counts"]["artwork"]["downloaded"] == 2
    assert stored_runs(engine) == [("catalog", "succeeded"), ("images", "succeeded")]


def test_a_failed_catalog_run_skips_the_images(
    capsys: pytest.CaptureFixture[str],
    database_url: str,
    engine: Engine,
    tmp_path: Path,
) -> None:
    exit_code, runs, _ = command(
        capsys, database_url, tmp_path, "all", {"series": failing(500)}
    )

    assert exit_code == 2
    assert [(run["kind"], run["status"]) for run in runs] == [("catalog", "failed")]
    assert stored_runs(engine) == [("catalog", "failed")]


@pytest.mark.parametrize("holder", ["sync", "set download"])
def test_a_sync_is_rejected_while_another_one_runs(
    capsys: pytest.CaptureFixture[str],
    database_url: str,
    engine: Engine,
    tmp_path: Path,
    holder: str,
) -> None:
    held = claim_syncs(engine) if holder == "sync" else join_syncs(engine)
    assert held is not None
    try:
        assert claim_syncs(engine) is None
        exit_code, runs, log = command(capsys, database_url, tmp_path, "all", {})
    finally:
        release_syncs(held)

    assert exit_code == 2
    assert runs == []
    assert [line["event"] for line in log] == ["sync.run.error"]
    assert "another sync is running" in log[0]["error"]
    assert stored_runs(engine) == []
    claimed = claim_syncs(engine)
    assert claimed is not None
    release_syncs(claimed)


def test_claiming_closes_the_runs_a_dead_process_left_running(
    engine: Engine,
) -> None:
    with engine.begin() as connection:
        connection.execute(
            insert(sync_runs).values(
                id=uuid4(),
                kind=SyncKind.CATALOG,
                source="tcgdex",
                status=RunStatus.RUNNING,
                started_at=START,
            )
        )

    claimed = claim_syncs(engine)
    assert claimed is not None
    release_syncs(claimed)

    with engine.connect() as connection:
        row = connection.execute(select(sync_runs)).mappings().one()
    assert (row["status"], row["error"]) == ("failed", INTERRUPTED)
