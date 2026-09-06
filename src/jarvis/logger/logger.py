"""The application's logger, defined in one place.

Named rather than the root logger so that records from this codebase can be
filtered apart from those the MCP SDK and Mangum emit.

No configuration happens here on purpose. Setting a level is a decision about
the *process*, and it belongs to whoever starts one — doing it at import time
would mean that importing any part of the application silently reconfigured
logging for whoever imported it, including a test.
"""

import logging

# Import this where something needs recording:
#
#     from jarvis.logger import logger
#
logger = logging.getLogger("jarvis")
