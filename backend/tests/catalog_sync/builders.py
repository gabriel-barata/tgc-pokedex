"""Shared builders for catalog-sync domain objects, with overridable defaults."""

from collections.abc import Iterable
from datetime import date

from tcg_pokedex.catalog_sync.domain import (
    Card,
    CardSet,
    Series,
    SetListing,
    Variant,
)


def make_series(*, id: str = "sv", name: str = "Escarlate e Violeta") -> Series:
    return Series(id=id, name=name)


def make_set(
    *,
    id: str = "sv01",
    series_id: str = "sv",
    name: str = "Escarlate e Violeta",
    release_date: date = date(2023, 3, 31),
    official_count: int = 198,
    total_count: int = 258,
    logo_url: str | None = "https://assets.tcgdex.net/pt/sv/sv01/logo",
    symbol_url: str | None = "https://assets.tcgdex.net/univ/sv/sv01/symbol",
) -> CardSet:
    return CardSet(
        id=id,
        series_id=series_id,
        name=name,
        release_date=release_date,
        official_count=official_count,
        total_count=total_count,
        logo_url=logo_url,
        symbol_url=symbol_url,
    )


def make_card(
    *,
    id: str = "sv01-001",
    set_id: str = "sv01",
    collector_number: str = "001",
    name: str = "Pineco",
    rarity: str | None = "Comum",
    illustrator: str | None = "Shigenori Negishi",
    image_url: str | None = "https://assets.tcgdex.net/pt/sv/sv01/001",
    variants: Iterable[Variant] = (Variant.NORMAL, Variant.REVERSE),
) -> Card:
    return Card(
        id=id,
        set_id=set_id,
        collector_number=collector_number,
        name=name,
        rarity=rarity,
        illustrator=illustrator,
        image_url=image_url,
        variants=frozenset(variants),
    )


def make_listing(
    *,
    card_set: CardSet | None = None,
    series: Series | None = None,
    card_ids: Iterable[str] = (),
) -> SetListing:
    card_set = card_set or make_set()
    series = series or make_series(id=card_set.series_id)
    return SetListing(card_set=card_set, series=series, card_ids=tuple(card_ids))
