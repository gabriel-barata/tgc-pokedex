from collections.abc import Mapping, Sequence
from importlib.metadata import version

import httpx2

from tcg_pokedex.catalog_sync.adapters.tcgdex import TcgdexProvider
from tcg_pokedex.catalog_sync.domain import Card, Failure
from tests.catalog_sync.tcgdex_fixtures import (
    HAPPY,
    FixtureRoutes,
    Reply,
    SleepRecorder,
    failing,
)


def fetch_card(
    routes: Mapping[str, Sequence[Reply]],
) -> tuple[Card | Failure, FixtureRoutes, SleepRecorder]:
    served = FixtureRoutes(routes)
    sleep = SleepRecorder()
    with TcgdexProvider(
        transport=httpx2.MockTransport(served), sleep=sleep
    ) as provider:
        (outcome,) = provider.fetch_cards("sv01", ["sv01-001"])
    return outcome, served, sleep


def test_requests_go_to_the_portuguese_api_and_identify_the_app() -> None:
    _, served, _ = fetch_card(HAPPY)

    (request,) = served.requests
    assert str(request.url) == "https://api.tcgdex.net/v2/pt/cards/sv01-001"
    assert request.headers["User-Agent"].startswith(
        f"tcg-pokedex/{version('tcg-pokedex')} "
    )


def test_a_server_error_is_retried_after_a_backoff() -> None:
    outcome, served, sleep = fetch_card(
        {"cards/sv01-001": (Reply(500), Reply(fixture="cards/sv01-001.json"))}
    )

    assert isinstance(outcome, Card)
    assert len(served.requests) == 2
    assert sleep.delays == [1.0]


def test_three_server_errors_are_a_failure() -> None:
    outcome, _, sleep = fetch_card({"cards/sv01-001": failing(500)})

    assert outcome == Failure(
        kind="card", provider_id="sv01-001", reason="HTTP 500 after 3 attempts"
    )
    assert sleep.delays == [1.0, 2.0]


def test_a_client_error_fails_at_once() -> None:
    outcome, served, sleep = fetch_card({"cards/sv01-001": (Reply(404),)})

    assert outcome == Failure(kind="card", provider_id="sv01-001", reason="HTTP 404")
    assert len(served.requests) == 1
    assert sleep.delays == []
