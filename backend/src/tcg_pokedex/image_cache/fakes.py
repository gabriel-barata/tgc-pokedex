"""In-memory fakes of the image-cache ports, shared by every test."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from tcg_pokedex.image_cache.domain import (
    ArtworkKind,
    ArtworkToFetch,
    CardImages,
    CardToResolve,
    Language,
    SetTracking,
    StoredCardImage,
)
from tcg_pokedex.image_cache.ports import ImageStoreUnavailableError


class InMemoryImageStore:
    """ImageStore keeping files in dicts. `writable=False` is a bad directory."""

    def __init__(self, *, writable: bool = True) -> None:
        self._writable = writable
        self.cards: dict[str, CardImages] = {}
        self.artwork: dict[tuple[str, ArtworkKind], bytes] = {}

    def check_writable(self) -> None:
        if not self._writable:
            raise ImageStoreUnavailableError("image directory is not writable")

    def has_card(self, card_id: str) -> bool:
        return card_id in self.cards

    def put_card(self, card_id: str, images: CardImages) -> None:
        self.cards[card_id] = images

    def put_artwork(self, set_id: str, kind: ArtworkKind, content: bytes) -> None:
        self.artwork[set_id, kind] = content


@dataclass(frozen=True)
class _CatalogSet:
    logo_url: str | None
    symbol_url: str | None


@dataclass(frozen=True)
class _CatalogCard:
    set_id: str
    image_url: str | None


class InMemoryImageCacheRepository:
    """ImageCacheRepository on dicts. Seed the catalog with `add_set` and `add_card`.

    Sets keep the order they were added in, which stands for catalog order.
    """

    def __init__(self) -> None:
        self._sets: dict[str, _CatalogSet] = {}
        self._cards: dict[str, _CatalogCard] = {}
        self.tracked: dict[tuple[UUID, str], datetime] = {}
        self.card_images: dict[str, StoredCardImage] = {}
        self.artwork: dict[tuple[str, ArtworkKind], datetime] = {}

    def add_set(
        self, set_id: str, logo_url: str | None = None, symbol_url: str | None = None
    ) -> None:
        self._sets[set_id] = _CatalogSet(logo_url, symbol_url)

    def add_card(self, card_id: str, set_id: str, image_url: str | None) -> None:
        self._cards[card_id] = _CatalogCard(set_id, image_url)

    def set_exists(self, set_id: str) -> bool:
        return set_id in self._sets

    def track(self, owner_id: UUID, set_id: str, at: datetime) -> bool:
        if (owner_id, set_id) in self.tracked:
            return False
        self.tracked[owner_id, set_id] = at
        return True

    def untrack(self, owner_id: UUID, set_id: str) -> None:
        self.tracked.pop((owner_id, set_id), None)

    def progress(self, owner_id: UUID, set_id: str) -> SetTracking:
        stored = [self.card_images.get(card_id) for card_id in self._card_ids(set_id)]
        return SetTracking(
            set_id=set_id,
            tracked=(owner_id, set_id) in self.tracked,
            total_cards=len(stored),
            cached=sum(1 for row in stored if row and row.language),
            unavailable=sum(1 for row in stored if row and row.language is None),
            downloading=False,
        )

    def tracked_set_ids(self) -> list[str]:
        tracked = {set_id for _, set_id in self.tracked}
        return [set_id for set_id in self._sets if set_id in tracked]

    def cards_to_resolve(self, set_id: str) -> list[CardToResolve]:
        return [
            CardToResolve(
                card_id=card_id,
                pt_image_url=self._cards[card_id].image_url,
                stored=self.card_images.get(card_id),
            )
            for card_id in self._card_ids(set_id)
        ]

    def save_card_images(
        self, rows: Sequence[tuple[str, Language | None]], fetched_at: datetime
    ) -> None:
        for card_id, language in rows:
            self.card_images[card_id] = StoredCardImage(language, fetched_at)

    def artwork_to_fetch(self) -> list[ArtworkToFetch]:
        return [
            ArtworkToFetch(
                set_id=set_id,
                kind=kind,
                url=urls.logo_url if kind is ArtworkKind.LOGO else urls.symbol_url,
                cached=(set_id, kind) in self.artwork,
            )
            for set_id, urls in self._sets.items()
            for kind in ArtworkKind
        ]

    def save_artwork(
        self, set_id: str, kind: ArtworkKind, fetched_at: datetime
    ) -> None:
        self.artwork[set_id, kind] = fetched_at

    def _card_ids(self, set_id: str) -> list[str]:
        return sorted(
            card_id for card_id, card in self._cards.items() if card.set_id == set_id
        )
