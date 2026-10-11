"""Contract every Clock adapter must honour, run against the fake and the real one."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from tcg_pokedex.clock.adapters.system import SystemClock
from tcg_pokedex.clock.fake import FakeClock
from tcg_pokedex.clock.ports import Clock


def make_fake_clock() -> Clock:
    return FakeClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))


def make_system_clock() -> Clock:
    return SystemClock()


@pytest.fixture(params=[make_fake_clock, make_system_clock], ids=["fake", "system"])
def clock(request: pytest.FixtureRequest) -> Clock:
    factory: Callable[[], Clock] = request.param
    return factory()


def test_now_is_timezone_aware_utc(clock: Clock) -> None:
    now = clock.now()

    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_now_never_goes_backwards(clock: Clock) -> None:
    first = clock.now()
    second = clock.now()

    assert second >= first
