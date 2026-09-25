from __future__ import annotations

from datetime import date
from typing import Annotated

from mcp.server.mcpserver.context import Context
from pydantic import Field

from jarvis.domain import Importance, Kind, Status, WorkItem
from jarvis.interface.identity import get_authenticated_user_id
from jarvis.logger import logger
from jarvis.storage.work_items import WorkItemRepository


def capture_workitem(
    title: Annotated[
        str,
        Field(description="Short name for the work, in the user's own words."),
    ],
    ctx: Context,
    kind: Kind = Kind.TASK,
    status: Status = Status.INBOX,
    importance: Importance = Importance.NORMAL,
    description: Annotated[
        str | None,
        Field(
            description=(
                "The detail: what it involves, what to bring, who it is with, "
                "why it matters. Anything the user said that does not fit in "
                "the title belongs here rather than being dropped."
            )
        ),
    ] = None,
    deadline: Annotated[
        date | None,
        Field(
            description=(
                "The date the work is due by — not when the user plans to sit "
                "down and do it."
            )
        ),
    ] = None,
    estimate_minutes: Annotated[
        int | None,
        Field(
            description=(
                "How long the work will take, when the user says so or it is "
                "plain from what they described. Not a guess for its own sake."
            )
        ),
    ] = None,
    tags: Annotated[
        list[str] | None,
        Field(
            description=(
                "Free-form labels, when the user's own words suggest one. Do "
                "not invent a taxonomy."
            )
        ),
    ] = None,
    parent_id: Annotated[
        str | None,
        Field(
            description=(
                "The id of an existing item this one is part of, available "
                "only from an earlier call in the same conversation."
            )
        ),
    ] = None,
) -> dict:
    """Use this tool whenever the user wants to capture something to do, remember,
    consider, or attend.

    Do not ask clarifying questions before capturing. Sparse input is valid.

    Populate fields from what the user explicitly says or what follows clearly
    from it. Do not guess missing dates, estimates, importance, tags, or other
    optional metadata.

    Resolve relative dates such as "Friday" or "next week" when their meaning is
    unambiguous from the current date and user timezone.
    """
    item = WorkItem(
        title=title,
        kind=kind,
        status=status,
        importance=importance,
        description=description,
        deadline=deadline,
        estimate_minutes=estimate_minutes,
        tags=tags or [],
        parent_id=parent_id,
    )

    # Read from the validated token rather than taken as an argument, which is
    # why there is no user_id parameter above for a model to fill in.
    user_id = get_authenticated_user_id(ctx)

    WorkItemRepository().create(user_id, item)

    # Log only operational metadata. Titles, descriptions and tags may contain
    # personal information and are not needed to confirm that capture worked.
    logger.info("Captured work item id=%s status=%s", item.id, item.status)

    return item.model_dump(mode="json")
