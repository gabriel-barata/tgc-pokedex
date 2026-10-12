"""Shared test helpers: recorded TCGdex answers and catalog rows to seed.

TCGdex answers are served through `httpx2.MockTransport`. Every request needs an
explicit route: an unknown URL, or a route whose answers are used up, raises
`AssertionError`. A route is an absolute URL, or a path under `PT_API`.
"""

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx2
from sqlalchemy import Engine, insert

from tcg_pokedex.tables import cards, series, sets
from tcg_pokedex.tcgdex import SOURCE, Tcgdex

FIXTURES = Path(__file__).parent / "fixtures"
PT_API = "https://api.tcgdex.net/v2/pt/"
EN_API = "https://api.tcgdex.net/v2/en/cards"
PIXEL = (FIXTURES / "images" / "pixel.webp").read_bytes()
SEEDED_AT = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Reply:
    """An HTTP answer: a status and a body, from a fixture file or given as bytes.

    `fixture` is relative to the pt API corpus, `FIXTURES / "tcgdex"`, or absolute.
    """

    status: int = 200
    fixture: str | Path | None = None
    body: bytes | None = None

    def content(self) -> bytes:
        if self.body is not None:
            return self.body
        if self.fixture is None:
            return b"{}"
        return (FIXTURES / "tcgdex" / self.fixture).read_bytes()


def ok(fixture: str) -> tuple[Reply]:
    return (Reply(fixture=fixture),)


def failing(status: int, times: int = 3) -> tuple[Reply, ...]:
    return (Reply(status),) * times


def image(base_url: str) -> dict[str, Sequence[Reply]]:
    """Both sizes of a card image, served once each."""
    return {
        f"{base_url}/low.webp": (Reply(body=PIXEL),),
        f"{base_url}/high.webp": (Reply(body=PIXEL),),
    }


def english(card_id: str, fixture: str | None = None) -> dict[str, Sequence[Reply]]:
    """The English card lookup, answered from a recorded payload or with a 404."""
    path = FIXTURES / "images" / "en" / fixture if fixture else None
    return {f"{EN_API}/{card_id}": (Reply(fixture=path) if path else Reply(404),)}


class FixtureRoutes:
    """`MockTransport` handler answering each URL from a route table, in order."""

    def __init__(self, routes: Mapping[str, Sequence[Reply]]) -> None:
        self._routes = {path: deque(answers) for path, answers in routes.items()}
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        url = str(request.url)
        answers = self._routes.get(url) or self._routes.get(url.removeprefix(PT_API))
        if not answers:
            raise AssertionError(f"no fixture route left for {url!r}")
        answer = answers.popleft()
        return httpx2.Response(answer.status, content=answer.content())

    def urls(self) -> list[str]:
        return [str(request.url) for request in self.requests]


class SleepRecorder:
    """Stands in for `time.sleep`: returns at once and keeps the requested delays."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def tcgdex(served: FixtureRoutes, sleep: SleepRecorder | None = None) -> Tcgdex:
    return Tcgdex(
        transport=httpx2.MockTransport(served), sleep=sleep or SleepRecorder()
    )


HAPPY: Mapping[str, Sequence[Reply]] = {
    "series": ok("series.json"),
    "series/sv": ok("series/sv.json"),
    "sets/sv01": ok("sets/sv01.json"),
    "cards/sv01-001": ok("cards/sv01-001.json"),
    "cards/sv01-002": ok("cards/sv01-002.json"),
}


def set_row(**overrides: Any) -> dict[str, Any]:
    return {
        "id": "sv01",
        "series_id": "sv",
        "name": "Escarlate e Violeta",
        "release_date": date(2023, 3, 31),
        "official_count": 198,
        "total_count": 258,
        "logo_url": "https://assets.tcgdex.net/pt/sv/sv01/logo",
        "symbol_url": "https://assets.tcgdex.net/univ/sv/sv01/symbol",
        **overrides,
    }


def card_row(**overrides: Any) -> dict[str, Any]:
    return {
        "id": "sv01-001",
        "set_id": "sv01",
        "collector_number": "001",
        "name": "Pineco",
        "rarity": "Comum",
        "illustrator": "Shigenori Negishi",
        "image_url": "https://assets.tcgdex.net/pt/sv/sv01/001",
        "variants": ["normal", "reverse"],
        **overrides,
    }


def seed(
    engine: Engine,
    set_rows: Sequence[dict[str, Any]] = (),
    card_rows: Sequence[dict[str, Any]] = (),
) -> None:
    """Store the sv series, these sets and these cards, as a catalog sync would."""
    provenance = {"source": SOURCE, "fetched_at": SEEDED_AT}
    with engine.begin() as connection:
        connection.execute(
            insert(series).values(id="sv", name="Escarlate e Violeta", **provenance)
        )
        for table, rows in ((sets, set_rows), (cards, card_rows)):
            if rows:
                connection.execute(
                    insert(table), [{**row, **provenance} for row in rows]
                )
