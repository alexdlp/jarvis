"""Tests for the repository boundary around DynamoDB PutItem calls."""

import pytest
from botocore.exceptions import ClientError, NoCredentialsError

from jarvis.domain import WorkItem
from jarvis.storage.dynamodb import PersistenceError, WorkItemAlreadyExists
from jarvis.storage.work_items import WorkItemRepository


def client_error(code: str) -> ClientError:
    """Build the shape botocore uses when DynamoDB rejects a request."""
    return ClientError({"Error": {"Code": code, "Message": ""}}, "PutItem")


def test_stores_the_item_and_returns_it(fake_table, user_id: str):
    """create() sends the mapped item to DynamoDB and returns the domain object."""
    # The fake records the outgoing request without making a network call.
    item = WorkItem(title="Aprender CUDA")

    returned = WorkItemRepository(fake_table).create(user_id, item)

    # Returning the same object lets the caller continue using the generated id
    # and timestamps; the key assertion proves that the repository mapped it.
    assert returned is item
    assert fake_table.calls[0]["Item"]["pk"] == f"U#{user_id}"


def test_adds_a_condition_that_prevents_overwriting(fake_table, user_id: str):
    """Every create asks DynamoDB to reject an existing primary key."""
    # PutItem normally replaces an existing item at the same primary key. The
    # repository must opt into create-only behaviour on every call.
    item = WorkItem(title="Aprender CUDA")

    WorkItemRepository(fake_table).create(user_id, item)

    assert fake_table.calls[0]["ConditionExpression"] == (
        "attribute_not_exists(pk) AND attribute_not_exists(sk)"
    )


def test_a_failed_condition_becomes_a_collision(fake_table, user_id: str):
    """A rejected create is exposed as the domain-specific collision error."""
    # Configure DynamoDB's response for an item whose primary key already exists.
    fake_table.error = client_error("ConditionalCheckFailedException")

    with pytest.raises(WorkItemAlreadyExists) as raised:
        WorkItemRepository(fake_table).create(user_id, WorkItem(title="Aprender CUDA"))

    # Exception chaining keeps the AWS detail available to logs and debugging.
    assert isinstance(raised.value.__cause__, ClientError)


def test_any_other_dynamodb_refusal_becomes_a_persistence_error(
    fake_table, user_id: str
):
    """A non-collision DynamoDB response becomes a generic persistence failure."""
    # Access denial is representative of ClientError responses that callers
    # cannot resolve as a normal work-item outcome.
    fake_table.error = client_error("AccessDeniedException")

    with pytest.raises(PersistenceError) as raised:
        WorkItemRepository(fake_table).create(user_id, WorkItem(title="Aprender CUDA"))

    # The public error is generic, while the original AWS error remains chained.
    assert not isinstance(raised.value, WorkItemAlreadyExists)
    assert isinstance(raised.value.__cause__, ClientError)


def test_never_reaching_dynamodb_also_becomes_a_persistence_error(
    fake_table, user_id: str
):
    """A botocore transport or configuration failure is translated consistently."""
    # NoCredentialsError is a BotoCoreError, not a ClientError: DynamoDB never
    # answered, so there is no response from which to read an error code.
    fake_table.error = NoCredentialsError()

    with pytest.raises(PersistenceError) as raised:
        WorkItemRepository(fake_table).create(user_id, WorkItem(title="Aprender CUDA"))

    # Chaining distinguishes the original operational cause without exposing it
    # as the repository's public exception type.
    assert isinstance(raised.value.__cause__, NoCredentialsError)


def test_an_injected_table_needs_no_environment(
    fake_table, user_id: str, monkeypatch
):
    """Dependency injection avoids reading Lambda configuration during a unit test."""
    # Removing the variable makes the assertion real: this call would raise
    # KeyError if the repository ignored the injected table.
    monkeypatch.delenv("JARVIS_TABLE_NAME", raising=False)

    WorkItemRepository(fake_table).create(user_id, WorkItem(title="Aprender CUDA"))
