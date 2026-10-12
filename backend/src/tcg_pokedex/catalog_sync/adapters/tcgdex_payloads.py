"""TCGdex payload schemas and their mapping to catalog entities.

The only provider-to-domain mapping. Every payload is validated here: text is trimmed,
required text must be non-empty, and blank optional text becomes None. An invalid set
or card payload becomes a `Failure`; an invalid index payload raises `ValidationError`.
"""

from datetime import date
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from tcg_pokedex.catalog_sync.domain import (
    Card,
    CardSet,
    Failure,
    Series,
    SetListing,
    Variant,
)

NO_VARIANTS = "no variants"


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


_SERIES_LIST = TypeAdapter(tuple[_Ref, ...])


def parse_series_ids(content: bytes) -> list[str]:
    return [series.id for series in _SERIES_LIST.validate_json(content)]


def parse_set_ids(content: bytes) -> list[str]:
    return [card_set.id for card_set in _SeriesDetail.model_validate_json(content).sets]


def invalid_payload(error: ValidationError) -> str:
    """The failure reason for a payload: its first error and that field's path."""
    first = error.errors(include_url=False)[0]
    field = ".".join(str(part) for part in first["loc"]) or "body"
    return f"invalid payload: {field}: {first['msg']}"


def parse_set(content: bytes, set_id: str) -> SetListing | Failure:
    """Map a set detail, or fail the requested `set_id` when the payload is invalid."""
    try:
        payload = _SetDetail.model_validate_json(content)
    except ValidationError as error:
        return Failure(kind="set", provider_id=set_id, reason=invalid_payload(error))
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


def parse_card(content: bytes, card_id: str, set_id: str) -> Card | Failure:
    """Map a card detail, or fail the requested `card_id`.

    The card belongs to `set_id`; the set named in its own payload is ignored.
    """
    try:
        payload = _CardDetail.model_validate_json(content)
    except ValidationError as error:
        return Failure(kind="card", provider_id=card_id, reason=invalid_payload(error))
    variants = _variants(payload.variants)
    if not variants:
        return Failure(kind="card", provider_id=card_id, reason=NO_VARIANTS)
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


def _variants(flags: _Variants | None) -> frozenset[Variant]:
    if flags is None:
        return frozenset()
    present = {
        Variant.NORMAL: flags.normal,
        Variant.REVERSE: flags.reverse,
        Variant.HOLO: flags.holo,
        Variant.FIRST_EDITION: flags.first_edition,
        Variant.W_PROMO: flags.w_promo,
    }
    return frozenset(variant for variant, flag in present.items() if flag)
