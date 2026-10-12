import json

from tcg_pokedex.catalog_sync.adapters.tcgdex_payloads import parse_card, parse_set
from tcg_pokedex.catalog_sync.domain import Failure, Series, SetListing
from tests.catalog_sync.builders import make_card, make_set
from tests.catalog_sync.tcgdex_fixtures import FIXTURES


def card_payload(*removed: str, **changes: object) -> bytes:
    payload: dict[str, object] = json.loads(
        (FIXTURES / "cards/sv01-001.json").read_bytes()
    )
    payload.update(changes)
    for key in removed:
        del payload[key]
    return json.dumps(payload).encode()


def test_set_detail_maps_to_a_listing() -> None:
    listing = parse_set((FIXTURES / "sets/sv01.json").read_bytes(), "sv01")

    assert listing == SetListing(
        card_set=make_set(),
        series=Series(id="sv", name="Escarlate e Violeta"),
        card_ids=("sv01-001", "sv01-002"),
    )


def test_card_detail_maps_to_a_card_of_the_synced_set() -> None:
    card = parse_card(card_payload(), "sv01-001", set_id="sv01-copy")

    assert card == make_card(set_id="sv01-copy")


def test_blank_text_and_none_rarity_are_absent() -> None:
    card = parse_card(
        card_payload(name=" Pineco ", rarity="None", illustrator="", image="  "),
        "sv01-001",
        set_id="sv01",
    )

    assert card == make_card(rarity=None, illustrator=None, image_url=None)


def test_an_invalid_card_is_a_failure() -> None:
    nameless = card_payload("name")
    no_variants = card_payload(variants={"normal": False})

    assert parse_card(nameless, "sv01-001", "sv01") == Failure(
        kind="card",
        provider_id="sv01-001",
        reason="invalid payload: name: Field required",
    )
    assert parse_card(no_variants, "sv01-001", "sv01") == Failure(
        kind="card", provider_id="sv01-001", reason="no variants"
    )
