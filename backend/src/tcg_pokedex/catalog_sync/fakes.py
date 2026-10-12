"""In-memory fakes of the catalog-sync ports, shared by every test."""

from collections.abc import Iterable, Sequence
from dataclasses import replace
from datetime import datetime

from tcg_pokedex.catalog_sync.domain import (
    Card,
    CardSet,
    Failure,
    Fetched,
    Series,
    SetBatch,
    SetListing,
    StoredCatalog,
)
from tcg_pokedex.catalog_sync.ports import InvalidBatchError, ProviderUnavailableError


class InMemoryCatalogProvider:
    """CatalogProvider serving a seeded catalog and scripted failures.

    `requests` records each call as the TCGdex path it stands for, e.g. `sets/sv01`.
    """

    def __init__(self) -> None:
        self._set_ids: dict[str, list[str]] = {}
        self._listings: dict[str, SetListing] = {}
        self._cards: dict[str, Card] = {}
        self._failed_sets: dict[str, str] = {}
        self._failed_cards: dict[str, str] = {}
        self._index_down: dict[str | None, str] = {}
        self.requests: list[str] = []

    def add_series(self, series_id: str, set_ids: Iterable[str] = ()) -> None:
        self._set_ids.setdefault(series_id, []).extend(set_ids)

    def add_set(self, listing: SetListing, cards: Iterable[Card] = ()) -> None:
        """List the set in its series and serve it with these cards."""
        self.add_series(listing.series.id, [listing.card_set.id])
        self._listings[listing.card_set.id] = listing
        self._cards.update((card.id, card) for card in cards)

    def fail_set(self, series_id: str, set_id: str, reason: str) -> None:
        self.add_series(series_id, [set_id])
        self._failed_sets[set_id] = reason

    def fail_card(self, card_id: str, reason: str) -> None:
        self._failed_cards[card_id] = reason

    def take_down(self, reason: str, series_id: str | None = None) -> None:
        """Make the series list, or one series' set list, unavailable."""
        self._index_down[series_id] = reason

    def list_series_ids(self) -> list[str]:
        self.requests.append("series")
        if None in self._index_down:
            raise ProviderUnavailableError(self._index_down[None])
        return list(self._set_ids)

    def list_set_ids(self, series_id: str) -> list[str]:
        self.requests.append(f"series/{series_id}")
        if series_id in self._index_down:
            raise ProviderUnavailableError(self._index_down[series_id])
        return list(self._set_ids[series_id])

    def fetch_set(self, set_id: str) -> SetListing | Failure:
        self.requests.append(f"sets/{set_id}")
        if set_id in self._failed_sets:
            return Failure(
                kind="set", provider_id=set_id, reason=self._failed_sets[set_id]
            )
        return self._listings[set_id]

    def fetch_cards(self, set_id: str, card_ids: Sequence[str]) -> list[Card | Failure]:
        return [self._fetch_card(set_id, card_id) for card_id in card_ids]

    def _fetch_card(self, set_id: str, card_id: str) -> Card | Failure:
        self.requests.append(f"cards/{card_id}")
        if card_id in self._failed_cards:
            return Failure(
                kind="card", provider_id=card_id, reason=self._failed_cards[card_id]
            )
        return replace(self._cards[card_id], set_id=set_id)


class InMemoryCatalogRepository:
    """CatalogRepository holding rows in dicts."""

    def __init__(self) -> None:
        self.series: dict[str, Fetched[Series]] = {}
        self.sets: dict[str, Fetched[CardSet]] = {}
        self.cards: dict[str, Fetched[Card]] = {}

    def load_stored(
        self, series_id: str, set_id: str, card_ids: Sequence[str]
    ) -> StoredCatalog:
        return StoredCatalog(
            series=self.series.get(series_id),
            card_set=self.sets.get(set_id),
            cards={
                card_id: self.cards[card_id]
                for card_id in card_ids
                if card_id in self.cards
            },
        )

    def save_set(self, batch: SetBatch, fetched_at: datetime) -> None:
        series_id = batch.card_set.series_id
        in_batch = batch.series is not None and batch.series.id == series_id
        if not in_batch and series_id not in self.series:
            raise InvalidBatchError(f"unknown series {series_id!r}")
        if batch.series:
            self.series[batch.series.id] = Fetched(batch.series, fetched_at)
        self.sets[batch.card_set.id] = Fetched(batch.card_set, fetched_at)
        self.cards.update((card.id, Fetched(card, fetched_at)) for card in batch.cards)
