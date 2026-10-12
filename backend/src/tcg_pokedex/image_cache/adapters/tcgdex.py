import time
from collections.abc import Callable
from typing import Self
from urllib.parse import quote

import httpx2
from pydantic import BaseModel, ConfigDict, ValidationError

from tcg_pokedex.image_cache.domain import (
    ArtworkKind,
    CardImages,
    ImageFailure,
    Missing,
)
from tcg_pokedex.tcgdex.http import RequestFailedError, TcgdexHttp

EN_CARDS_URL = "https://api.tcgdex.net/v2/en/cards"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
NOT_FOUND = 404


class _EnglishCard(BaseModel):
    model_config = ConfigDict(extra="ignore")

    image: str | None = None


class TcgdexImageProvider:
    """ImageProvider on TCGdex assets, through the shared `TcgdexHttp` policy.

    Every image is requested as WebP and accepted only when it is a WebP of at most
    `MAX_IMAGE_BYTES`. A 404 is `Missing`; any other problem is an `ImageFailure`.
    `transport` and `sleep` are test seams.
    """

    def __init__(
        self,
        transport: httpx2.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = TcgdexHttp(transport=transport, sleep=sleep)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def fetch_card_images(
        self, card_id: str, base_url: str
    ) -> CardImages | Missing | ImageFailure:
        try:
            small = self._download(f"{base_url}/low.webp")
            if isinstance(small, Missing):
                return small
            large = self._download(f"{base_url}/high.webp")
        except RequestFailedError as error:
            return ImageFailure(kind="card", provider_id=card_id, reason=error.reason)
        return large if isinstance(large, Missing) else CardImages(small, large)

    def english_image_url(self, card_id: str) -> str | ImageFailure | None:
        try:
            content = self._http.get(f"{EN_CARDS_URL}/{quote(card_id, safe='')}")
        except RequestFailedError as error:
            if error.status == NOT_FOUND:
                return None
            return ImageFailure(kind="card", provider_id=card_id, reason=error.reason)
        try:
            return _EnglishCard.model_validate_json(content).image
        except ValidationError:
            return ImageFailure(
                kind="card", provider_id=card_id, reason="invalid payload"
            )

    def fetch_artwork(
        self, set_id: str, kind: ArtworkKind, url: str
    ) -> bytes | Missing | ImageFailure:
        try:
            return self._download(f"{url}.webp")
        except RequestFailedError as error:
            return ImageFailure.of_artwork(set_id, kind, error.reason)

    def _download(self, url: str) -> bytes | Missing:
        """The WebP at `url`. Raises `RequestFailedError`, also for a bad body."""
        try:
            content = self._http.get(url)
        except RequestFailedError as error:
            if error.status == NOT_FOUND:
                return Missing()
            raise
        if len(content) > MAX_IMAGE_BYTES:
            raise RequestFailedError("too large")
        if content[:4] != b"RIFF" or content[8:12] != b"WEBP":
            raise RequestFailedError("not an image")
        return content
