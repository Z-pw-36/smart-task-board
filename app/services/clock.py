from collections.abc import Callable
from datetime import UTC, datetime

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Return an aware UTC timestamp suitable for business events."""

    return datetime.now(UTC)
