from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from tcg_pokedex.catalog_sync.domain import (
    SOURCE,
    Card,
    CardCounts,
    Change,
    Failure,
    Fetched,
    KindCounts,
    ResultBuilder,
    RunStatus,
    SetCounts,
    StoredCatalog,
    SyncCounts,
    SyncKind,
    SyncResult,
    SyncRun,
    Variant,
    classify,
    is_pocket_series,
    plan_set,
)
from tests.catalog_sync.builders import make_card, make_listing, make_series, make_set

STARTED = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


def zero_counts() -> SyncCounts:
    return SyncCounts(
        series=KindCounts(fetched=0, created=0, updated=0, unchanged=0),
        sets=SetCounts(
            fetched=0, created=0, updated=0, unchanged=0, skipped=0, failed=0
        ),
        cards=CardCounts(fetched=0, created=0, updated=0, unchanged=0, failed=0),
    )


def test_variants_are_declared_in_canonical_storage_order() -> None:
    assert [variant.value for variant in Variant] == [
        "normal",
        "reverse",
        "holo",
        "first_edition",
        "w_promo",
    ]


def test_only_the_tcgp_series_is_pocket() -> None:
    assert is_pocket_series("tcgp")
    assert not is_pocket_series("sv")


def test_source_is_tcgdex() -> None:
    assert SOURCE == "tcgdex"


def test_card_needs_at_least_one_variant() -> None:
    with pytest.raises(ValueError, match="variant"):
        make_card(variants=())


def test_kind_counts_reject_fetched_that_is_not_the_sum_of_its_parts() -> None:
    with pytest.raises(ValidationError, match="fetched"):
        KindCounts(fetched=3, created=1, updated=1, unchanged=0)


def test_kind_counts_accept_fetched_equal_to_the_sum_of_its_parts() -> None:
    counts = KindCounts(fetched=3, created=1, updated=1, unchanged=1)

    assert counts.fetched == 3


def test_set_and_card_counts_add_skipped_and_failed() -> None:
    sets = SetCounts(fetched=1, created=1, updated=0, unchanged=0, skipped=2, failed=3)
    cards = CardCounts(fetched=1, created=0, updated=0, unchanged=1, failed=4)

    assert (sets.skipped, sets.failed) == (2, 3)
    assert cards.failed == 4


def test_set_counts_also_check_the_fetched_sum() -> None:
    with pytest.raises(ValidationError, match="fetched"):
        SetCounts(fetched=1, created=0, updated=0, unchanged=0, skipped=0, failed=0)


def test_result_keeps_at_most_100_failures() -> None:
    failures = tuple(
        Failure(kind="card", provider_id=f"sv01-{n}", reason="HTTP 404")
        for n in range(101)
    )

    with pytest.raises(ValidationError, match="100"):
        SyncResult(counts=zero_counts(), failures=failures)


def test_failure_kind_is_set_or_card() -> None:
    with pytest.raises(ValidationError):
        Failure.model_validate(
            {"kind": "series", "provider_id": "sv", "reason": "HTTP 500"}
        )


def test_sync_run_round_trips_through_json_in_utc() -> None:
    sao_paulo = timezone(timedelta(hours=-3))
    run = SyncRun(
        id=uuid4(),
        kind=SyncKind.CATALOG,
        status=RunStatus.PARTIAL,
        started_at=STARTED.astimezone(sao_paulo),
        finished_at=STARTED + timedelta(seconds=90),
        duration_ms=90_000,
        result=SyncResult(
            counts=zero_counts(),
            failures=(Failure(kind="card", provider_id="sv01-999", reason="HTTP 404"),),
        ),
    )

    restored = SyncRun.model_validate_json(run.model_dump_json())

    assert restored == run
    assert restored.started_at.tzinfo is UTC
    assert restored.started_at == STARTED
    assert run.model_dump(mode="json")["started_at"] == "2026-10-11T12:00:00Z"
    assert restored.kind == "catalog"
    assert restored.source == "tcgdex"


def test_new_sync_run_is_open() -> None:
    run = SyncRun(
        id=uuid4(), kind=SyncKind.CATALOG, status=RunStatus.RUNNING, started_at=STARTED
    )

    assert run.finished_at is None
    assert run.duration_ms is None
    assert run.result is None
    assert run.error is None


def test_sync_run_needs_an_aware_start_time() -> None:
    with pytest.raises(ValidationError):
        SyncRun(
            id=uuid4(),
            kind=SyncKind.CATALOG,
            status=RunStatus.RUNNING,
            started_at=datetime(2026, 10, 11, 12, 0),
        )


EARLIER = STARTED - timedelta(days=1)
NOTHING_STORED = StoredCatalog(series=None, card_set=None, cards={})


def card_failure(n: int) -> Failure:
    return Failure(kind="card", provider_id=f"sv01-{n:03d}", reason="HTTP 404")


def test_classify_without_a_stored_row_is_created() -> None:
    assert classify(None, make_card()) is Change.CREATED


def test_classify_an_identical_row_is_unchanged() -> None:
    assert classify(make_card(), make_card()) is Change.UNCHANGED


@pytest.mark.parametrize(
    "changed",
    [
        make_card(set_id="sv02"),
        make_card(collector_number="001a"),
        make_card(name="Pineco de Teste"),
        make_card(rarity=None),
        make_card(illustrator=None),
        make_card(image_url=None),
        make_card(variants=[Variant.NORMAL]),
    ],
)
def test_classify_a_change_in_any_field_is_updated(changed: Card) -> None:
    assert classify(make_card(), changed) is Change.UPDATED


