from datetime import UTC, datetime

from tcg_pokedex.catalog_sync.domain import (
    Change,
    Failure,
    Fetched,
    ResultBuilder,
    RunStatus,
    StoredCatalog,
    plan_set,
)
from tests.catalog_sync.builders import make_card, make_listing, make_series, make_set

EARLIER = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def card_failure(n: int) -> Failure:
    return Failure(kind="card", provider_id=f"sv01-{n:03d}", reason="HTTP 404")


def test_plan_set_classifies_each_row_against_the_stored_one() -> None:
    stored = StoredCatalog(
        series=Fetched(make_series(), EARLIER),
        card_set=Fetched(make_set(name="Nome antigo"), EARLIER),
        cards={
            "sv01-001": Fetched(make_card(), EARLIER),
            "sv01-002": Fetched(make_card(id="sv01-002", name="Antigo"), EARLIER),
        },
    )
    cards = [
        make_card(),
        make_card(id="sv01-002", name="Heracross"),
        make_card(id="sv01-003", name="Shroomish"),
    ]

    batch, changes = plan_set(stored, make_listing(), cards, series_written=set())

    assert batch.cards == tuple(cards)
    assert changes.series is Change.UNCHANGED
    assert changes.card_set is Change.UPDATED
    assert changes.cards == (Change.UNCHANGED, Change.UPDATED, Change.CREATED)


def test_plan_set_leaves_out_a_series_already_written_this_run() -> None:
    nothing = StoredCatalog(series=None, card_set=None, cards={})

    batch, changes = plan_set(nothing, make_listing(), [], series_written={"sv"})

    assert batch.series is None
    assert changes.series is None


def test_result_status_follows_failures_and_aborts() -> None:
    builder = ResultBuilder()
    assert builder.status() is RunStatus.SUCCEEDED

    builder.fail(card_failure(1))
    assert builder.status() is RunStatus.PARTIAL

    builder.abort()
    assert builder.status() is RunStatus.FAILED


def test_result_keeps_the_first_100_failures_but_counts_them_all() -> None:
    builder = ResultBuilder()

    for n in range(105):
        builder.fail(card_failure(n))
    result = builder.build()

    assert result.failures == tuple(card_failure(n) for n in range(100))
    assert result.counts.cards.failed == 105
