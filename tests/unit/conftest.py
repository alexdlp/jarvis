"""Shared test data and fakes for the work-item persistence tests."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from jarvis.domain import WorkItem


USER_ID = "a1b2c3d4-5e6f-7890-abcd-ef1234567890"
FIXED_MOMENT = datetime(2026, 9, 18, 10, 12, 0, tzinfo=UTC)


class FakeTable:
    """Record DynamoDB requests and return configurable query pages."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

        # Keep write and query requests separate for test assertions.
        self.calls: list[dict[str, Any]] = []
        self.query_calls: list[dict[str, Any]] = []

        # Tests can configure the pages returned by successive query calls.
        self.query_pages: list[dict[str, Any]] = []

    def put_item(self, **kwargs: Any) -> None:
        """Record a write request and optionally simulate a failure."""
        self.calls.append(kwargs)

        if self.error:
            raise self.error

    def query(self, **kwargs: Any) -> dict[str, Any]:
        """Return the next configured page or an empty final page."""
        self.query_calls.append(kwargs)

        if self.error:
            raise self.error

        if self.query_pages:
            return self.query_pages.pop(0)

        return {"Items": []}


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
