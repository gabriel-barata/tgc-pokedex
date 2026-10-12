"""TCGdex image adapter cases beyond the ImageProvider contract.

Symbol URLs (FIX-1): the catalog stores every set symbol under `/univ/`. Re-probed
with `curl -sI` on 2026-10-12: `https://assets.tcgdex.net/univ/sv/sv01/symbol.webp`
answered 404 and `https://assets.tcgdex.net/pt/sv/sv01/symbol.webp` answered 200.
"""

from collections.abc import Mapping, Sequence
from importlib.metadata import version

import httpx2

from tcg_pokedex.image_cache.adapters.tcgdex import MAX_IMAGE_BYTES, TcgdexImageProvider
from tcg_pokedex.image_cache.domain import (
    ArtworkKind,
    CardImages,
    ImageFailure,
    Missing,
)
from tests.image_cache.assets import PIXEL, image
from tests.tcgdex.fixtures import FixtureRoutes, Reply, SleepRecorder

BASE = "https://assets.tcgdex.net/pt/sv/sv01/001"


def fetch(
    routes: Mapping[str, Sequence[Reply]],
) -> tuple[CardImages | Missing | ImageFailure, FixtureRoutes]:
    served = FixtureRoutes(routes)
    with TcgdexImageProvider(
        transport=httpx2.MockTransport(served), sleep=SleepRecorder()
    ) as provider:
        return provider.fetch_card_images("sv01-001", BASE), served


def test_both_sizes_are_requested_with_the_app_user_agent() -> None:
    _, served = fetch(image(BASE))

    assert [str(request.url) for request in served.requests] == [
        f"{BASE}/low.webp",
        f"{BASE}/high.webp",
    ]
    assert (
        served.requests[0]
        .headers["User-Agent"]
        .startswith(f"tcg-pokedex/{version('tcg-pokedex')} ")
    )


def test_a_body_that_is_not_a_small_webp_is_a_failure() -> None:
    html = Reply(body=b"<html>oops</html>")
    huge = Reply(body=PIXEL + b"\0" * MAX_IMAGE_BYTES)

    not_an_image, _ = fetch({f"{BASE}/low.webp": (html,)})
    too_large, _ = fetch({f"{BASE}/low.webp": (huge,)})

    assert not_an_image == ImageFailure(
        kind="card", provider_id="sv01-001", reason="not an image"
    )
    assert too_large == ImageFailure(
        kind="card", provider_id="sv01-001", reason="too large"
    )


UNIV = "https://assets.tcgdex.net/univ/sv/sv01"
PT = "https://assets.tcgdex.net/pt/sv/sv01"


def fetch_artwork(
    kind: ArtworkKind, url: str, routes: Mapping[str, Sequence[Reply]]
) -> tuple[bytes | Missing | ImageFailure, FixtureRoutes]:
    served = FixtureRoutes(routes)
    with TcgdexImageProvider(
        transport=httpx2.MockTransport(served), sleep=SleepRecorder()
    ) as provider:
        return provider.fetch_artwork("sv01", kind, url), served


def test_a_univ_symbol_that_answers_404_is_fetched_from_pt() -> None:
    symbol, _ = fetch_artwork(
        ArtworkKind.SYMBOL,
        f"{UNIV}/symbol",
        {
            f"{UNIV}/symbol.webp": (Reply(404),),
            f"{PT}/symbol.webp": (Reply(body=PIXEL),),
        },
    )

    assert symbol == PIXEL


def test_only_symbols_are_retried_and_only_once() -> None:
    logo, logo_served = fetch_artwork(
        ArtworkKind.LOGO, f"{UNIV}/logo", {f"{UNIV}/logo.webp": (Reply(404),)}
    )
    symbol, _ = fetch_artwork(
        ArtworkKind.SYMBOL,
        f"{UNIV}/symbol",
        {f"{UNIV}/symbol.webp": (Reply(404),), f"{PT}/symbol.webp": (Reply(404),)},
    )

    assert logo == Missing()
    assert len(logo_served.requests) == 1
    assert symbol == Missing()
