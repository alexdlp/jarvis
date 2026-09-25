from datetime import UTC, datetime


def now() -> datetime:
    """Return the current instant in UTC."""
    return datetime.now(UTC)
