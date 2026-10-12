from datetime import UTC, datetime
from uuid import uuid4

import pytest

from tcg_pokedex.image_cache.domain import (
    CardPlan,
    CardToResolve,
    ImageCounts,
    ImageFailure,
    ImageResultBuilder,
    ImageSyncResult,
    Language,
    Outcome,
    StoredCardImage,
    plan_card,
)
from tcg_pokedex.sync_runs.domain import RunStatus, SyncKind, SyncRun

EARLIER = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
PT_URL = "https://assets.tcgdex.net/pt/sv/sv01/001"


def stored(language: Language | None) -> StoredCardImage:
    return StoredCardImage(language=language, fetched_at=EARLIER)


@pytest.mark.parametrize(
    ("stored_image", "files_present", "pt_url", "plan"),
    [
        (stored(Language.PT), True, PT_URL, CardPlan.SKIP),
        (stored(Language.PT), True, None, CardPlan.SKIP),
        (stored(Language.EN), True, None, CardPlan.SKIP),
        (stored(Language.EN), True, PT_URL, CardPlan.TRY_PT_KEEP_EN),
        (None, False, PT_URL, CardPlan.TRY_PT_THEN_EN),
        (stored(None), False, PT_URL, CardPlan.TRY_PT_THEN_EN),
        (stored(Language.PT), False, PT_URL, CardPlan.TRY_PT_THEN_EN),
        (None, False, None, CardPlan.TRY_EN),
        (stored(None), False, None, CardPlan.TRY_EN),
        (stored(Language.EN), False, None, CardPlan.TRY_EN),
    ],
)
def test_plan_card(
    stored_image: StoredCardImage | None,
    files_present: bool,
    pt_url: str | None,
    plan: CardPlan,
) -> None:
    card = CardToResolve(
        card_id="sv01-001",
        pt_image_url=pt_url,
        stored=stored_image,
        files_present=files_present,
    )

    assert plan_card(card) is plan


def card_failure(n: int) -> ImageFailure:
    return ImageFailure(kind="card", provider_id=f"sv01-{n:03d}", reason="HTTP 500")


def test_result_counts_cards_and_artwork_apart_and_keeps_100_failures() -> None:
    builder = ImageResultBuilder(set_id="sv01")
    builder.count_card(Outcome.DOWNLOADED)
    builder.count_card(Outcome.CACHED)
    builder.count_artwork(Outcome.UNAVAILABLE)
    builder.fail(ImageFailure(kind="symbol", provider_id="sv01", reason="HTTP 500"))
    for n in range(105):
        builder.fail(card_failure(n))

    result = builder.build()

    assert result.set_id == "sv01"
    assert result.counts.cards == ImageCounts(
        downloaded=1, cached=1, unavailable=0, failed=105
    )
    assert result.counts.artwork == ImageCounts(
        downloaded=0, cached=0, unavailable=1, failed=1
    )
    assert len(result.failures) == 100


def test_result_status_follows_failures_and_aborts() -> None:
    builder = ImageResultBuilder(set_id=None)
    assert builder.status() is RunStatus.SUCCEEDED

    builder.fail(card_failure(1))
    assert builder.status() is RunStatus.PARTIAL

    builder.abort()
    assert builder.status() is RunStatus.FAILED


def test_an_images_run_round_trips_through_json() -> None:
    builder = ImageResultBuilder(set_id=None)
    builder.count_card(Outcome.DOWNLOADED)
    run = SyncRun[ImageSyncResult](
        id=uuid4(),
        kind=SyncKind.IMAGES,
        status=RunStatus.SUCCEEDED,
        started_at=EARLIER,
        result=builder.build(),
    )

    assert SyncRun[ImageSyncResult].model_validate_json(run.model_dump_json()) == run
