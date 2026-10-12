from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from tcg_pokedex.catalog_sync.domain import (
    SOURCE,
    CardCounts,
    Failure,
    KindCounts,
    RunStatus,
    SetCounts,
    SyncCounts,
    SyncKind,
    SyncResult,
    SyncRun,
    Variant,
    is_pocket_series,
)
from tests.catalog_sync.builders import make_card

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
