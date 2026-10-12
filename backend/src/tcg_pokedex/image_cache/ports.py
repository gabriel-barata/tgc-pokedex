from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from tcg_pokedex.image_cache.domain import (
    ArtworkKind,
    ArtworkToFetch,
    CardImages,
    CardToResolve,
    ImageFailure,
    Language,
    Missing,
    SetTracking,
)


class ImageStoreUnavailableError(Exception):
    """The image directory cannot be created or written, so no run can go on."""


class ImageProvider(Protocol):
    """Source of card images and set artwork.

    Thread-safe. Never raises for one asset: every outcome is a value.
    """

    def fetch_card_images(
        self, card_id: str, base_url: str
    ) -> CardImages | Missing | ImageFailure:
        """Both sizes of the image at `base_url`, `Missing` when either is absent."""
        ...

    def english_image_url(self, card_id: str) -> str | ImageFailure | None:
        """The English card's image base URL, None when it has none."""
        ...

    def fetch_artwork(
        self, set_id: str, kind: ArtworkKind, url: str
    ) -> bytes | Missing | ImageFailure: ...


class ImageStore(Protocol):
    """Where image files live. Thread-safe; every write is atomic."""

    def check_writable(self) -> None:
        """Create the store if needed. Raises `ImageStoreUnavailableError`."""
        ...

    def has_card(self, card_id: str) -> bool:
        """Both sizes of the card are stored."""
        ...

    def put_card(self, card_id: str, images: CardImages) -> None: ...

    def put_artwork(self, set_id: str, kind: ArtworkKind, content: bytes) -> None: ...


class ImageCacheRepository(Protocol):
    """Our own store of tracked sets and of which images are cached."""

    def set_exists(self, set_id: str) -> bool: ...

    def track(self, owner_id: UUID, set_id: str, at: datetime) -> bool:
        """Track the set; True only when the owner did not track it yet."""
        ...

    def untrack(self, owner_id: UUID, set_id: str) -> None: ...

    def progress(self, owner_id: UUID, set_id: str) -> SetTracking:
        """The set's tracking and image counts; `downloading` is always False."""
        ...

    def tracked_set_ids(self) -> list[str]:
        """Sets tracked by any owner, in catalog order."""
        ...

    def cards_to_resolve(self, set_id: str) -> list[CardToResolve]:
        """Each card of the set with its pt image URL and stored image row.

        `files_present` is left False; the caller fills it in from the image store.
        """
        ...

    def save_card_images(
        self, rows: Sequence[tuple[str, Language | None]], fetched_at: datetime
    ) -> None:
        """Upsert one row per card id in one transaction; None means unavailable."""
        ...

    def artwork_to_fetch(self) -> list[ArtworkToFetch]:
        """Every stored set's logo and symbol, with its URL and whether it is cached."""
        ...

    def save_artwork(
        self, set_id: str, kind: ArtworkKind, fetched_at: datetime
    ) -> None: ...
