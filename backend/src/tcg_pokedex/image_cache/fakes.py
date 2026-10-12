"""In-memory fakes of the image-cache ports, shared by every test."""

from tcg_pokedex.image_cache.domain import ArtworkKind, CardImages
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
