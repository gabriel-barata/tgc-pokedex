import json
from datetime import date

import pytest

from tcg_pokedex.catalog_sync.adapters.tcgdex_payloads import (
    parse_card,
    parse_series_ids,
    parse_set,
    parse_set_ids,
)
from tcg_pokedex.catalog_sync.domain import Card, Series, SetListing, Variant
from tests.catalog_sync.builders import make_card, make_set
from tests.catalog_sync.tcgdex_fixtures import FIXTURES, SV01_CARD_IDS


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def edited(fixture_name: str, /, **changes: object) -> bytes:
    payload: dict[str, object] = json.loads(fixture(fixture_name))
    payload.update(changes)
    return json.dumps(payload).encode()


def without(fixture_name: str, *keys: str) -> bytes:
    payload: dict[str, object] = json.loads(fixture(fixture_name))
    for key in keys:
        del payload[key]
    return json.dumps(payload).encode()


def parsed_set(content: bytes) -> SetListing:
    listing = parse_set(content)
    assert isinstance(listing, SetListing)
    return listing


def parsed_card(content: bytes, set_id: str = "sv01") -> Card:
    card = parse_card(content, set_id=set_id)
    assert isinstance(card, Card)
    return card


def test_series_list_maps_to_ids_in_provider_order() -> None:
    assert parse_series_ids(fixture("series.json")) == [
        "base",
        "xy",
        "swsh",
        "sv",
        "tcgp",
    ]


def test_series_detail_maps_to_its_set_ids() -> None:
    assert parse_set_ids(fixture("series/swsh.json")) == ["swshp", "swsh4.5"]
    assert parse_set_ids(fixture("series/tcgp.json")) == ["A1"]


def test_set_detail_maps_to_a_listing() -> None:
    listing = parsed_set(fixture("sets/sv01.json"))

    assert listing.card_set == make_set()
    assert listing.series == Series(id="sv", name="Escarlate e Violeta")
    assert listing.card_ids == SV01_CARD_IDS


def test_set_counts_and_date_come_from_the_set_detail() -> None:
    card_set = parsed_set(fixture("sets/swshp.json")).card_set

    assert card_set.release_date == date(2019, 11, 15)
    assert (card_set.official_count, card_set.total_count) == (307, 307)


def test_empty_set_maps_to_no_card_ids() -> None:
    listing = parsed_set(fixture("sets/base1.json"))

    assert listing.card_ids == ()
    assert listing.card_set.logo_url is None
    assert listing.card_set.symbol_url is None


def test_set_without_a_logo_keeps_its_symbol() -> None:
    card_set = parsed_set(fixture("sets/xy0.json")).card_set

    assert card_set.logo_url is None
    assert card_set.symbol_url == "https://assets.tcgdex.net/univ/xy/xy0/symbol"


def test_set_name_is_trimmed() -> None:
    assert parsed_set(fixture("sets/swsh4.5.json")).card_set.name == (
        "Destinos Brilhantes"
    )


def test_text_in_a_set_is_trimmed() -> None:
    content = edited(
        "sets/sv01.json",
        id=" sv01 ",
        serie={"id": " sv", "name": "Escarlate e Violeta  "},
        logo=" https://assets.tcgdex.net/pt/sv/sv01/logo ",
    )

    listing = parsed_set(content)

    assert listing.card_set == make_set()
    assert listing.series == Series(id="sv", name="Escarlate e Violeta")


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_logo_and_symbol_are_absent(blank: str) -> None:
    card_set = parsed_set(edited("sets/sv01.json", logo=blank, symbol=blank)).card_set

    assert card_set.logo_url is None
    assert card_set.symbol_url is None


def test_card_detail_maps_to_a_card() -> None:
    assert parsed_card(fixture("cards/sv01-001.json")) == make_card()


def test_non_numeric_collector_number_is_kept_verbatim() -> None:
    card = parsed_card(fixture("cards/swshp-SWSH158.json"), set_id="swshp")

    assert card.collector_number == "SWSH158"
    assert card.name == "Greninja V-UNIÃO"
    assert card.rarity == "Promo"
    assert card.image_url is None
    assert card.variants == frozenset({Variant.HOLO})


def test_none_rarity_is_absent() -> None:
    card = parsed_card(fixture("cards/xy0-1.json"), set_id="xy0")

    assert card.rarity is None
    assert card.illustrator == "Akira Komayama"


@pytest.mark.parametrize("blank", ["", "   ", " None "])
def test_blank_rarity_is_absent(blank: str) -> None:
    assert parsed_card(edited("cards/sv01-001.json", rarity=blank)).rarity is None


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_illustrator_and_image_are_absent(blank: str) -> None:
    card = parsed_card(edited("cards/sv01-001.json", illustrator=blank, image=blank))

    assert card.illustrator is None
    assert card.image_url is None


def test_absent_rarity_illustrator_and_image_are_absent() -> None:
    card = parsed_card(without("cards/sv01-001.json", "rarity", "illustrator", "image"))

    assert (card.rarity, card.illustrator, card.image_url) == (None, None, None)


def test_text_in_a_card_is_trimmed() -> None:
    content = edited(
        "cards/sv01-001.json",
        id="sv01-001 ",
        localId=" 001",
        name=" Pineco ",
        rarity="Comum ",
        illustrator=" Shigenori Negishi",
        image="https://assets.tcgdex.net/pt/sv/sv01/001 ",
    )

    assert parsed_card(content) == make_card()


def test_every_variant_flag_maps_to_its_variant() -> None:
    content = edited(
        "cards/sv01-001.json",
        variants={
            "normal": True,
            "reverse": True,
            "holo": True,
            "firstEdition": True,
            "wPromo": True,
        },
    )

    assert parsed_card(content).variants == frozenset(Variant)


def test_first_edition_and_w_promo_flags_map_alone() -> None:
    first_edition = edited(
        "cards/sv01-001.json",
        variants={"normal": False, "reverse": False, "firstEdition": True},
    )
    w_promo = edited("cards/sv01-001.json", variants={"wPromo": True})

    assert parsed_card(first_edition).variants == {Variant.FIRST_EDITION}
    assert parsed_card(w_promo).variants == {Variant.W_PROMO}


def test_the_card_belongs_to_the_set_being_synced() -> None:
    card = parsed_card(fixture("cards/sv01-001.json"), set_id="sv01-copy")

    assert card.set_id == "sv01-copy"
