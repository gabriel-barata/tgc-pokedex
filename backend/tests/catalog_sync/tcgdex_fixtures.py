"""Serve the recorded TCGdex corpus to the adapter through `httpx2.MockTransport`.

Every request needs an explicit route: an unknown path, or a route whose responses
are used up, raises `AssertionError`. Route paths are relative to
`https://api.tcgdex.net/v2/pt/`. `fixtures/tcgdex/README.md` says what each fixture
covers.
"""

import threading
import time
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import httpx2

FIXTURES = Path(__file__).parent / "fixtures" / "tcgdex"
API_PREFIX = "/v2/pt/"


@dataclass(frozen=True)
class Reply:
    """An HTTP answer: a status, an optional fixture file body and extra headers."""

    status: int = 200
    fixture: str | None = None
    headers: Mapping[str, str] = field(default_factory=dict[str, str])


@dataclass(frozen=True)
class Raise:
    """A transport error raised instead of answering, e.g. `httpx2.ReadTimeout`."""

    error: type[httpx2.TransportError]


@dataclass(frozen=True)
class Requested:
    """One request the adapter made."""

    path: str
    url: str
    headers: httpx2.Headers
    timeout: Mapping[str, float | None]


def ok(fixture: str) -> tuple[Reply]:
    return (Reply(fixture=fixture),)


def failing(status: int, times: int = 3) -> tuple[Reply, ...]:
    return (Reply(status),) * times


class FixtureRoutes:
    """`MockTransport` handler serving responses from a route table, in order per path.

    `hold` keeps each request in flight for that many seconds, so tests can observe how
    many requests overlap (`peak_in_flight`).
    """

    def __init__(
        self, routes: Mapping[str, Sequence[Reply | Raise]], hold: float = 0.0
    ) -> None:
        self._routes = {path: deque(answers) for path, answers in routes.items()}
        self._hold = hold
        self._lock = threading.Lock()
        self._in_flight = 0
        self.peak_in_flight = 0
        self.requests: list[Requested] = []

    @property
    def paths(self) -> list[str]:
        return [requested.path for requested in self.requests]

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path.removeprefix(API_PREFIX)
        with self._lock:
            self.requests.append(
                Requested(
                    path=path,
                    url=str(request.url),
                    headers=request.headers,
                    timeout=request.extensions.get("timeout", {}),
                )
            )
            answers = self._routes.get(path)
            if not answers:
                raise AssertionError(f"no fixture route left for {path!r}")
            answer = answers.popleft()
            self._in_flight += 1
            self.peak_in_flight = max(self.peak_in_flight, self._in_flight)
        try:
            time.sleep(self._hold)
        finally:
            with self._lock:
                self._in_flight -= 1
        if isinstance(answer, Raise):
            raise answer.error(f"fixture error for {path}", request=request)
        content = (FIXTURES / answer.fixture).read_bytes() if answer.fixture else b"{}"
        return httpx2.Response(
            answer.status,
            headers={"Content-Type": "application/json", **answer.headers},
            content=content,
        )


class SleepRecorder:
    """Stands in for `time.sleep`: returns at once and keeps the requested delays."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


SV01_CARD_IDS = tuple(f"sv01-{number:03d}" for number in range(1, 10))
HAPPY_CARD_IDS = (
    *SV01_CARD_IDS,
    "xy0-1",
    "xy0-2",
    "swshp-SWSH032",
    "swshp-SWSH158",
    "swsh4.5-1",
)

HAPPY: Mapping[str, Sequence[Reply | Raise]] = {
    "series": ok("series.json"),
    "series/base": ok("series/base.json"),
    "series/xy": ok("series/xy.json"),
    "series/swsh": ok("series/swsh.json"),
    "series/sv": ok("series/sv.json"),
    "sets/base1": ok("sets/base1.json"),
    "sets/xy0": ok("sets/xy0.json"),
    "sets/swshp": ok("sets/swshp.json"),
    "sets/swsh4.5": ok("sets/swsh4.5.json"),
    "sets/sv01": ok("sets/sv01.json"),
    **{f"cards/{card_id}": ok(f"cards/{card_id}.json") for card_id in HAPPY_CARD_IDS},
}

WITH_FAILURES: Mapping[str, Sequence[Reply | Raise]] = {
    **HAPPY,
    "series/sv": ok("series/sv.with-failures.json"),
    "sets/sv02": failing(500),
    "sets/fail01": ok("sets/fail01.json"),
    "cards/fail01-001": ok("cards/fail01-001.json"),
    "cards/fail01-002": ok("cards/fail01-002.json"),
    "cards/fail01-003": (Reply(404),),
    "cards/fail01-004": (Reply(500), Reply(fixture="cards/fail01-004.json")),
}

INDEX_DOWN: Mapping[str, Sequence[Reply | Raise]] = {"series": failing(500)}