def test_classify_compares_sets_and_series_too() -> None:
    assert classify(make_set(), make_set(name="Outro")) is Change.UPDATED
    assert classify(make_series(), make_series()) is Change.UNCHANGED


def test_plan_set_on_an_empty_store_creates_everything() -> None:
    listing = make_listing(card_ids=["sv01-001", "sv01-002"])
    cards = [make_card(), make_card(id="sv01-002", collector_number="002")]

    batch, changes = plan_set(NOTHING_STORED, listing, cards, series_written=set())

    assert batch.series == listing.series
    assert batch.card_set == listing.card_set
    assert batch.cards == tuple(cards)
    assert changes.series is Change.CREATED
    assert changes.card_set is Change.CREATED
    assert changes.cards == (Change.CREATED, Change.CREATED)


def test_plan_set_leaves_out_a_series_already_written_this_run() -> None:
    listing = make_listing(card_ids=["sv01-001"])

    batch, changes = plan_set(
        NOTHING_STORED, listing, [make_card()], series_written={"sv"}
    )

    assert batch.series is None
    assert changes.series is None


def test_plan_set_classifies_against_the_stored_rows() -> None:
    stored = StoredCatalog(
        series=Fetched(make_series(), EARLIER),
        card_set=Fetched(make_set(name="Nome antigo"), EARLIER),
        cards={
            "sv01-001": Fetched(make_card(), EARLIER),
            "sv01-002": Fetched(
                make_card(id="sv01-002", collector_number="002", name="Antigo"),
                EARLIER,
            ),
        },
    )
    listing = make_listing(card_ids=["sv01-001", "sv01-002", "sv01-003"])
    cards = [
        make_card(),
        make_card(id="sv01-002", collector_number="002", name="Heracross"),
        make_card(id="sv01-003", collector_number="003", name="Shroomish"),
    ]

    batch, changes = plan_set(stored, listing, cards, series_written=set())

    assert changes.series is Change.UNCHANGED
    assert changes.card_set is Change.UPDATED
    assert changes.cards == (Change.UNCHANGED, Change.UPDATED, Change.CREATED)
    assert all(card.set_id == listing.card_set.id for card in batch.cards)


def test_plan_set_without_cards_still_writes_the_set() -> None:
    batch, changes = plan_set(
        NOTHING_STORED, make_listing(card_ids=["sv01-001"]), [], series_written=set()
    )

    assert batch.card_set == make_set()
    assert batch.cards == ()
    assert changes.cards == ()


def test_result_builder_with_nothing_recorded_is_all_zero_and_succeeded() -> None:
    builder = ResultBuilder()

    result = builder.build()

    assert result.counts.series == KindCounts(
        fetched=0, created=0, updated=0, unchanged=0
    )
    assert result.counts.sets == SetCounts(
        fetched=0, created=0, updated=0, unchanged=0, skipped=0, failed=0
    )
    assert result.counts.cards == CardCounts(
        fetched=0, created=0, updated=0, unchanged=0, failed=0
    )
    assert result.failures == ()
    assert builder.status() is RunStatus.SUCCEEDED


def test_result_builder_counts_each_kind() -> None:
    builder = ResultBuilder()
    stored = StoredCatalog(series=None, card_set=Fetched(make_set(), EARLIER), cards={})
    _, first = plan_set(
        NOTHING_STORED, make_listing(), [make_card()], series_written=set()
    )
    _, second = plan_set(
        stored,
        make_listing(),
        [make_card(), make_card(id="sv01-002")],
        series_written={"sv"},
    )

    builder.record(first)
    builder.record(second)
    builder.skip_set()
    builder.fail(Failure(kind="set", provider_id="sv02", reason="HTTP 500"))
    builder.fail(card_failure(3))
    result = builder.build()

    assert result.counts.series == KindCounts(
        fetched=1, created=1, updated=0, unchanged=0
    )
    assert result.counts.sets == SetCounts(
        fetched=2, created=1, updated=0, unchanged=1, skipped=1, failed=1
    )
    assert result.counts.cards == CardCounts(
        fetched=3, created=3, updated=0, unchanged=0, failed=1
    )


def test_result_builder_keeps_the_first_100_failures_and_exact_counts() -> None:
    builder = ResultBuilder()

    for n in range(105):
        builder.fail(card_failure(n))
    result = builder.build()

    assert result.failures == tuple(card_failure(n) for n in range(100))
    assert result.counts.cards.failed == 105


def test_result_builder_status_is_partial_after_a_set_failure() -> None:
    builder = ResultBuilder()

    builder.fail(Failure(kind="set", provider_id="sv02", reason="HTTP 500"))

    assert builder.status() is RunStatus.PARTIAL


def test_result_builder_status_is_partial_after_a_card_failure() -> None:
    builder = ResultBuilder()

    builder.fail(card_failure(1))

    assert builder.status() is RunStatus.PARTIAL


def test_result_builder_status_is_failed_once_aborted() -> None:
    builder = ResultBuilder()
    builder.fail(card_failure(1))

    builder.abort()

    assert builder.status() is RunStatus.FAILED


def test_skipped_sets_alone_still_succeed() -> None:
    builder = ResultBuilder()

    builder.skip_set()

    assert builder.status() is RunStatus.SUCCEEDED
