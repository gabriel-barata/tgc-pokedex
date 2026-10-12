"""The TCGdex client: one HTTP policy, the pt catalog and every image we cache.

The only provider-to-app mapping. Every payload is validated here: text is trimmed,
required text must be non-empty, and blank optional text becomes None. Anything that
goes wrong raises `TcgdexError`, whose message is the failure reason a sync records.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from importlib.metadata import version
from typing import Annotated, Self
from urllib.parse import quote

import httpx2
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from tcg_pokedex.schemas import ArtworkKind

SOURCE = "tcgdex"
"""The provider name stored on every row and run fetched from TCGdex."""

PT_API = "https://api.tcgdex.net/v2/pt"
EN_CARDS_URL = "https://api.tcgdex.net/v2/en/cards"
REPOSITORY_URL = "https://github.com/gabriel-barata/tgc-pokedex"
USER_AGENT = f"tcg-pokedex/{version('tcg-pokedex')} (+{REPOSITORY_URL})"
TIMEOUT_SECONDS = 10
MAX_IN_FLIGHT = 8
ATTEMPTS = 3
BACKOFF_SECONDS = (1.0, 2.0)
TOO_MANY_REQUESTS = 429
NOT_FOUND = 404
SERVER_ERROR = 500
RETRY_AFTER_STATUSES = frozenset({TOO_MANY_REQUESTS, 503})
MAX_IMAGE_BYTES = 5 * 1024 * 1024
UNIVERSAL_PATH = "/univ/"
SYMBOL_FALLBACK_PATH = "/pt/"
NO_VARIANTS = "no variants"


class TcgdexError(Exception):
    """A request or payload failed. `status` is the last HTTP status, if any."""

    def __init__(self, reason: str, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


class Variant(StrEnum):
    """A printing a card exists in. Declaration order is the canonical storage order."""

    NORMAL = "normal"
    REVERSE = "reverse"
    HOLO = "holo"
    FIRST_EDITION = "first_edition"
    W_PROMO = "w_promo"


@dataclass(frozen=True)
class Series:
    id: str
    name: str


@dataclass(frozen=True)
class CardSet:
    id: str
    series_id: str
    name: str
    release_date: date
    official_count: int
    total_count: int
    logo_url: str | None
    symbol_url: str | None


@dataclass(frozen=True)
class Card:
    id: str
    set_id: str
    collector_number: str
    name: str
    rarity: str | None
    illustrator: str | None
    image_url: str | None
    variants: frozenset[Variant]


@dataclass(frozen=True)
class SetListing:
    """One set as TCGdex returns it: the set, its series and its card ids."""

    card_set: CardSet
    series: Series
    card_ids: tuple[str, ...]


@dataclass(frozen=True)
class _Retry:
    reason: str
    status: int | None = None
    retry_after: float | None = None


class Tcgdex:
    """GETs TCGdex on one client shared by every thread.

    At most `MAX_IN_FLIGHT` requests run at once. Network errors, 5xx and 429 are
    retried up to `ATTEMPTS` times, waiting `BACKOFF_SECONDS` or the provider's
    `Retry-After`; any other 4xx fails at once. `transport` and `sleep` are test seams.
    """

    def __init__(
        self,
        transport: httpx2.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = httpx2.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
            limits=httpx2.Limits(max_connections=MAX_IN_FLIGHT),
            transport=transport,
        )
        self._sleep = sleep

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self._client.close()

    def series_ids(self) -> list[str]:
        return [series.id for series in _parse(_SERIES_LIST, self._pt("/series"))]

    def set_ids(self, series_id: str) -> list[str]:
        detail = _parse(_SERIES_DETAIL, self._pt(f"/series/{series_id}"))
        return [card_set.id for card_set in detail.sets]

    def set_listing(self, set_id: str) -> SetListing:
        payload = _parse(_SET_DETAIL, self._pt(f"/sets/{set_id}"))
        return SetListing(
            card_set=CardSet(
                id=payload.id,
                series_id=payload.serie.id,
                name=payload.name,
                release_date=payload.release_date,
                official_count=payload.card_count.official,
                total_count=payload.card_count.total,
                logo_url=payload.logo,
                symbol_url=payload.symbol,
            ),
            series=Series(id=payload.serie.id, name=payload.serie.name),
            card_ids=tuple(card.id for card in payload.cards),
        )

    def card(self, card_id: str, set_id: str) -> Card:
        """The card, as a card of `set_id`; the set named in its payload is ignored."""
        return parse_card(self._pt(f"/cards/{card_id}"), set_id)

    def card_images(self, base_url: str) -> tuple[bytes, bytes] | None:
        """The small and large image at `base_url`, None when either is absent."""
        small = self._image(f"{base_url}/low.webp")
        if small is None:
            return None
        large = self._image(f"{base_url}/high.webp")
        return None if large is None else (small, large)

    def english_image_url(self, card_id: str) -> str | None:
        """The English card's image base URL, None when it has none."""
        try:
            content = self.get(f"{EN_CARDS_URL}/{quote(card_id, safe='')}")
        except TcgdexError as error:
            if error.status == NOT_FOUND:
                return None
            raise
        try:
            return _EnglishCard.model_validate_json(content).image
        except ValidationError as error:
            raise TcgdexError("invalid payload") from error

    def artwork(self, kind: ArtworkKind, url: str) -> bytes | None:
        """The artwork at `{url}.webp`, None when absent.

        TCGdex answers 404 for every symbol under `/univ/`, which is where the
        catalog points, while the same path under `/pt/` exists. Such a symbol is
        retried once there.
        """
        content = self._image(f"{url}.webp")
        if content is None and kind is ArtworkKind.SYMBOL and UNIVERSAL_PATH in url:
            fallback = url.replace(UNIVERSAL_PATH, SYMBOL_FALLBACK_PATH, 1)
            content = self._image(f"{fallback}.webp")
        return content

    def get(self, url: str) -> bytes:
        """The response body of a 2xx. Raises `TcgdexError` otherwise."""
        attempt = 1
        while True:
            outcome = self._attempt(url)
            if isinstance(outcome, bytes):
                return outcome
            if attempt == ATTEMPTS:
                raise TcgdexError(
                    f"{outcome.reason} after {ATTEMPTS} attempts", outcome.status
                )
            wait = outcome.retry_after
            self._sleep(BACKOFF_SECONDS[attempt - 1] if wait is None else wait)
            attempt += 1

    def _pt(self, path: str) -> bytes:
        return self.get(f"{PT_API}{path}")

    def _image(self, url: str) -> bytes | None:
        """The WebP at `url`, None on a 404. A body that is not a small WebP fails."""
        try:
            content = self.get(url)
        except TcgdexError as error:
            if error.status == NOT_FOUND:
                return None
            raise
        if len(content) > MAX_IMAGE_BYTES:
            raise TcgdexError("too large")
        if content[:4] != b"RIFF" or content[8:12] != b"WEBP":
            raise TcgdexError("not an image")
        return content

    def _attempt(self, url: str) -> bytes | _Retry:
        try:
            response = self._client.get(url)
        except httpx2.TimeoutException:
            return _Retry("timeout")
        except httpx2.TransportError:
            return _Retry("network error")
        if response.is_success:
            return response.content
        status = response.status_code
        if status != TOO_MANY_REQUESTS and status < SERVER_ERROR:
            raise TcgdexError(f"HTTP {status}", status)
        return _Retry(f"HTTP {status}", status, _retry_after(response))


