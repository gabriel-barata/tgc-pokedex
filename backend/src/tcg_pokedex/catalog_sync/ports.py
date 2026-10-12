from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from tcg_pokedex.catalog_sync.domain import (
    Card,
    Failure,
    SetBatch,
    SetListing,
    StoredCatalog,
)


class ProviderUnavailableError(Exception):
    """The provider's index could not be read, so the run cannot go on."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class InvalidBatchError(Exception):
    """A set's write was rejected as a whole; none of it was stored."""


class CatalogProvider(Protocol):
    """Source of the card catalog. It never filters Pocket ids; the caller does."""

    def list_series_ids(self) -> list[str]:
        """Every series id, in provider order. Raises `ProviderUnavailableError`."""
        ...

    def list_set_ids(self, series_id: str) -> list[str]:
        """The set ids of one series, in provider order.

        Raises `ProviderUnavailableError`.
        """
        ...

    def fetch_set(self, set_id: str) -> SetListing | Failure:
        """One set with its series and card ids, or a `set` failure. Never raises."""
        ...

    def fetch_cards(self, set_id: str, card_ids: Sequence[str]) -> list[Card | Failure]:
        """One outcome per id, in request order, each card belonging to `set_id`."""
        ...


class CatalogRepository(Protocol):
    """Our own store of the catalog."""

    def load_stored(
        self, series_id: str, set_id: str, card_ids: Sequence[str]
    ) -> StoredCatalog:
        """The stored series, set and cards; missing rows are None or left out."""
        ...

    def save_set(self, batch: SetBatch, fetched_at: datetime) -> None:
        """Upsert the batch in one transaction, never deleting anything.

        Raises `InvalidBatchError`, storing nothing of the batch, when it cannot be
        written whole.
        """
        ...
