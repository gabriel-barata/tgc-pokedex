"""The TCGdex client against recorded answers.

Symbol URLs: the catalog stores every set symbol under `/univ/`. Re-probed with
`curl -sI` on 2026-10-12: `https://assets.tcgdex.net/univ/sv/sv01/symbol.webp`
answered 404 and `https://assets.tcgdex.net/pt/sv/sv01/symbol.webp` answered 200.
"""

import json
from datetime import date
from importlib.metadata import version

import pytest

from tcg_pokedex.schemas import ArtworkKind
from tcg_pokedex.tcgdex import (
    MAX_IMAGE_BYTES,
    Card,
    CardSet,
    Series,
    SetListing,
    TcgdexError,
    Variant,
    parse_card,
)
from tests.helpers import (
    FIXTURES,
    HAPPY,
    PIXEL,
    FixtureRoutes,
    Reply,
    SleepRecorder,
    english,
    failing,
    image,
    tcgdex,
)

PINECO = Card(
    id="sv01-001",
    set_id="sv01",
    collector_number="001",
    name="Pineco",
    rarity="Comum",
    illustrator="Shigenori Negishi",
    image_url="https://assets.tcgdex.net/pt/sv/sv01/001",
    variants=frozenset({Variant.NORMAL, Variant.REVERSE}),
)
BASE = "https://assets.tcgdex.net/pt/sv/sv01/001"
UNIV = "https://assets.tcgdex.net/univ/sv/sv01"
PT = "https://assets.tcgdex.net/pt/sv/sv01"


def card_payload(*removed: str, **changes: object) -> bytes:
    payload: dict[str, object] = json.loads(
        (FIXTURES / "tcgdex" / "cards" / "sv01-001.json").read_bytes()
    )
    payload.update(changes)
    for key in removed:
        del payload[key]
    return json.dumps(payload).encode()


def test_requests_go_to_the_pt_api_and_identify_the_app() -> None:
    served = FixtureRoutes(HAPPY)

    with tcgdex(served) as client:
        card = client.card("sv01-001", "sv01")

    assert card == PINECO
    assert served.urls() == ["https://api.tcgdex.net/v2/pt/cards/sv01-001"]
    assert (
        served.requests[0]
        .headers["User-Agent"]
        .startswith(f"tcg-pokedex/{version('tcg-pokedex')} ")
    )


@pytest.mark.parametrize(
    ("replies", "requests", "delays", "reason"),
    [
        ((Reply(500), Reply(fixture="cards/sv01-001.json")), 2, [1.0], None),
        (failing(500), 3, [1.0, 2.0], "HTTP 500 after 3 attempts"),
        ((Reply(404),), 1, [], "HTTP 404"),
    ],
    ids=["server-error-retried", "three-server-errors", "client-error"],
)
def test_server_errors_are_retried_and_client_errors_fail_at_once(
    replies: tuple[Reply, ...], requests: int, delays: list[float], reason: str | None
) -> None:
    served = FixtureRoutes({"cards/sv01-001": replies})
    sleep = SleepRecorder()

    with tcgdex(served, sleep) as client:
        if reason is None:
            assert client.card("sv01-001", "sv01") == PINECO
        else:
            with pytest.raises(TcgdexError, match=reason):
                client.card("sv01-001", "sv01")

    assert len(served.requests) == requests
    assert sleep.delays == delays


def test_the_index_and_a_set_map_to_ids_and_a_listing() -> None:
    with tcgdex(FixtureRoutes(HAPPY)) as client:
        series_ids = client.series_ids()
        listing = client.set_listing("sv01")

    assert series_ids == ["sv", "tcgp"]
    assert listing == SetListing(
        card_set=CardSet(
            id="sv01",
            series_id="sv",
            name="Escarlate e Violeta",
            release_date=date(2023, 3, 31),
            official_count=198,
            total_count=258,
            logo_url="https://assets.tcgdex.net/pt/sv/sv01/logo",
            symbol_url="https://assets.tcgdex.net/univ/sv/sv01/symbol",
        ),
        series=Series(id="sv", name="Escarlate e Violeta"),
        card_ids=("sv01-001", "sv01-002"),
    )


def test_a_card_belongs_to_the_synced_set_and_blank_text_is_absent() -> None:
    blank = card_payload(name=" Pineco ", rarity="None", illustrator="", image="  ")

    card = parse_card(blank, set_id="sv01-copy")

    assert card == Card(
        id="sv01-001",
        set_id="sv01-copy",
        collector_number="001",
        name="Pineco",
        rarity=None,
        illustrator=None,
        image_url=None,
        variants=PINECO.variants,
    )


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        (card_payload("name"), "invalid payload: name: Field required"),
        (card_payload(variants={"normal": False}), "no variants"),
    ],
)
def test_an_invalid_card_raises_its_reason(payload: bytes, reason: str) -> None:
    with pytest.raises(TcgdexError) as raised:
        parse_card(payload, set_id="sv01")

    assert raised.value.reason == reason


def test_card_images_come_in_both_sizes_and_must_be_small_webps() -> None:
    html = Reply(body=b"<html>oops</html>")
    huge = Reply(body=PIXEL + b"\0" * MAX_IMAGE_BYTES)
    served = FixtureRoutes(
        {
            **image(BASE),
            f"{PT}/002/low.webp": (Reply(404),),
            f"{PT}/003/low.webp": (html,),
            f"{PT}/004/low.webp": (huge,),
        }
    )

    with tcgdex(served) as client:
        assert client.card_images(BASE) == (PIXEL, PIXEL)
        assert client.card_images(f"{PT}/002") is None
        with pytest.raises(TcgdexError, match="not an image"):
            client.card_images(f"{PT}/003")
        with pytest.raises(TcgdexError, match="too large"):
            client.card_images(f"{PT}/004")

    assert served.urls()[:2] == [f"{BASE}/low.webp", f"{BASE}/high.webp"]


def test_english_image_url_is_the_recorded_one_or_none() -> None:
    served = FixtureRoutes(
        {
            **english("swshp-SWSH032", "swshp-SWSH032.json"),
            **english("svp-085", "svp-085.no-image.json"),
            **english("sv01-003"),
        }
    )

    with tcgdex(served) as client:
        assert (
            client.english_image_url("swshp-SWSH032")
            == "https://assets.tcgdex.net/en/swsh/swshp/SWSH032"
        )
        assert client.english_image_url("svp-085") is None
        assert client.english_image_url("sv01-003") is None


def test_only_a_univ_symbol_is_retried_once_under_pt() -> None:
    served = FixtureRoutes(
        {
            f"{UNIV}/symbol.webp": (Reply(404), Reply(404)),
            f"{PT}/symbol.webp": (Reply(body=PIXEL), Reply(404)),
            f"{UNIV}/logo.webp": (Reply(404),),
        }
    )

    with tcgdex(served) as client:
        assert client.artwork(ArtworkKind.SYMBOL, f"{UNIV}/symbol") == PIXEL
        assert client.artwork(ArtworkKind.SYMBOL, f"{UNIV}/symbol") is None
        assert client.artwork(ArtworkKind.LOGO, f"{UNIV}/logo") is None

    assert served.urls().count(f"{UNIV}/logo.webp") == 1
    assert len(served.requests) == 5
