from datetime import UTC, datetime


class SystemClock:
    """Clock backed by the operating system's wall time."""

    def now(self) -> datetime:
        return datetime.now(UTC)