def _retry_after(response: httpx2.Response) -> float | None:
    """The wait the provider asked for, when given in seconds on a 429 or 503."""
    header = response.headers.get("Retry-After", "")
    if response.status_code in RETRY_AFTER_STATUSES and header.isdigit():
        return float(header)
    return None


def _blank_to_none(value: str | None) -> str | None:
    return value or None


def _no_rarity_to_none(value: str | None) -> str | None:
    return None if value in {None, "", "None"} else value


class _Payload(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        alias_generator=to_camel,
        frozen=True,
    )


class _Ref(_Payload):
    id: str = Field(min_length=1)


class _NamedRef(_Ref):
    name: str = Field(min_length=1)


class _SeriesDetail(_Payload):
    sets: tuple[_Ref, ...]


class _CardCount(_Payload):
    official: int
    total: int


class _SetDetail(_NamedRef):
    release_date: date
    serie: _NamedRef
    card_count: _CardCount
    logo: Annotated[str | None, AfterValidator(_blank_to_none)] = None
    symbol: Annotated[str | None, AfterValidator(_blank_to_none)] = None
    cards: tuple[_Ref, ...]


class _Variants(_Payload):
    normal: bool = False
    reverse: bool = False
    holo: bool = False
    first_edition: bool = False
    w_promo: bool = False


class _CardDetail(_NamedRef):
    local_id: str = Field(min_length=1)
    rarity: Annotated[str | None, AfterValidator(_no_rarity_to_none)] = None
    illustrator: Annotated[str | None, AfterValidator(_blank_to_none)] = None
    image: Annotated[str | None, AfterValidator(_blank_to_none)] = None
    variants: _Variants | None = None


class _EnglishCard(BaseModel):
    model_config = ConfigDict(extra="ignore")

    image: str | None = None


_SERIES_LIST = TypeAdapter(tuple[_Ref, ...])
_SERIES_DETAIL = TypeAdapter(_SeriesDetail)
_SET_DETAIL = TypeAdapter(_SetDetail)
_CARD_DETAIL = TypeAdapter(_CardDetail)


def _parse[T](adapter: TypeAdapter[T], content: bytes) -> T:
    """Validate a payload. Raises `TcgdexError` naming its first error and field."""
    try:
        return adapter.validate_json(content)
    except ValidationError as error:
        first = error.errors(include_url=False)[0]
        field = ".".join(str(part) for part in first["loc"]) or "body"
        raise TcgdexError(f"invalid payload: {field}: {first['msg']}") from error


def parse_card(content: bytes, set_id: str) -> Card:
    payload = _parse(_CARD_DETAIL, content)
    flags = payload.variants or _Variants()
    present = {
        Variant.NORMAL: flags.normal,
        Variant.REVERSE: flags.reverse,
        Variant.HOLO: flags.holo,
        Variant.FIRST_EDITION: flags.first_edition,
        Variant.W_PROMO: flags.w_promo,
    }
    variants = frozenset(variant for variant, flag in present.items() if flag)
    if not variants:
        raise TcgdexError(NO_VARIANTS)
    return Card(
        id=payload.id,
        set_id=set_id,
        collector_number=payload.local_id,
        name=payload.name,
        rarity=payload.rarity,
        illustrator=payload.illustrator,
        image_url=payload.image,
        variants=variants,
    )
