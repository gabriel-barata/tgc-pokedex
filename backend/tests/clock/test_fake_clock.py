from datetime import UTC, datetime, timedelta, timezone

import pytest

from tcg_pokedex.clock.fake import FakeClock

START = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_now_returns_the_start_time_until_advanced() -> None:
    clock = FakeClock(START)

    assert clock.now() == START
    assert clock.now() == START


def test_advance_moves_time_forward() -> None:
    clock = FakeClock(START)

    clock.advance(timedelta(hours=3))

    assert clock.now() == datetime(2026, 1, 1, 15, 0, tzinfo=UTC)


def test_start_time_is_returned_in_utc() -> None:
    sao_paulo = timezone(timedelta(hours=-3))
    clock = FakeClock(datetime(2026, 1, 1, 9, 0, tzinfo=sao_paulo))

    assert clock.now() == START
    assert clock.now().tzinfo is UTC


def test_naive_start_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FakeClock(datetime(2026, 1, 1))


def test_advancing_backwards_is_rejected() -> None:
    clock = FakeClock(START)

    with pytest.raises(ValueError, match="backwards"):
        clock.advance(timedelta(seconds=-1))
