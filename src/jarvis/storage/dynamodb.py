import os
from functools import cache

import boto3


class PersistenceError(RuntimeError):
    """Raised when the store cannot service a request."""


class WorkItemAlreadyExists(PersistenceError):
    """Raised when a work item is created with an id that is already taken."""


@cache
def create_table():
    """Return the DynamoDB table this process writes to.

    Built on first use rather than at import, so importing anything that reaches
    this module does not require the table name or AWS credentials. Cached, so a
    warm Lambda invocation reuses the client and its open connections.

    Raises:
        KeyError: If JARVIS_TABLE_NAME is not set.
    """
    return boto3.resource("dynamodb").Table(os.environ["JARVIS_TABLE_NAME"])
