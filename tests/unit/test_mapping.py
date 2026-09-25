"""Tests for translating WorkItem objects to and from DynamoDB attributes."""

from collections.abc import Callable
from datetime import date, datetime

import pytest

from jarvis.domain import Importance, Kind, Status, WorkItem
from jarvis.storage.mapping import from_item, to_item


def test_writes_all_storage_key_attributes(
    user_id: str, work_item_factory: Callable[..., WorkItem]
):
    """Every stored work item contains all base-table and status-index keys."""
    # A GSI is sparse: an item missing these is not indexed, the write still
    # succeeds, and the queries that should find it come back empty.
    stored = to_item(user_id, work_item_factory())

    assert set(stored) >= {"pk", "sk", "status_pk", "status_sk"}


def test_partitions_by_user(
    user_id: str, work_item_factory: Callable[..., WorkItem]
):
    """The base primary key combines authenticated ownership with item identity."""
    # The user controls the partition; the generated work-item id controls its
    # stable address inside that partition.
    item = to_item(user_id, work_item_factory())

    assert item["pk"] == f"U#{user_id}"
    assert item["sk"] == f"ITEM#{item['id']}"


@pytest.mark.parametrize(
    "status", [Status.INBOX, Status.ACTIVE, Status.PARKED]
)
def test_work_in_play_shares_one_index_partition(
    status: Status, user_id: str, work_item_factory: Callable[..., WorkItem]
):
    """Inbox, active and parked items share the queryable open partition."""
    # Parametrization applies the same storage rule to every non-terminal status.
    stored = to_item(user_id, work_item_factory(status=status))

    assert stored["status_pk"] == f"U#{user_id}#open"


@pytest.mark.parametrize("status", [Status.DONE, Status.CANCELLED])
def test_terminal_work_moves_to_its_own_index_partition(
    status: Status, user_id: str, work_item_factory: Callable[..., WorkItem]
):
    """Done and cancelled items share the queryable closed partition."""
    # The parameter list defines exactly which lifecycle states leave open work.
    stored = to_item(user_id, work_item_factory(status=status))

    assert stored["status_pk"] == f"U#{user_id}#closed"


def test_the_inbox_is_ordered_by_capture_time(
    user_id: str, work_item_factory: Callable[..., WorkItem]
):
    """An inbox key contains created_at so older captures sort before newer ones."""
    # The fixture's fixed timestamp makes the complete derived key explicit.
    item = to_item(user_id, work_item_factory(status=Status.INBOX))

    assert item["status_sk"] == "inbox#2026-09-18T10:12:00+00:00"


def test_active_work_is_ordered_by_deadline(
    user_id: str, work_item_factory: Callable[..., WorkItem]
):
    """An active key contains its deadline so dated work sorts chronologically."""
    # ISO dates have the same lexical and chronological order.
    item = to_item(
        user_id,
        work_item_factory(status=Status.ACTIVE, deadline=date(2026, 10, 31)),
    )

    assert item["status_sk"] == "active#2026-10-31"


def test_undated_work_sorts_last_instead_of_leaving_the_index(
    user_id: str, work_item_factory: Callable[..., WorkItem]
):
    """An active item without a deadline remains indexed after real deadlines."""
    # The sentinel retains undated work in the GSI and sorts after plausible dates.
    item = to_item(user_id, work_item_factory(status=Status.ACTIVE))

    assert item["status_sk"] == "active#9999-12-31"
    assert item["status_sk"] > "active#2099-12-31"


def test_finished_work_is_ordered_by_completion(
    user_id: str,
    fixed_moment: datetime,
    work_item_factory: Callable[..., WorkItem],
):
    """A done key contains completed_at so finished work can be queried by date."""
    # Supplying a fixed completion time proves which domain field enters the key.
    finished = work_item_factory(
        status=Status.DONE,
        completed_at=fixed_moment,
    )

    assert to_item(user_id, finished)["status_sk"] == (
        "done#2026-09-18T10:12:00+00:00"
    )


def test_sort_keys_use_seconds_without_changing_domain_precision(
    user_id: str,
    fixed_moment: datetime,
    work_item_factory: Callable[..., WorkItem],
):
    """The derived index key normalizes precision while WorkItem keeps microseconds."""
    # Key formatting is a storage concern: the domain timestamp should remain exact.
    precise_moment = fixed_moment.replace(microsecond=996470)
    precise = work_item_factory(created_at=precise_moment)

    stored = to_item(user_id, precise)

    assert stored["status_sk"] == "inbox#2026-09-18T10:12:00+00:00"
    assert precise.created_at == precise_moment


def test_unset_attributes_are_not_written(
    user_id: str, work_item_factory: Callable[..., WorkItem]
):
    """Optional values represented by None are omitted from the DynamoDB item."""
    # Missing attributes cost no storage and Pydantic restores their defaults.
    item = to_item(user_id, work_item_factory())

    assert "deadline" not in item
    assert "description" not in item
    assert "completed_at" not in item


def test_an_item_survives_the_round_trip(
    user_id: str, work_item_factory: Callable[..., WorkItem]
):
    """Serializing and loading a populated item preserves all domain information."""
    # Use every non-trivial field so the test covers dates, enums, lists and text.
    original = work_item_factory(
        status=Status.ACTIVE,
        kind=Kind.PROJECT,
        importance=Importance.HIGH,
        deadline=date(2026, 10, 31),
        estimate_minutes=90,
        tags=["aprendizaje"],
        description="Empezar por el modelo de memoria",
    )

    restored = from_item(to_item(user_id, original))

    assert restored == original
