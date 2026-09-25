"""Shared test data and fakes for the work-item persistence tests."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from jarvis.domain import WorkItem


USER_ID = "a1b2c3d4-5e6f-7890-abcd-ef1234567890"
FIXED_MOMENT = datetime(2026, 9, 18, 10, 12, 0, tzinfo=UTC)


class FakeTable:
    """Record DynamoDB writes in memory and optionally fail on demand."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def put_item(self, **kwargs: Any) -> None:
        """Record the PutItem arguments, then raise the configured error."""
        self.calls.append(kwargs)

        if self.error:
            raise self.error


@pytest.fixture
def user_id() -> str:
    """Return one stable Cognito subject for tests that build storage keys."""
    return USER_ID


@pytest.fixture
def fixed_moment() -> datetime:
    """Return a fixed UTC instant so timestamp assertions are deterministic."""
    return FIXED_MOMENT


@pytest.fixture
def work_item_factory(
    fixed_moment: datetime,
) -> Callable[..., WorkItem]:
    """Build work items with stable timestamps and per-test field overrides."""

    def build(**overrides: Any) -> WorkItem:
        """Return a valid work item, replacing only the requested fields."""
        defaults = {
            "title": "Aprender CUDA",
            "created_at": fixed_moment,
            "updated_at": fixed_moment,
        }
        return WorkItem(**(defaults | overrides))

    return build


@pytest.fixture
def fake_table() -> FakeTable:
    """Return an empty in-memory stand-in for boto3's DynamoDB Table."""
    return FakeTable()
