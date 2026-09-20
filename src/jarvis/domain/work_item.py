"""The work item: the single entity Jarvis stores.

One type covers what would otherwise be several. An idea, a task and a project
are not different structures — they differ in `kind`, which records a judgement
someone made about the thing. A subtask is not a kind at all: it is an item
that happens to have a parent.

Nothing here is inferred from shape, and that is deliberate. "Aprender CUDA" is
a project before anyone breaks it down, so deriving `project` from "has
children" would get it wrong exactly when it matters. Equally, a title with an
estimate attached is not thereby a task — being finishable is a property of the
work, not of which fields are populated.

What is absent is as considered as what is here. There is no scheduled time:
when you plan to do something is a separate fact, it lives in the calendar, and
storing it here as well would create two owners for it. There is no priority
either — importance is stated and stays true, whereas urgency is a function of
`deadline` and today's date and would go stale the moment it was written down.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from jarvis.utils.clock import now
from jarvis.utils.ids import new_id


class Kind(StrEnum):
    """What the item is. Recorded during triage, never derived."""

    IDEA = "idea"        # not actionable yet — still needs thinking through
    TASK = "task"        # concrete, and finishable as it stands
    PROJECT = "project"  # has to be broken down before it can be worked on


class Status(StrEnum):
    """Where the item is in its life.

    Limited to what cannot be computed from other fields. There is no `ready`,
    because that is an item that has been estimated; no `in progress`, because
    that is an item started and not finished; no `blocked`, because what is
    useful there is *what* blocks it rather than the fact that something does.
    """

    INBOX = "inbox"          # captured, not yet triaged
    ACTIVE = "active"        # triaged and in play
    PARKED = "parked"        # someday — deliberately not now
    DONE = "done"            # finished
    CANCELLED = "cancelled"  # decided against, which is not the same as done


class Importance(StrEnum):
    """How much this matters. Stated by the user, never inferred."""

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

    def complete(self) -> None:
        """Mark the work finished.

        A method rather than two field assignments because the status and the
        completion time have to move together: an item that is done without a
        completed_at is a hole in the record that only shows up much later,
        when there is nothing left to reconstruct it from.
        """
        moment = now()
        self.status = Status.DONE
        self.completed_at = moment
        self.updated_at = moment
