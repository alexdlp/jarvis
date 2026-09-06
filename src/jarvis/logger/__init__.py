"""Logging for the application.

Re-exported here so that callers write `from jarvis.logger import logger` and
get the Logger. Without this, that same line resolves to the module inside the
package instead — the two share a name — and `logger.info(...)` fails with an
AttributeError.
"""

from jarvis.logger.logger import logger

__all__ = ["logger"]
