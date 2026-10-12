import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from functools import partial
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
from tcg_pokedex.tcgdex.http import MAX_IN_FLIGHT, RequestFailedError, TcgdexHttp

BASE_URL = "https://api.tcgdex.net/v2/pt"


class TcgdexProvider:
    """CatalogProvider reading the Portuguese TCGdex API.

    Card requests run on up to `MAX_IN_FLIGHT` threads; index and set requests run one
    at a time. Retries and limits come from the shared `TcgdexHttp`. `transport` and
    `sleep` are test seams.
    """

    def __init__(
        self,
        transport: httpx2.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = TcgdexHttp(transport=transport, sleep=sleep)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def list_series_ids(self) -> list[str]:
        return self._index("/series", parse_series_ids)

    def list_set_ids(self, series_id: str) -> list[str]:
        return self._index(f"/series/{series_id}", parse_set_ids)

    def fetch_set(self, set_id: str) -> SetListing | Failure:
        try:
            content = self._get(f"/sets/{set_id}")
        except RequestFailedError as error:
            return Failure(kind="set", provider_id=set_id, reason=error.reason)
        return parse_set(content, set_id)

    def fetch_cards(self, set_id: str, card_ids: Sequence[str]) -> list[Card | Failure]:
        with ThreadPoolExecutor(max_workers=MAX_IN_FLIGHT) as pool:
            return list(pool.map(partial(self._fetch_card, set_id), card_ids))

    def _fetch_card(self, set_id: str, card_id: str) -> Card | Failure:
        try:
            content = self._get(f"/cards/{card_id}")
        except RequestFailedError as error:
            return Failure(kind="card", provider_id=card_id, reason=error.reason)
        return parse_card(content, card_id, set_id=set_id)

    def _index(self, path: str, parse: Callable[[bytes], list[str]]) -> list[str]:
        try:
            return parse(self._get(path))
        except RequestFailedError as error:
            raise ProviderUnavailableError(error.reason) from error
        except ValidationError as error:
            raise ProviderUnavailableError(invalid_payload(error)) from error

    def _get(self, path: str) -> bytes:
        return self._http.get(f"{BASE_URL}{path}")
