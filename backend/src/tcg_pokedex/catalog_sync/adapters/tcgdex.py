import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from importlib.metadata import version
from typing import Self

import httpx2
from pydantic import ValidationError

from tcg_pokedex.catalog_sync.adapters.tcgdex_payloads import (
    invalid_payload,
    parse_card,
    parse_series_ids,
    parse_set,
    parse_set_ids,
)
from tcg_pokedex.catalog_sync.domain import Card, Failure, SetListing
from tcg_pokedex.catalog_sync.ports import ProviderUnavailableError

BASE_URL = "https://api.tcgdex.net/v2/pt"
REPOSITORY_URL = "https://github.com/gabriel-barata/tgc-pokedex"
USER_AGENT = f"tcg-pokedex/{version('tcg-pokedex')} (+{REPOSITORY_URL})"
TIMEOUT_SECONDS = 10
MAX_IN_FLIGHT = 8
ATTEMPTS = 3
BACKOFF_SECONDS = (1.0, 2.0)
TOO_MANY_REQUESTS = 429
SERVER_ERROR = 500
RETRY_AFTER_STATUSES = frozenset({TOO_MANY_REQUESTS, 503})


class _RequestFailedError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class _Retry:
    reason: str
    retry_after: float | None = None


class TcgdexProvider:
    """CatalogProvider reading the Portuguese TCGdex API.

    Card requests run on up to `MAX_IN_FLIGHT` threads sharing one client; index and
    set requests run one at a time. Network errors, 5xx and 429 are retried up to
    `ATTEMPTS` times, waiting `BACKOFF_SECONDS` or the provider's `Retry-After`; any
    other 4xx fails at once. `transport` and `sleep` are test seams.
    """

    def __init__(
        self,
        transport: httpx2.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = httpx2.Client(
            base_url=BASE_URL,
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

    def list_series_ids(self) -> list[str]:
        return self._index("/series", parse_series_ids)

    def list_set_ids(self, series_id: str) -> list[str]:
        return self._index(f"/series/{series_id}", parse_set_ids)

    def fetch_set(self, set_id: str) -> SetListing | Failure:
        try:
            content = self._get(f"/sets/{set_id}")
        except _RequestFailedError as error:
            return Failure(kind="set", provider_id=set_id, reason=error.reason)
        return parse_set(content, set_id)

    def fetch_cards(self, set_id: str, card_ids: Sequence[str]) -> list[Card | Failure]:
        with ThreadPoolExecutor(max_workers=MAX_IN_FLIGHT) as pool:
            return list(pool.map(partial(self._fetch_card, set_id), card_ids))

    def _fetch_card(self, set_id: str, card_id: str) -> Card | Failure:
        try:
            content = self._get(f"/cards/{card_id}")
        except _RequestFailedError as error:
            return Failure(kind="card", provider_id=card_id, reason=error.reason)
        return parse_card(content, card_id, set_id=set_id)

    def _index(self, path: str, parse: Callable[[bytes], list[str]]) -> list[str]:
        try:
            return parse(self._get(path))
        except _RequestFailedError as error:
            raise ProviderUnavailableError(error.reason) from error
        except ValidationError as error:
            raise ProviderUnavailableError(invalid_payload(error)) from error

    def _get(self, path: str) -> bytes:
        attempt = 1
        while True:
            outcome = self._attempt(path)
            if isinstance(outcome, bytes):
                return outcome
            if attempt == ATTEMPTS:
                raise _RequestFailedError(f"{outcome.reason} after {ATTEMPTS} attempts")
            wait = outcome.retry_after
            self._sleep(BACKOFF_SECONDS[attempt - 1] if wait is None else wait)
            attempt += 1

    def _attempt(self, path: str) -> bytes | _Retry:
        try:
            response = self._client.get(path)
        except httpx2.TimeoutException:
            return _Retry("timeout")
        except httpx2.TransportError:
            return _Retry("network error")
        if response.is_success:
            return response.content
        status = response.status_code
        if status != TOO_MANY_REQUESTS and status < SERVER_ERROR:
            raise _RequestFailedError(f"HTTP {status}")
        return _Retry(f"HTTP {status}", _retry_after(response))


def _retry_after(response: httpx2.Response) -> float | None:
    """The wait the provider asked for, when given in seconds on a 429 or 503."""
    header = response.headers.get("Retry-After", "")
    if response.status_code in RETRY_AFTER_STATUSES and header.isdigit():
        return float(header)
    return None
