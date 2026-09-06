"""Entry point AWS Lambda calls on every invocation.

Does two things and nothing else: configures the process, and translates
between Lambda's event shape and ASGI. What the application *is* belongs to
jarvis.interface; this file only starts it.

The application is rebuilt on every invocation rather than once at import
time. That is a constraint of the MCP SDK rather than a choice, and
build_starlette_server() carries the explanation.
"""

import logging

from mangum import Mangum

from jarvis.interface import build_starlette_server

# Lambda installs a CloudWatch handler on the root logger but leaves the level
# at WARNING, so every INFO record the MCP SDK and Mangum emit is discarded —
# without this the log shows START/END/REPORT and nothing else, and a 200 is
# indistinguishable from a 500. The root logger rather than the application's
# own, because the records worth seeing here come from libraries.
#
# Done at the entry point because setting a level is a decision about the
# process, and the entry point is what owns one. In an imported module it would
# mean that importing any part of the application silently reconfigured logging
# for whoever imported it.
logging.getLogger().setLevel(logging.INFO)


def handler(event, context):
    return Mangum(build_starlette_server())(event, context)
