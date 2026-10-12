"""The ownership rules, without the database."""

from collections.abc import Mapping, Sequence

import pytest

from tcg_pokedex.models.ownership import card_ownership, set_completion
from tcg_pokedex.views.ownership import Variant

N, R, H = Variant.NORMAL, Variant.REVERSE, Variant.HOLO


@pytest.mark.parametrize(
    ("listed", "stored", "quantities", "owned", "wanted_version_missing"),
    [
        ([N, R], {}, [(N, 0), (R, 0)], False, False),
        ([N], {N: 1}, [(N, 1)], True, False),
        ([N, R], {N: 2}, [(N, 2), (R, 0)], True, True),
        ([N, R], {R: 1}, [(N, 0), (R, 1)], True, False),
        ([N, R], {N: 3, R: 1}, [(N, 3), (R, 1)], True, False),
        ([H], {H: 1}, [(H, 1)], True, False),
        ([N], {N: 1, R: 3}, [(N, 1)], True, False),
    ],
)
def test_card_ownership_follows_the_rules_table(
    listed: Sequence[Variant],
    stored: Mapping[Variant, int],
    quantities: list[tuple[Variant, int]],
    owned: bool,
    wanted_version_missing: bool,
) -> None:
    result = card_ownership("sv01-001", listed, stored)

    assert result.model_dump(mode="json") == {
        "card_id": "sv01-001",
        "variants": [
            {"variant": variant.value, "quantity": quantity}
            for variant, quantity in quantities
        ],
        "owned": owned,
        "wanted_version_missing": wanted_version_missing,
    }


@pytest.mark.parametrize(
    ("total", "owned", "so_normal", "expected"),
    [
        (0, 0, 0, (0, 0, False)),
        (198, 0, 0, (0, 0, False)),
        (198, 198, 7, (198, 7, True)),
        (198, 205, 9, (198, 9, True)),
        (3, 5, 5, (3, 3, True)),
    ],
)
def test_set_completion_caps_owned_at_the_total(
    total: int, owned: int, so_normal: int, expected: tuple[int, int, bool]
) -> None:
    completion = set_completion(total, owned, so_normal)

    assert (completion.owned, completion.so_normal, completion.complete) == expected
    assert completion.total == total
