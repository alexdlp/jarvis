"""Tests for the repository boundary around DynamoDB PutItem calls."""

import pytest
from botocore.exceptions import ClientError, NoCredentialsError

from jarvis.domain import WorkItem, Kind, Status
from jarvis.storage.dynamodb import PersistenceError, WorkItemAlreadyExists
from jarvis.storage.work_items import WorkItemRepository
from jarvis.storage.mapping import to_item


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

def test_list_for_user_returns_empty_list(fake_table, user_id: str):
    """A user without work items receives an empty collection."""

    # The shared fake returns an empty page unless a test configures results.
    repository = WorkItemRepository(fake_table)

    result = repository.list_for_user(user_id)

    assert result == []

    # Verify that the repository actually queried the table.
    assert len(fake_table.query_calls) == 1

def test_list_for_user_returns_work_items(
    fake_table,
    user_id: str,
    work_item_factory,
):
    """Return complete work items regardless of their kind."""

    idea = work_item_factory(
        kind=Kind.IDEA,
        title="Explore a new project",
        description="Keep this detail when reading the item.",
    )
    task = work_item_factory(
        kind=Kind.TASK,
        title="Review the documentation",
    )

    # Configure one final page using the actual storage representation.
    fake_table.query_pages = [
        {
            "Items": [
                to_item(user_id, idea),
                to_item(user_id, task),
            ],
        },
    ]

    repository = WorkItemRepository(fake_table)

    result = repository.list_for_user(user_id)

    # Model equality checks every field, including identifiers and timestamps.
    assert result == [idea, task]

def test_list_for_user_filters_by_kind_independently_of_status(
    fake_table,
    user_id: str,
    work_item_factory,
):
    """Filter by kind without imposing a status restriction."""

    inbox_task = work_item_factory(
        kind=Kind.TASK,
        status=Status.INBOX,
    )
    active_task = work_item_factory(
        kind=Kind.TASK,
        status=Status.ACTIVE,
    )
    idea = work_item_factory(
        kind=Kind.IDEA,
        status=Status.INBOX,
    )

    # Include different kinds and statuses in the same query response.
    stored_items = [inbox_task, active_task, idea]
    fake_table.query_pages = [
        {"Items": [to_item(user_id, item) for item in stored_items]},
    ]

    repository = WorkItemRepository(fake_table)

    result = repository.list_for_user(user_id, kind=Kind.TASK)

    # Both tasks match, regardless of their status. The idea is excluded.
    assert result == [inbox_task, active_task]

def test_list_for_user_filters_by_status_independently_of_kind(
    fake_table,
    user_id: str,
    work_item_factory,
):
    """Filter by status without imposing a kind restriction."""

    inbox_idea = work_item_factory(
        kind=Kind.IDEA,
        status=Status.INBOX,
    )
    inbox_task = work_item_factory(
        kind=Kind.TASK,
        status=Status.INBOX,
    )
    active_task = work_item_factory(
        kind=Kind.TASK,
        status=Status.ACTIVE,
    )

    # Include an active task to verify that the status filter excludes it.
    stored_items = [inbox_idea, inbox_task, active_task]
    fake_table.query_pages = [
        {"Items": [to_item(user_id, item) for item in stored_items]},
    ]

    repository = WorkItemRepository(fake_table)

    result = repository.list_for_user(
        user_id,
        statuses={Status.INBOX},
    )

    # Inbox includes both the idea and the task.
    assert result == [inbox_idea, inbox_task]

def test_list_for_user_continues_after_a_page_without_matches(
    fake_table,
    user_id: str,
    work_item_factory,
):
    """Continue pagination even when an earlier page has no matching items."""

    idea = work_item_factory(kind=Kind.IDEA)
    task = work_item_factory(kind=Kind.TASK)

    stored_idea = to_item(user_id, idea)
    last_key = {
        "pk": stored_idea["pk"],
        "sk": stored_idea["sk"],
    }

    # The first page contains no tasks, but indicates another page exists.
    fake_table.query_pages = [
        {
            "Items": [stored_idea],
            "LastEvaluatedKey": last_key,
        },
        {
            "Items": [to_item(user_id, task)],
        },
    ]

    repository = WorkItemRepository(fake_table)

    result = repository.list_for_user(user_id, kind=Kind.TASK)

    assert result == [task]

    # Verify that the next request resumes from the returned cursor.
    assert len(fake_table.query_calls) == 2
    assert "ExclusiveStartKey" not in fake_table.query_calls[0]
    assert fake_table.query_calls[1]["ExclusiveStartKey"] == last_key

@pytest.mark.parametrize(
    "error",
    [
        ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "Access denied",
                },
            },
            "Query",
        ),
        NoCredentialsError(),
    ],
)
def test_list_for_user_translates_storage_errors(
    fake_table,
    user_id: str,
    error,
):
    """Expose query failures through the repository's error contract."""

    # Simulate either a service rejection or a local credentials failure.
    fake_table.error = error
    repository = WorkItemRepository(fake_table)

    with pytest.raises(PersistenceError) as raised:
        repository.list_for_user(user_id)

    # Preserve the original exception for debugging.
    assert raised.value.__cause__ is error
