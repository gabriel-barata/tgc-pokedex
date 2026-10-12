from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from importlib.metadata import version

import httpx2
import pytest

from tcg_pokedex.catalog_sync.adapters.tcgdex import TcgdexProvider
from tcg_pokedex.catalog_sync.domain import Card, Failure, SetListing
from tcg_pokedex.catalog_sync.ports import ProviderUnavailableError
from tests.catalog_sync.tcgdex_fixtures import (
    HAPPY,
    SV01_CARD_IDS,
    FixtureRoutes,
    Raise,
    Reply,
    SleepRecorder,
    failing,
    ok,
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


def fetch_one_card(
    answers: Sequence[Reply | Raise], sleep: SleepRecorder
) -> tuple[Card | Failure, FixtureRoutes]:
    served = routes({"cards/sv01-001": answers})
    with tcgdex(served, sleep) as provider:
        (outcome,) = provider.fetch_cards("sv01", ["sv01-001"])
    return outcome, served


def test_a_card_answered_500_then_200_is_fetched_after_one_wait() -> None:
    sleep = SleepRecorder()

    outcome, served = fetch_one_card(
        (Reply(500), Reply(fixture="cards/sv01-001.json")), sleep
    )

    assert isinstance(outcome, Card)
    assert len(served.requests) == 2
    assert sleep.delays == [1.0]


def test_a_set_failing_three_times_is_a_failure_after_backing_off() -> None:
    sleep = SleepRecorder()
    served = routes({"sets/sv02": failing(500)})

    with tcgdex(served, sleep) as provider:
        outcome = provider.fetch_set("sv02")

    assert outcome == Failure(
        kind="set", provider_id="sv02", reason="HTTP 500 after 3 attempts"
    )
    assert served.paths == ["sets/sv02"] * 3
    assert sleep.delays == [1.0, 2.0]


def test_a_card_not_found_fails_at_once() -> None:
    sleep = SleepRecorder()

    outcome, served = fetch_one_card((Reply(404),), sleep)

    assert outcome == Failure(kind="card", provider_id="sv01-001", reason="HTTP 404")
    assert len(served.requests) == 1
    assert sleep.delays == []


@pytest.mark.parametrize(("status", "wait"), [(429, "5"), (503, "3")])
def test_retry_after_is_honoured_on_429_and_503(status: int, wait: str) -> None:
    sleep = SleepRecorder()

    outcome, _ = fetch_one_card(
        (
            Reply(status, headers={"Retry-After": wait}),
            Reply(fixture="cards/sv01-001.json"),
        ),
        sleep,
    )

    assert isinstance(outcome, Card)
    assert sleep.delays == [float(wait)]


def test_a_retry_after_date_falls_back_to_the_backoff() -> None:
    sleep = SleepRecorder()

    outcome, _ = fetch_one_card(
        (
            Reply(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}),
            Reply(fixture="cards/sv01-001.json"),
        ),
        sleep,
    )

    assert isinstance(outcome, Card)
    assert sleep.delays == [1.0]


def test_too_many_requests_three_times_is_a_failure() -> None:
    outcome, _ = fetch_one_card(failing(429), SleepRecorder())

    assert outcome == Failure(
        kind="card", provider_id="sv01-001", reason="HTTP 429 after 3 attempts"
    )


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (httpx2.ReadTimeout, "timeout after 3 attempts"),
        (httpx2.ConnectTimeout, "timeout after 3 attempts"),
        (httpx2.ConnectError, "network error after 3 attempts"),
        (httpx2.RemoteProtocolError, "network error after 3 attempts"),
    ],
)
def test_transport_errors_are_retried_then_fail(
    error: type[httpx2.TransportError], reason: str
) -> None:
    sleep = SleepRecorder()

    outcome, served = fetch_one_card((Raise(error),) * 3, sleep)

    assert outcome == Failure(kind="card", provider_id="sv01-001", reason=reason)
    assert len(served.requests) == 3
    assert sleep.delays == [1.0, 2.0]


def test_an_invalid_card_payload_is_not_retried() -> None:
    sleep = SleepRecorder()

    outcome, served = fetch_one_card(ok("cards/fail01-001.json"), sleep)

    assert isinstance(outcome, Failure)
    assert outcome.reason == "invalid payload: name: Field required"
    assert len(served.requests) == 1
    assert sleep.delays == []


def test_the_series_index_failing_three_times_is_unavailable() -> None:
    with (
        tcgdex(routes({"series": failing(500)})) as provider,
        pytest.raises(ProviderUnavailableError) as raised,
    ):
        provider.list_series_ids()

    assert raised.value.reason == "HTTP 500 after 3 attempts"


def test_a_series_detail_failing_three_times_is_unavailable() -> None:
    with (
        tcgdex(routes({"series/sv": failing(502)})) as provider,
        pytest.raises(ProviderUnavailableError) as raised,
    ):
        provider.list_set_ids("sv")

    assert raised.value.reason == "HTTP 502 after 3 attempts"


def test_a_series_detail_not_found_is_unavailable_at_once() -> None:
    with (
        tcgdex(routes({"series/sv": (Reply(404),)})) as provider,
        pytest.raises(ProviderUnavailableError) as raised,
    ):
        provider.list_set_ids("sv")

    assert raised.value.reason == "HTTP 404"


def test_an_invalid_index_payload_is_unavailable() -> None:
    with (
        tcgdex(routes({"series": ok("sets/sv01.json")})) as provider,
        pytest.raises(ProviderUnavailableError) as raised,
    ):
        provider.list_series_ids()

    assert raised.value.reason.startswith("invalid payload: ")
