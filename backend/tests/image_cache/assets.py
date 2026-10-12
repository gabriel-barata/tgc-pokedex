"""Recorded image-cache answers and the TCGdex URLs that serve them."""

from collections.abc import Mapping, Sequence
from pathlib import Path

from tests.tcgdex.fixtures import Reply

FIXTURES = Path(__file__).parent / "fixtures"
PIXEL = (FIXTURES / "pixel.webp").read_bytes()
EN_API = "https://api.tcgdex.net/v2/en/cards"


def image(base_url: str) -> dict[str, Sequence[Reply]]:
    """Both sizes of a card image, served once each."""
    return {
        f"{base_url}/low.webp": (Reply(body=PIXEL),),
        f"{base_url}/high.webp": (Reply(body=PIXEL),),
    }


def english(card_id: str, fixture: str | None = None) -> Mapping[str, Sequence[Reply]]:
    """The English card lookup, answered from a recorded payload or with a 404."""
    reply = Reply(fixture=FIXTURES / "en" / fixture) if fixture else Reply(404)
    return {f"{EN_API}/{card_id}": (reply,)}
