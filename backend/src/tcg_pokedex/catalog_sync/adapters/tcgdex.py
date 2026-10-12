import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from importlib.metadata import version
from typing import Self

import httpx2

from tcg_pokedex.catalog_sync.adapters.tcgdex_payloads import (
    parse_card,
    parse_series_ids,
    parse_set,
    parse_set_ids,
)
from tcg_pokedex.catalog_sync.domain import Card, Failure, SetListing

BASE_URL = "https://api.tcgdex.net/v2/pt"
REPOSITORY_URL = "https://github.com/gabriel-barata/tgc-pokedex"
USER_AGENT = f"tcg-pokedex/{version('tcg-pokedex')} (+{REPOSITORY_URL})"
TIMEOUT_SECONDS = 10
MAX_IN_FLIGHT = 8


class TcgdexProvider:
    """CatalogProvider reading the Portuguese TCGdex API.

    Card requests run on up to `MAX_IN_FLIGHT` threads sharing one client; index and
    set requests run one at a time. `transport` and `sleep` are test seams.
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
        return parse_series_ids(self._get("/series"))

    def list_set_ids(self, series_id: str) -> list[str]:
        return parse_set_ids(self._get(f"/series/{series_id}"))

    def fetch_set(self, set_id: str) -> SetListing | Failure:
        return parse_set(self._get(f"/sets/{set_id}"), set_id)

    def fetch_cards(self, set_id: str, card_ids: Sequence[str]) -> list[Card | Failure]:
        with ThreadPoolExecutor(max_workers=MAX_IN_FLIGHT) as pool:
            return list(pool.map(partial(self._fetch_card, set_id), card_ids))

    def _fetch_card(self, set_id: str, card_id: str) -> Card | Failure:
        return parse_card(self._get(f"/cards/{card_id}"), card_id, set_id=set_id)

    def _get(self, path: str) -> bytes:
        response = self._client.get(path)
        response.raise_for_status()
        return response.content
