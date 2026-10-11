from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Source of the current time. Inject it wherever logic depends on time."""

    def now(self) -> datetime:
        """Return the current time as a timezone-aware UTC datetime."""
        ...
