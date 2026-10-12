"""End to end: `tcg sync images` in-process on Postgres, a temp image directory and
recorded TCGdex answers. sv01 is tracked; its second card fails on the first run.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2
import pytest
from pydantic import PostgresDsn

from tcg_pokedex.catalog_sync.adapters.postgres import PostgresCatalogRepository
from tcg_pokedex.catalog_sync.domain import SetBatch
from tcg_pokedex.clock.fake import FakeClock
from tcg_pokedex.config import Settings
from tcg_pokedex.database import create_database_engine
from tcg_pokedex.image_cache.adapters.postgres import PostgresImageCacheRepository
from tcg_pokedex.image_cache.command import run_image_sync
from tcg_pokedex.image_cache.domain import ImageSyncResult
from tcg_pokedex.migrations import upgrade_to_head
from tcg_pokedex.owners.domain import HOUSEHOLD_OWNER_ID
from tcg_pokedex.sync_runs.adapters.postgres import PostgresSyncRunRepository
from tcg_pokedex.sync_runs.domain import RunStatus, SyncRun
from tests.catalog_sync.builders import make_card, make_series, make_set
from tests.image_cache.assets import PIXEL, image
from tests.tcgdex.fixtures import FixtureRoutes, Reply, SleepRecorder, failing

START = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
PT_001 = "https://assets.tcgdex.net/pt/sv/sv01/001"
PT_002 = "https://assets.tcgdex.net/pt/sv/sv01/002"
SV01 = make_set(symbol_url=None)

FIRST_RUN: Mapping[str, Sequence[Reply]] = {
    **image(PT_001),
    f"{PT_002}/low.webp": failing(500),
    f"{SV01.logo_url}.webp": (Reply(body=PIXEL),),
}


@dataclass(frozen=True)
class Outcome:
    exit_code: int
    stdout: str
    log: list[dict[str, Any]]

    @property
    def run(self) -> SyncRun[ImageSyncResult]:
        return SyncRun[ImageSyncResult].model_validate_json(self.stdout)


@pytest.fixture
def database_url(empty_database_url: str) -> str:
    upgrade_to_head(empty_database_url)
    engine = create_database_engine(empty_database_url)
    cards = (make_card(image_url=PT_001), make_card(id="sv01-002", image_url=PT_002))
    try:
        PostgresCatalogRepository(engine).save_set(
            SetBatch(series=make_series(), card_set=SV01, cards=cards), START
        )
        PostgresImageCacheRepository(engine).track(HOUSEHOLD_OWNER_ID, "sv01", START)
    finally:
        engine.dispose()
    return empty_database_url


def sync(
    capsys: pytest.CaptureFixture[str],
    database_url: str,
    image_dir: Path,
    routes: Mapping[str, Sequence[Reply]],
) -> Outcome:
    capsys.readouterr()
    exit_code = run_image_sync(
        Settings(database_url=PostgresDsn(database_url), image_dir=image_dir),
        FakeClock(START),
        transport=httpx2.MockTransport(FixtureRoutes(routes)),
        sleep=SleepRecorder(),
    )
    captured = capsys.readouterr()
    log = [json.loads(line) for line in captured.err.splitlines()]
    return Outcome(exit_code, captured.out, log)


def stored_run(database_url: str, outcome: Outcome) -> SyncRun[ImageSyncResult] | None:
    engine = create_database_engine(database_url)
    try:
        return PostgresSyncRunRepository(engine).get_run(
            outcome.run.id, ImageSyncResult
        )
    finally:
        engine.dispose()


def test_a_failed_card_makes_a_partial_run_that_the_next_run_completes(
    capsys: pytest.CaptureFixture[str], database_url: str, tmp_path: Path
) -> None:
    images = tmp_path / "images"

    first = sync(capsys, database_url, images, FIRST_RUN)
    second = sync(capsys, database_url, images, image(PT_002))

    assert first.exit_code == 1
    assert first.run.status is RunStatus.PARTIAL
    assert first.run.result is not None
    assert first.run.result.set_id is None
    assert first.run.result.counts.artwork.downloaded == 1
    assert stored_run(database_url, first) == first.run
    assert "sync.failure" in [line["event"] for line in first.log]
    assert (images / "cards" / "sv01-001" / "large.webp").read_bytes() == PIXEL
    assert (images / "sets" / "sv01" / "logo.webp").read_bytes() == PIXEL
    assert second.exit_code == 0
    assert second.run.result is not None
    assert second.run.result.counts.cards.downloaded == 1
    assert (images / "cards" / "sv01-002" / "small.webp").is_file()


def test_an_unwritable_image_directory_fails_the_run(
    capsys: pytest.CaptureFixture[str], database_url: str, tmp_path: Path
) -> None:
    read_only = tmp_path / "read-only"
    read_only.mkdir(mode=0o500)

    outcome = sync(capsys, database_url, read_only / "images", {})

    assert outcome.exit_code == 2
    assert outcome.run.status is RunStatus.FAILED
