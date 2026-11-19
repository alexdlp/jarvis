from __future__ import annotations

from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from boto3.dynamodb.conditions import Key

from jarvis.domain import Kind, Status, WorkItem
from jarvis.storage.dynamodb import (
    PersistenceError,
    WorkItemAlreadyExists,
    create_table,
)
from jarvis.storage.mapping import to_item, from_item, partition_key

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


    def list_for_user(self, user_id: str, kind: Kind | None = None, statuses: set[Status] | None = None) -> list[WorkItem]:
        """Return the user's work items matching the optional filters.
        
        Filters are independent:
        - kind=None accpets anu item kind.
        - statuses=None accepts any status.
        - statuses=set() accepts no statuses.
        
        Raises:
            PersistenceError: If DynamoDB cannot complete the query.
        """

        # An empty set accepts no statuses, so no AWS request is necessary.
        if statuses is not None and not statuses:
            return []

        # Query the base table to retrieve every field in the domain model.
        # The partition restricts reads to this user, while the ITEM# prefix
        # excludes other entity types stored in the same partition.
        query_parameters: dict[str, Any] = {
            "KeyConditionExpression": (
                Key("pk").eq(partition_key(user_id))
                & Key("sk").begins_with("ITEM#")
            ),

            # Include completed writes when querying immediately after capture.
            "ConsistentRead": True,
        }

        # Collect matching items across every page returned by DynamoDB.
        items: list[WorkItem] = []

        try:
            while True:
                # Unpack the query parameters into keyword arguments.
                # A response may contain only part of the complete result.
                response = self._table.query(**query_parameters)

                for attributes in response.get("Items", []):
                    # Convert the stored attributes into a domain object.
                    item = from_item(attributes)

                    # Apply kind and status filters independently.
                    # None means that the corresponding filter is unrestricted.
                    if kind is not None and item.kind != kind:
                        continue

                    if statuses is not None and item.status not in statuses:
                        continue

                    items.append(item)

                # Continue until DynamoDB reports that no further page remains.
                # Finding no matches on one page does not end the query.
                last_key = response.get("LastEvaluatedKey")

                if not last_key:
                    break

                # Preserve the query and resume after the previous page.
                query_parameters["ExclusiveStartKey"] = last_key

        except (ClientError, BotoCoreError) as error:
            # Preserve the repository's error contract and chain the cause.
            # Never return a partial result as though the query had completed.
            raise PersistenceError(
                "Could not retrieve work items"
            ) from error

        # Filtering in Python reduces the returned collection, but does not
        # reduce the amount of data DynamoDB had to read.
        return items