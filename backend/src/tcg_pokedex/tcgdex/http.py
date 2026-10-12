"""The one HTTP policy for TCGdex requests: client, user agent, limits, retries."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version
from typing import Self

import httpx2

REPOSITORY_URL = "https://github.com/gabriel-barata/tgc-pokedex"
USER_AGENT = f"tcg-pokedex/{version('tcg-pokedex')} (+{REPOSITORY_URL})"
TIMEOUT_SECONDS = 10
MAX_IN_FLIGHT = 8
ATTEMPTS = 3
BACKOFF_SECONDS = (1.0, 2.0)
TOO_MANY_REQUESTS = 429
SERVER_ERROR = 500
RETRY_AFTER_STATUSES = frozenset({TOO_MANY_REQUESTS, 503})


class RequestFailedError(Exception):
    """A request gave up. `status` is the last HTTP status, None for a network error."""

    def __init__(self, reason: str, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


@dataclass(frozen=True)
class _Retry:
    reason: str
    status: int | None = None
    retry_after: float | None = None


class TcgdexHttp:
    """GETs absolute TCGdex URLs on one client shared by every thread.

    At most `MAX_IN_FLIGHT` requests run at once. Network errors, 5xx and 429 are
    retried up to `ATTEMPTS` times, waiting `BACKOFF_SECONDS` or the provider's
    `Retry-After`; any other 4xx fails at once. `transport` and `sleep` are test seams.
    """

    def __init__(
        self,
        transport: httpx2.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = httpx2.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
            limits=httpx2.Limits(max_connections=MAX_IN_FLIGHT),
            transport=transport,
        )
        self._sleep = sleep

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get(self, url: str) -> bytes:
        """The response body of a 2xx. Raises `RequestFailedError` otherwise."""
        attempt = 1
        while True:
            outcome = self._attempt(url)
            if isinstance(outcome, bytes):
                return outcome
            if attempt == ATTEMPTS:
                raise RequestFailedError(
                    f"{outcome.reason} after {ATTEMPTS} attempts", outcome.status
                )
            wait = outcome.retry_after
            self._sleep(BACKOFF_SECONDS[attempt - 1] if wait is None else wait)
            attempt += 1

    def _attempt(self, url: str) -> bytes | _Retry:
        try:
            response = self._client.get(url)
        except httpx2.TimeoutException:
            return _Retry("timeout")
        except httpx2.TransportError:
            return _Retry("network error")
        if response.is_success:
            return response.content
        status = response.status_code
        if status != TOO_MANY_REQUESTS and status < SERVER_ERROR:
            raise RequestFailedError(f"HTTP {status}", status)
        return _Retry(f"HTTP {status}", status, _retry_after(response))


def _retry_after(response: httpx2.Response) -> float | None:
    """The wait the provider asked for, when given in seconds on a 429 or 503."""
    header = response.headers.get("Retry-After", "")
    if response.status_code in RETRY_AFTER_STATUSES and header.isdigit():
        return float(header)
    return None
