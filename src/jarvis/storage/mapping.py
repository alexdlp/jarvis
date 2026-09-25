from __future__ import annotations

from typing import Any

from jarvis.domain import Status, WorkItem

# Statuses that mean the work is still in play. They share an index partition so
# that "all open work" is a single query: sorted lexicographically they are not
# contiguous, because cancelled and done fall between active and inbox.
OPEN_STATUSES = frozenset({Status.INBOX, Status.ACTIVE, Status.PARKED})

# Sorts after every real date, so undated work lands at the end of its status
# instead of being absent from the index.
NO_DEADLINE = "9999-12-31"


def partition_key(user_id: str) -> str:
    """Return the base table partition key for a user."""
    return f"U#{user_id}"


def sort_key(work_item_id: str) -> str:
    """Return the base table sort key for a work item."""
    return f"ITEM#{work_item_id}"


def ordering_date(item: WorkItem) -> str:
    """Return the date the item is ordered by while in its current status.

    Different per status because the relevant date is not the same field
    throughout an item's life: the inbox is read oldest first, work in play by
    deadline, and finished work by when it was finished.
    """
    if item.status is Status.INBOX:
        return item.created_at.isoformat(timespec="seconds")

    if item.status in (Status.DONE, Status.CANCELLED):
        moment = item.completed_at or item.updated_at
        return moment.isoformat(timespec="seconds")

    return item.deadline.isoformat() if item.deadline else NO_DEADLINE


def to_item(user_id: str, item: WorkItem) -> dict[str, Any]:
    """Return the DynamoDB attributes for a work item.

    The four key attributes are copies of id, status and deadline. They exist
    because DynamoDB can only sort and range over what sits in a key.

    Attributes that are None are dropped. An absent attribute reads back as the
    model's own default, so recording that a deadline was not set costs bytes
    and buys nothing.
    """
    phase = "open" if item.status in OPEN_STATUSES else "closed"

    attributes = {
        "pk": partition_key(user_id),
        "sk": sort_key(item.id),
        "status_pk": f"{partition_key(user_id)}#{phase}",
        "status_sk": f"{item.status}#{ordering_date(item)}",
        "entity": "work_item",
        # mode="json" renders dates as ISO strings and enums as their values;
        # boto3 cannot serialise the objects the default would produce.
        **item.model_dump(mode="json"),
    }

    return {key: value for key, value in attributes.items() if value is not None}


def from_item(attributes: dict[str, Any]) -> WorkItem:
    """Return the work item stored in a set of DynamoDB attributes.

    Key attributes are ignored rather than mapped back, since each is derived
    from a field that is also stored in its own right.
    """
    return WorkItem.model_validate(attributes)
