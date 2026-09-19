"""What Jarvis manages, independent of how it is stored or exposed.

Nothing in here imports from storage or from the interface, and nothing should:
this is the one package that would survive changing the database or dropping
MCP entirely. Imports point inwards, so a violation shows up as a domain module
reaching outwards.
"""

from jarvis.domain.work_item import (
    Importance,
    Kind,
    Status,
    WorkItem,
)

__all__ = [
    "Importance",
    "Kind",
    "Status",
    "WorkItem",
]
