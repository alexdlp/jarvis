from __future__ import annotations

from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from jarvis.domain import WorkItem
from jarvis.storage.dynamodb import (
    PersistenceError,
    WorkItemAlreadyExists,
    create_table,
)
from jarvis.storage.mapping import to_item

_ALREADY_EXISTS = "ConditionalCheckFailedException"


class WorkItemRepository:
    """Reads and writes work items."""

    def __init__(self, table: Any = None) -> None:
        self._table = table if table is not None else create_table()

    def create(self, user_id: str, item: WorkItem) -> WorkItem:
        """Store a new work item and return it.

        Raises:
            WorkItemAlreadyExists: If that user already has an item with this id.
            PersistenceError: If the write fails for any other reason.
        """
        try:
            self._table.put_item(
                Item=to_item(user_id, item),
                # Without this a put replaces whatever shares the key, so a
                # repeated id would destroy an existing item instead of failing.
                ConditionExpression=(
                    "attribute_not_exists(pk) AND attribute_not_exists(sk)"
                ),
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == _ALREADY_EXISTS:
                raise WorkItemAlreadyExists(item.id) from error

            raise PersistenceError(f"Could not store work item {item.id}") from error
        except BotoCoreError as error:
            # ClientError covers what DynamoDB answers; BotoCoreError covers
            # never reaching it — missing credentials, no endpoint, a dropped
            # connection. Both are chained so the original reaches the logs.
            raise PersistenceError(f"Could not store work item {item.id}") from error

        return item
