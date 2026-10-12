"""Contract every CatalogProvider must honour, run against the fake and the real one.

Both providers serve the same catalog: the recorded TCGdex corpus (`tcgdex_fixtures`).
"""

from collections.abc import Callable, Mapping, Sequence
from datetime import date

import httpx2
import pytest

from tcg_pokedex.catalog_sync.adapters.tcgdex import TcgdexProvider
from tcg_pokedex.catalog_sync.domain import Card, Failure, SetListing
from tcg_pokedex.catalog_sync.fakes import InMemoryCatalogProvider
from tcg_pokedex.catalog_sync.ports import CatalogProvider, ProviderUnavailableError
from tests.catalog_sync.builders import make_card, make_listing, make_series, make_set
from tests.catalog_sync.tcgdex_fixtures import (
    HAPPY,
    INDEX_DOWN,
    SV01_CARD_IDS,
    WITH_FAILURES,
    FixtureRoutes,
    Raise,
    Reply,
    SleepRecorder,
)

SERIES_IDS = ["base", "xy", "swsh", "sv", "tcgp"]


def sv01_card(card_id: str) -> Card:
    return make_card(id=card_id, collector_number=card_id.removeprefix("sv01-"))


def seeded_fake() -> InMemoryCatalogProvider:
    provider = InMemoryCatalogProvider()
    provider.add_series("base")
    provider.add_series("xy")
    provider.add_series("swsh", ["swshp", "swsh4.5"])
    provider.add_series("sv")
    provider.add_series("tcgp", ["A1"])
    provider.add_set(
        make_listing(
            card_set=make_set(
                id="base1",
                series_id="base",
                name="Coleção Básica",
                release_date=date(1999, 1, 9),
                official_count=102,
                total_count=102,
                logo_url=None,
                symbol_url=None,
            ),
            series=make_series(id="base", name="Coleção Básica"),
        )
    )
    provider.add_set(
        make_listing(card_ids=SV01_CARD_IDS),
        [sv01_card(card_id) for card_id in SV01_CARD_IDS],
    )
    provider.add_set(
        make_listing(
            card_set=make_set(id="xy0", series_id="xy"),
            series=make_series(id="xy", name="XY"),
        )
    )
    return provider


def corpus_fake(_request: pytest.FixtureRequest) -> CatalogProvider:
    return seeded_fake()


def corpus_fake_with_failures(_request: pytest.FixtureRequest) -> CatalogProvider:
    provider = seeded_fake()
    provider.fail_set("sv", "sv02", "HTTP 500 after 3 attempts")
    card_ids = [f"fail01-00{n}" for n in range(1, 5)]
    provider.add_set(
        make_listing(card_set=make_set(id="fail01"), card_ids=card_ids),
        [make_card(id="fail01-004", set_id="fail01")],
    )
    provider.fail_card("fail01-001", "invalid payload: name: Field required")
    provider.fail_card("fail01-002", "no variants")
    provider.fail_card("fail01-003", "HTTP 404")
    return provider


def index_down_fake(_request: pytest.FixtureRequest) -> CatalogProvider:
    provider = seeded_fake()
    provider.take_down("HTTP 500 after 3 attempts")
    return provider


def tcgdex_over(
    routes: Mapping[str, Sequence[Reply | Raise]], request: pytest.FixtureRequest
) -> TcgdexProvider:
    provider = TcgdexProvider(
        transport=httpx2.MockTransport(FixtureRoutes(routes)), sleep=SleepRecorder()
    )
    request.addfinalizer(provider.close)
    return provider


def corpus_tcgdex(request: pytest.FixtureRequest) -> CatalogProvider:
    return tcgdex_over(HAPPY, request)


def corpus_tcgdex_with_failures(request: pytest.FixtureRequest) -> CatalogProvider:
    return tcgdex_over(WITH_FAILURES, request)


def index_down_tcgdex(request: pytest.FixtureRequest) -> CatalogProvider:
    return tcgdex_over(INDEX_DOWN, request)


