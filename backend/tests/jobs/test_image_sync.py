"""Image syncs on real Postgres, a temp image directory and recorded TCGdex answers.

sv01 holds a pt card (001), an English-only card (002), a card with no image (003)
and a card whose pt image fails (004).
"""

import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx2
import pytest
from pydantic import PostgresDsn
from sqlalchemy import Engine, insert, select, update

from tcg_pokedex.cli import run_sync
from tcg_pokedex.config import Settings
from tcg_pokedex.jobs.image_sync import (
    CardPlan,
    CardToResolve,
    ImageCounts,
    ImageFailure,
    ImageSyncResult,
    Language,
    card_path,
    plan_card,
    sync_images,
    write_file,
)
from tcg_pokedex.models.catalog import Card
from tcg_pokedex.models.images import CardImage
from tcg_pokedex.models.owner import HOUSEHOLD_OWNER_ID
from tcg_pokedex.models.sync_runs import get_run
from tcg_pokedex.models.tracking import TrackedSet
from tcg_pokedex.views.images import CardSize
from tcg_pokedex.views.sync import RunStatus, SyncRun
from tests.helpers import (
    PIXEL,
    FixtureRoutes,
    Reply,
    SleepRecorder,
    card_row,
    english,
    failing,
    image,
    seed,
    set_row,
    tcgdex,
)

START = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
LATER = START + timedelta(hours=1)
PT = "https://assets.tcgdex.net/pt/sv/sv01"
EN_002 = "https://assets.tcgdex.net/en/swsh/swshp/SWSH032"
SERVER_ERROR = "HTTP 500 after 3 attempts"

FIRST_RUN: Mapping[str, Sequence[Reply]] = {
    **image(f"{PT}/001"),
    **english("sv01-002", "swshp-SWSH032.json"),
    **image(EN_002),
    **english("sv01-003"),
    f"{PT}/004/low.webp": failing(500),
}


@pytest.fixture
def image_dir(tmp_path: Path) -> Path:
    return tmp_path / "images"


@pytest.fixture
def seeded(engine: Engine) -> Engine:
    seed(
        engine,
        [set_row()],
        [
            card_row(),
            card_row(id="sv01-002", image_url=None),
            card_row(id="sv01-003", image_url=None),
            card_row(id="sv01-004", image_url=f"{PT}/004"),
        ],
    )
    return engine


def sync(
    engine: Engine,
    image_dir: Path,
    routes: Mapping[str, Sequence[Reply]],
    at: datetime = START,
) -> tuple[SyncRun[ImageSyncResult], FixtureRoutes]:
    served = FixtureRoutes(routes)
    with tcgdex(served) as client:
        run = sync_images(engine, client, image_dir, set_id="sv01", now=lambda: at)
    return run, served


def stored_images(engine: Engine) -> dict[str, tuple[str | None, datetime]]:
    with engine.connect() as connection:
        rows = connection.execute(select(CardImage))
        return {row.card_id: (row.language, row.fetched_at) for row in rows}


def test_a_set_run_caches_pt_then_english_and_records_the_rest(
    seeded: Engine, image_dir: Path
) -> None:
    run, served = sync(seeded, image_dir, FIRST_RUN)

    assert run.status is RunStatus.PARTIAL
    assert run.result is not None
    assert run.result.set_id == "sv01"
    assert run.result.counts.cards == ImageCounts(
        downloaded=2, cached=0, unavailable=1, failed=1
    )
    assert run.result.failures == (
        ImageFailure(kind="card", provider_id="sv01-004", reason=SERVER_ERROR),
    )
    assert stored_images(seeded) == {
        "sv01-001": ("pt", START),
        "sv01-002": ("en", START),
        "sv01-003": (None, START),
    }
    assert card_path(image_dir, "sv01-002", CardSize.LARGE) is not None
    assert not [url for url in served.urls() if "logo" in url]
    assert get_run(seeded, run.id, ImageSyncResult) == run


