from collections.abc import Mapping, Sequence
from importlib.metadata import version

import httpx2

from tcg_pokedex.image_cache.adapters.tcgdex import MAX_IMAGE_BYTES, TcgdexImageProvider
from tcg_pokedex.image_cache.domain import CardImages, ImageFailure, Missing
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
