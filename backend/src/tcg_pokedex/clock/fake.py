from datetime import UTC, datetime, timedelta


class FakeClock:
    """In-memory Clock for tests: time stands still until advanced."""

    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None:
            raise ValueError("FakeClock needs a timezone-aware start time")
        self._now = start.astimezone(UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        if delta < timedelta(0):
            raise ValueError("FakeClock cannot move backwards")
        self._now += delta
