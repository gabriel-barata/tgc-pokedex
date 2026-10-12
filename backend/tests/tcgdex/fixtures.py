"""Serve recorded TCGdex answers to the adapters through `httpx2.MockTransport`.

Every request needs an explicit route: an unknown URL, or a route whose responses are
used up, raises `AssertionError`. A route is an absolute URL, or a path relative to
`https://api.tcgdex.net/v2/pt/`.
"""

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx2

FIXTURES = Path(__file__).parents[1] / "catalog_sync" / "fixtures" / "tcgdex"
PT_API = "https://api.tcgdex.net/v2/pt/"


@dataclass(frozen=True)
class Reply:
    """An HTTP answer: a status and a body read from a fixture file or given as bytes.

    `fixture` is relative to the pt API corpus, `FIXTURES`, or an absolute path.
    """

    status: int = 200
    fixture: str | Path | None = None
    body: bytes | None = None

    def content(self) -> bytes:
        if self.body is not None:
            return self.body
        return (FIXTURES / self.fixture).read_bytes() if self.fixture else b"{}"


def ok(fixture: str) -> tuple[Reply]:
    return (Reply(fixture=fixture),)


def failing(status: int, times: int = 3) -> tuple[Reply, ...]:
    return (Reply(status),) * times


class FixtureRoutes:
    """`MockTransport` handler answering each path from a route table, in order."""

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


class SleepRecorder:
    """Stands in for `time.sleep`: returns at once and keeps the requested delays."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


SV01_CARD_IDS = ("sv01-001", "sv01-002")

HAPPY: Mapping[str, Sequence[Reply]] = {
    "series": ok("series.json"),
    "series/sv": ok("series/sv.json"),
    "sets/sv01": ok("sets/sv01.json"),
    **{f"cards/{card_id}": ok(f"cards/{card_id}.json") for card_id in SV01_CARD_IDS},
}

WITH_FAILURES: Mapping[str, Sequence[Reply]] = {
    **HAPPY,
    "series/sv": ok("series/sv.with-failures.json"),
    "sets/sv02": failing(500),
    "cards/sv01-002": (Reply(404),),
}

INDEX_DOWN: Mapping[str, Sequence[Reply]] = {"series": failing(500)}