def test_a_second_run_skips_pt_images_upgrades_english_and_retries_failures(
    seeded: Engine, image_dir: Path
) -> None:
    sync(seeded, image_dir, FIRST_RUN)
    with seeded.begin() as connection:
        connection.execute(
            update(Card).where(Card.id == "sv01-002").values(image_url=f"{PT}/002")
        )

    run, served = sync(
        seeded,
        image_dir,
        {**image(f"{PT}/002"), **english("sv01-003"), **image(f"{PT}/004")},
        at=LATER,
    )

    assert f"{PT}/001/low.webp" not in served.urls()
    assert run.result is not None
    assert run.result.counts.cards == ImageCounts(
        downloaded=2, cached=1, unavailable=1, failed=0
    )
    assert stored_images(seeded)["sv01-002"] == ("pt", LATER)
    assert stored_images(seeded)["sv01-001"] == ("pt", START)


def test_the_command_caches_tracked_sets_and_every_sets_artwork_once(
    capsys: pytest.CaptureFixture[str],
    database_url: str,
    engine: Engine,
    image_dir: Path,
) -> None:
    sv02_logo = "https://assets.tcgdex.net/pt/sv/sv02/logo"
    seed(
        engine,
        [
            set_row(symbol_url=None),
            set_row(id="sv02", logo_url=sv02_logo, symbol_url=None),
        ],
        [card_row(), card_row(id="sv02-001", set_id="sv02", image_url=f"{PT}/x")],
    )
    with engine.begin() as connection:
        connection.execute(
            insert(TrackedSet).values(
                owner_id=HOUSEHOLD_OWNER_ID, set_id="sv01", tracked_at=START
            )
        )
    logo = Reply(body=PIXEL)

    def command(
        routes: Mapping[str, Sequence[Reply]],
    ) -> tuple[int, SyncRun[ImageSyncResult]]:
        capsys.readouterr()
        exit_code = run_sync(
            "images",
            Settings(database_url=PostgresDsn(database_url), image_dir=image_dir),
            now=lambda: START,
            transport=httpx2.MockTransport(FixtureRoutes(routes)),
            sleep=SleepRecorder(),
        )
        stdout = capsys.readouterr().out
        return exit_code, SyncRun[ImageSyncResult].model_validate_json(stdout)

    exit_code, first = command(
        {
            **image(f"{PT}/001"),
            "https://assets.tcgdex.net/pt/sv/sv01/logo.webp": (logo,),
            f"{sv02_logo}.webp": failing(500),
        }
    )
    _, second = command({f"{sv02_logo}.webp": failing(500)})

    assert exit_code == 1
    assert first.result is not None
    assert first.result.set_id is None
    assert first.result.counts.cards.downloaded == 1
    assert first.result.counts.artwork == ImageCounts(
        downloaded=1, cached=0, unavailable=2, failed=1
    )
    assert (image_dir / "sets" / "sv01" / "logo.webp").read_bytes() == PIXEL
    assert second.result is not None
    assert second.result.counts.artwork.cached == 1
    assert second.result.counts.cards.cached == 1


def test_an_unwritable_image_directory_fails_the_run(
    seeded: Engine, tmp_path: Path
) -> None:
    read_only = tmp_path / "read-only"
    read_only.mkdir(mode=0o500)

    run, served = sync(seeded, read_only / "images", {})

    assert run.status is RunStatus.FAILED
    assert run.error is not None
    assert "is not writable" in run.error
    assert served.requests == []


@pytest.mark.parametrize(
    ("language", "files_present", "pt_url", "plan"),
    [
        (Language.PT, True, "pt", CardPlan.SKIP),
        (Language.EN, True, None, CardPlan.SKIP),
        (Language.EN, True, "pt", CardPlan.TRY_PT_KEEP_EN),
        (Language.PT, False, "pt", CardPlan.TRY_PT_THEN_EN),
        (None, False, "pt", CardPlan.TRY_PT_THEN_EN),
        (None, False, None, CardPlan.TRY_EN),
        (Language.EN, False, None, CardPlan.TRY_EN),
    ],
)
def test_plan_card(
    language: Language | None, files_present: bool, pt_url: str | None, plan: CardPlan
) -> None:
    card = CardToResolve("sv01-001", pt_url, language, files_present)

    assert plan_card(card) is plan


def test_files_stay_in_the_image_directory_and_a_failed_write_leaves_none(
    image_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_replace(*_args: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(OSError, match="disk full"):
        write_file(image_dir / "sets" / "sv01", "logo", b"logo")

    assert [p for p in image_dir.rglob("*") if p.is_file()] == []
    assert card_path(image_dir, "..", CardSize.SMALL) is None
    assert card_path(image_dir, ".", CardSize.SMALL) is None
