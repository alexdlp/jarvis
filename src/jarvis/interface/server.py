"""Assembles the ASGI application that serves Jarvis over MCP."""

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from jarvis.interface import well_known
from jarvis.interface.tools import TOOLS


def build_starlette_server() -> Starlette:
    """Build the ASGI application serving Jarvis over MCP.

    A fresh instance every call, which looks wasteful and is deliberate: the
    SDK's StreamableHTTPSessionManager refuses a second run() on the same
    instance, and Mangum drives the Starlette lifespan — which is what calls
    run() — on every invocation. A module-level app would therefore serve the
    first request of a cold container and raise on every request after it: a
    bug that passes a single-request smoke test and only shows up once the
    container is reused.

    Measured cost of rebuilding: ~2 ms, against 83 ms billed duration.

    Returns a Starlette application rather than the MCP server itself — the
    server is an implementation detail of the assembly done here.
    """
    mcp = MCPServer("Jarvis")

    for tool in TOOLS:
        mcp.add_tool(tool)

    well_known.register(mcp)

    return mcp.streamable_http_app(
        # No Mcp-Session-Id is issued, so the client never sends one back and
        # every request stands alone. The only workable mode on Lambda, where
        # there is nowhere to keep a session between invocations.
        stateless_http=True,
        # Answer with one application/json response instead of an SSE stream.
        # The client's Accept header offers both and leaves the choice to the
        # server, which is what makes an HTTP API viable here — it cannot
        # stream a lambda response.
        json_response=True,
        # Without this the SDK sees its default host of 127.0.0.1, switches on
        # DNS rebinding protection, and accepts only localhost Host headers.
        # API Gateway sends its own domain, so every request would be rejected
        # with 421 before reaching any code here. DNS rebinding is a browser
        # attack and this caller is server-side; API Gateway is the control
        # over who reaches the function at all.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )
