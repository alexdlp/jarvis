from datetime import UTC, datetime


def now() -> datetime:
    """The current instant, timezone-aware."""
    return datetime.now(UTC)