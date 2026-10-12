"""Contract every CatalogProvider must honour, run against the fake and the real one.

Both providers serve the same catalog: the recorded TCGdex corpus (`tcgdex_fixtures`).
"""

from collections.abc import Callable, Mapping, Sequence

import httpx2
import pytest

from tcg_pokedex.catalog_sync.adapters.tcgdex import TcgdexProvider
from tcg_pokedex.catalog_sync.domain import Failure, SetListing
from tcg_pokedex.catalog_sync.fakes import InMemoryCatalogProvider
from tcg_pokedex.catalog_sync.ports import CatalogProvider, ProviderUnavailableError
from tests.catalog_sync.builders import make_card, make_listing
from tests.catalog_sync.tcgdex_fixtures import (
    INDEX_DOWN,
    WITH_FAILURES,
    FixtureRoutes,
    Reply,
    SleepRecorder,
)

SV01_CARDS = [make_card(), make_card(id="sv01-002", name="Heracross")]


def fake(_request: pytest.FixtureRequest) -> CatalogProvider:
    provider = InMemoryCatalogProvider()
    provider.add_set(make_listing(card_ids=["sv01-001", "sv01-002"]), SV01_CARDS)
    provider.fail_set("sv", "sv02", "HTTP 500 after 3 attempts")
    provider.fail_card("sv01-002", "HTTP 404")
    provider.add_series("tcgp")
    return provider


def fake_index_down(_request: pytest.FixtureRequest) -> CatalogProvider:
    provider = InMemoryCatalogProvider()
    provider.take_down("HTTP 500 after 3 attempts")
    return provider


def tcgdex_over(
    routes: Mapping[str, Sequence[Reply]], request: pytest.FixtureRequest
) -> TcgdexProvider:
    provider = TcgdexProvider(
        transport=httpx2.MockTransport(FixtureRoutes(routes)), sleep=SleepRecorder()
    )
    request.addfinalizer(provider.close)
    return provider


def tcgdex(request: pytest.FixtureRequest) -> CatalogProvider:
    return tcgdex_over(WITH_FAILURES, request)


def tcgdex_index_down(request: pytest.FixtureRequest) -> CatalogProvider:
    return tcgdex_over(INDEX_DOWN, request)


@pytest.fixture(params=[fake, tcgdex], ids=["fake", "tcgdex"])
def provider(request: pytest.FixtureRequest) -> CatalogProvider:
    factory: Callable[[pytest.FixtureRequest], CatalogProvider] = request.param
    return factory(request)


@pytest.fixture(params=[fake_index_down, tcgdex_index_down], ids=["fake", "tcgdex"])
def index_down_provider(request: pytest.FixtureRequest) -> CatalogProvider:
    factory: Callable[[pytest.FixtureRequest], CatalogProvider] = request.param
    return factory(request)


def test_lists_series_and_their_sets_pocket_included(
    provider: CatalogProvider,
) -> None:
    assert provider.list_series_ids() == ["sv", "tcgp"]
    assert provider.list_set_ids("sv") == ["sv01", "sv02"]


def test_fetches_a_set_or_returns_its_failure(provider: CatalogProvider) -> None:
    listing = provider.fetch_set("sv01")
    failure = provider.fetch_set("sv02")

    assert isinstance(listing, SetListing)
    assert listing.card_set.series_id == "sv"
    assert listing.card_ids == ("sv01-001", "sv01-002")
    assert isinstance(failure, Failure)
    assert (failure.kind, failure.provider_id) == ("set", "sv02")


def test_fetch_cards_returns_one_outcome_per_id_in_request_order(
    provider: CatalogProvider,
) -> None:
    outcomes = provider.fetch_cards("sv01", ["sv01-001", "sv01-002"])

    assert outcomes == [
        SV01_CARDS[0],
        Failure(kind="card", provider_id="sv01-002", reason="HTTP 404"),
    ]


def test_an_index_failure_raises_provider_unavailable(
    index_down_provider: CatalogProvider,
) -> None:
    with pytest.raises(ProviderUnavailableError) as raised:
        index_down_provider.list_series_ids()

    assert raised.value.reason == "HTTP 500 after 3 attempts"
