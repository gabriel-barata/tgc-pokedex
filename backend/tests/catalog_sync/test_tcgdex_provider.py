from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from importlib.metadata import version

import httpx2

from tcg_pokedex.catalog_sync.adapters.tcgdex import TcgdexProvider
from tcg_pokedex.catalog_sync.domain import Card, SetListing
from tests.catalog_sync.tcgdex_fixtures import (
    HAPPY,
    SV01_CARD_IDS,
    FixtureRoutes,
    Raise,
    Reply,
    SleepRecorder,
)

USER_AGENT = (
    f"tcg-pokedex/{version('tcg-pokedex')} "
    "(+https://github.com/gabriel-barata/tgc-pokedex)"
)


@contextmanager
def tcgdex(
    routes: FixtureRoutes, sleep: SleepRecorder | None = None
) -> Generator[TcgdexProvider]:
    with TcgdexProvider(
        transport=httpx2.MockTransport(routes), sleep=sleep or SleepRecorder()
    ) as provider:
        yield provider


def routes(
    table: Mapping[str, Sequence[Reply | Raise]] = HAPPY, hold: float = 0.0
) -> FixtureRoutes:
    return FixtureRoutes(table, hold=hold)


def test_requests_go_to_the_portuguese_api() -> None:
    served = routes()

    with tcgdex(served) as provider:
        provider.list_series_ids()
        provider.list_set_ids("sv")
        provider.fetch_set("sv01")
        provider.fetch_cards("sv01", ["sv01-001"])

    assert [requested.url for requested in served.requests] == [
        "https://api.tcgdex.net/v2/pt/series",
        "https://api.tcgdex.net/v2/pt/series/sv",
        "https://api.tcgdex.net/v2/pt/sets/sv01",
        "https://api.tcgdex.net/v2/pt/cards/sv01-001",
    ]


def test_every_request_identifies_the_app_and_has_a_10_second_timeout() -> None:
    served = routes()

    with tcgdex(served) as provider:
        provider.list_series_ids()
        provider.fetch_cards("sv01", SV01_CARD_IDS[:2])

    assert len(served.requests) == 3
    for requested in served.requests:
        assert requested.headers["User-Agent"] == USER_AGENT
        assert requested.timeout == {
            "connect": 10,
            "read": 10,
            "write": 10,
            "pool": 10,
        }


def test_fetch_set_returns_the_listing() -> None:
    with tcgdex(routes()) as provider:
        listing = provider.fetch_set("sv01")

    assert isinstance(listing, SetListing)
    assert listing.card_ids == SV01_CARD_IDS


def test_fetch_cards_returns_outcomes_aligned_with_the_requested_ids() -> None:
    card_ids = list(reversed(SV01_CARD_IDS))

    with tcgdex(routes()) as provider:
        outcomes = provider.fetch_cards("sv01", card_ids)

    assert [card.id for card in outcomes if isinstance(card, Card)] == card_ids


def test_card_requests_overlap_but_never_exceed_eight_in_flight() -> None:
    served = routes(hold=0.05)

    with tcgdex(served) as provider:
        provider.fetch_cards("sv01", SV01_CARD_IDS)

    assert len(SV01_CARD_IDS) == 9
    assert 1 < served.peak_in_flight <= 8


def test_a_successful_fetch_never_waits() -> None:
    sleep = SleepRecorder()

    with tcgdex(routes(), sleep) as provider:
        provider.fetch_cards("sv01", SV01_CARD_IDS)

    assert sleep.delays == []
