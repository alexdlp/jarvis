import uuid


def new_id() -> str:
    """A fresh identifier."""
    return uuid.uuid4().hex