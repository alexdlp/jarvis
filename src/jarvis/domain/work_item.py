from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from jarvis.utils.clock import now
from jarvis.utils.ids import new_id


class Kind(StrEnum):
    """What the item is.

    idea     not actionable yet — still needs thinking through
    task     concrete, and finishable as it stands
    project  has to be broken down before it can be worked on
    """

    # The meanings live in the docstring rather than beside each member because
    # that is the half that survives: pydantic carries a class docstring into
    # the JSON Schema as the type's `description`, so an agent reading the
    # schema sees these three lines. A comment reaches nobody but a reader of
    # this file — which is what makes it the right place for the rest of the
    # reasoning. This is a judgement someone made, never inferred from shape;
    # the module docstring argues why.
    IDEA = "idea"
    TASK = "task"
    PROJECT = "project"


class Status(StrEnum):
    """Where the item is in its life.

    inbox      captured, not thought about yet
    active     in play — decided, real, possibly already started
    parked     someday, deliberately not now
    done       finished
    cancelled  decided against, which is not the same as done
    """

    # Limited to what cannot be computed from other fields. There is no `ready`,
    # because that is an item that has been estimated; no `in progress`, because
    # that is an item started and not finished; no `blocked`, because what is
    # useful there is *what* blocks it rather than the fact that something does.
    #
    # That argument is a comment and not part of the docstring on purpose. It
    # explains states this enum does not have, which is worth a great deal to
    # someone changing this file and worth nothing to an agent filling in a
    # field — and the docstring is sent to the agent on every request.
    INBOX = "inbox"
    ACTIVE = "active"
    PARKED = "parked"
    DONE = "done"
    CANCELLED = "cancelled"


class Importance(StrEnum):
    """How much this matters, as the user judges it.

    low, normal, high. `high` only when the user says or clearly implies this
    matters more than their other work. Urgency is not importance: something
    due tomorrow is not thereby important.
    """

    # Stated, never inferred — which is also why urgency is absent entirely.
    # Urgency is a function of `deadline` and today's date, so it would go stale
    # the moment it was written down.
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class WorkItem(BaseModel):
    """Something the user wants to do."""

    id: str = Field(default_factory=new_id)

    # Structure, not kind. A subtask is a task that happens to have a parent,
    # and an item is recognised as a project long before it has any children.
    parent_id: str | None = None

    title: str = Field(min_length=1)
    kind: Kind = Kind.TASK
    status: Status = Status.INBOX
    description: str | None = None

    deadline: date | None = None
    estimate_minutes: int | None = Field(default=None, gt=0)
    importance: Importance = Importance.NORMAL

    # Free-form on purpose: this is where flexibility lives. A new way of
    # slicing the backlog is a new tag, not a schema change — which matters
    # because the useful categories are not knowable in advance.
    tags: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)

    # Set only when the work was actually finished. Together with
    # estimate_minutes this is what will eventually show how far off the
    # estimates run — which is why it is worth recording long before anything
    # reads it. Estimates can be analysed at any time; a completion that was
    # never written down cannot be recovered.
    completed_at: datetime | None = None