@pytest.fixture(params=[corpus_fake, corpus_tcgdex], ids=["fake", "tcgdex"])
def provider(request: pytest.FixtureRequest) -> CatalogProvider:
    factory: Callable[[pytest.FixtureRequest], CatalogProvider] = request.param
    return factory(request)


@pytest.fixture(
    params=[corpus_fake_with_failures, corpus_tcgdex_with_failures],
    ids=["fake", "tcgdex"],
)
def failing_provider(request: pytest.FixtureRequest) -> CatalogProvider:
    factory: Callable[[pytest.FixtureRequest], CatalogProvider] = request.param
    return factory(request)


@pytest.fixture(params=[index_down_fake, index_down_tcgdex], ids=["fake", "tcgdex"])
def index_down_provider(request: pytest.FixtureRequest) -> CatalogProvider:
    factory: Callable[[pytest.FixtureRequest], CatalogProvider] = request.param
    return factory(request)


def test_lists_every_series_in_provider_order_pocket_included(
    provider: CatalogProvider,
) -> None:
    assert provider.list_series_ids() == SERIES_IDS


def test_lists_the_set_ids_of_a_series_in_provider_order(
    provider: CatalogProvider,
) -> None:
    assert provider.list_set_ids("swsh") == ["swshp", "swsh4.5"]


def test_fetches_a_set_with_its_series_and_card_ids(provider: CatalogProvider) -> None:
    listing = provider.fetch_set("sv01")

    assert isinstance(listing, SetListing)
    assert listing.card_set.id == "sv01"
    assert listing.card_set.series_id == "sv"
    assert listing.series.id == "sv"
    assert listing.card_ids == SV01_CARD_IDS


def test_an_empty_set_is_a_listing_with_no_card_ids(provider: CatalogProvider) -> None:
    listing = provider.fetch_set("base1")

    assert isinstance(listing, SetListing)
    assert listing.card_ids == ()


def test_fetch_cards_returns_one_outcome_per_id_in_request_order(
    provider: CatalogProvider,
) -> None:
    card_ids = ["sv01-003", "sv01-001", "sv01-002"]

    outcomes = provider.fetch_cards("sv01", card_ids)

    assert [outcome.id for outcome in outcomes if isinstance(outcome, Card)] == card_ids


def test_a_card_belongs_to_the_requested_set_whatever_it_claims(
    provider: CatalogProvider,
) -> None:
    outcomes = provider.fetch_cards("sv01-copy", ["sv01-001"])

    assert len(outcomes) == 1
    assert isinstance(outcomes[0], Card)
    assert outcomes[0].set_id == "sv01-copy"


def test_an_index_failure_raises_provider_unavailable(
    index_down_provider: CatalogProvider,
) -> None:
    with pytest.raises(ProviderUnavailableError) as raised:
        index_down_provider.list_series_ids()

    assert raised.value.reason


def test_a_set_failure_is_returned_not_raised(
    failing_provider: CatalogProvider,
) -> None:
    outcome = failing_provider.fetch_set("sv02")

    assert isinstance(outcome, Failure)
    assert (outcome.kind, outcome.provider_id) == ("set", "sv02")
    assert outcome.reason


def test_card_failures_are_returned_aligned_with_the_requested_ids(
    failing_provider: CatalogProvider,
) -> None:
    card_ids = [f"fail01-00{n}" for n in range(1, 5)]

    outcomes = failing_provider.fetch_cards("fail01", card_ids)

    assert len(outcomes) == 4
    failures = outcomes[:3]
    assert all(isinstance(failure, Failure) for failure in failures)
    assert [(f.kind, f.provider_id) for f in failures if isinstance(f, Failure)] == [
        ("card", "fail01-001"),
        ("card", "fail01-002"),
        ("card", "fail01-003"),
    ]
    assert isinstance(outcomes[3], Card)
    assert outcomes[3].id == "fail01-004"
