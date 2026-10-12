"""Contract every ImageProvider must honour, run against the fake and TCGdex.

Both serve the same assets: the TCGdex adapter through recorded answers.
"""

from collections.abc import Callable

import httpx2
import pytest

from tcg_pokedex.image_cache.adapters.tcgdex import TcgdexImageProvider
from tcg_pokedex.image_cache.domain import (
    ArtworkKind,
    CardImages,
    ImageFailure,
    Missing,
)
from tcg_pokedex.image_cache.fakes import InMemoryImageProvider
from tcg_pokedex.image_cache.ports import ImageProvider
from tests.image_cache.assets import PIXEL, english, image
from tests.tcgdex.fixtures import FixtureRoutes, Reply, SleepRecorder, failing

PT_IMAGE = "https://assets.tcgdex.net/pt/sv/sv01/001"
NO_IMAGE = "https://assets.tcgdex.net/pt/sv/sv01/002"
BROKEN_IMAGE = "https://assets.tcgdex.net/pt/sv/sv01/003"
EN_IMAGE = "https://assets.tcgdex.net/en/swsh/swshp/SWSH032"
LOGO = "https://assets.tcgdex.net/pt/sv/sv01/logo"
NO_LOGO = "https://assets.tcgdex.net/pt/sv/sv02/logo"
SERVER_ERROR = "HTTP 500 after 3 attempts"


def fake(_request: pytest.FixtureRequest) -> ImageProvider:
    provider = InMemoryImageProvider()
    provider.add_image(PT_IMAGE, CardImages(PIXEL, PIXEL))
    provider.fail(BROKEN_IMAGE, SERVER_ERROR)
    provider.add_english("swshp-SWSH032", EN_IMAGE)
    provider.add_artwork(LOGO, PIXEL)
    return provider


def tcgdex(request: pytest.FixtureRequest) -> ImageProvider:
    routes = FixtureRoutes(
        {
            **image(PT_IMAGE),
            f"{NO_IMAGE}/low.webp": (Reply(404),),
            f"{BROKEN_IMAGE}/low.webp": failing(500),
            **english("swshp-SWSH032", "swshp-SWSH032.json"),
            **english("svp-085", "svp-085.no-image.json"),
            **english("xy1-001"),
            f"{LOGO}.webp": (Reply(body=PIXEL),),
            f"{NO_LOGO}.webp": (Reply(404),),
        }
    )
    provider = TcgdexImageProvider(
        transport=httpx2.MockTransport(routes), sleep=SleepRecorder()
    )
    request.addfinalizer(provider.close)
    return provider


@pytest.fixture(params=[fake, tcgdex], ids=["fake", "tcgdex"])
def provider(request: pytest.FixtureRequest) -> ImageProvider:
    factory: Callable[[pytest.FixtureRequest], ImageProvider] = request.param
    return factory(request)


def test_card_images_come_in_both_sizes_or_not_at_all(provider: ImageProvider) -> None:
    assert provider.fetch_card_images("sv01-001", PT_IMAGE) == CardImages(PIXEL, PIXEL)
    assert provider.fetch_card_images("sv01-002", NO_IMAGE) == Missing()
    assert provider.fetch_card_images("sv01-003", BROKEN_IMAGE) == ImageFailure(
        kind="card", provider_id="sv01-003", reason=SERVER_ERROR
    )


def test_english_image_url_or_none(provider: ImageProvider) -> None:
    assert provider.english_image_url("swshp-SWSH032") == EN_IMAGE
    assert provider.english_image_url("svp-085") is None
    assert provider.english_image_url("xy1-001") is None


def test_artwork_or_missing(provider: ImageProvider) -> None:
    assert provider.fetch_artwork("sv01", ArtworkKind.LOGO, LOGO) == PIXEL
    assert provider.fetch_artwork("sv02", ArtworkKind.LOGO, NO_LOGO) == Missing()
