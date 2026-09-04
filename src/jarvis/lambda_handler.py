"""Entry point AWS Lambda calls on every invocation.

The MCP server is built inside the handler rather than once at import time.
That looks wasteful and is deliberate: the SDK's StreamableHTTPSessionManager
refuses a second run() on the same instance, and Mangum drives the Starlette
lifespan — which is what calls run() — on every invocation. A module-level app
would therefore serve the first request of a cold container and raise on every
request after it: a bug that passes a single-request smoke test and only shows
up once the container is reused.

Measured cost of rebuilding per request: ~2 ms, against 83 ms billed duration.
"""
import logging
import os

from mangum import Mangum
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse


# Lambda installs a CloudWatch handler on the root logger but leaves the level
# at WARNING, so every INFO record the MCP SDK and Mangum emit is discarded.
# Without this the log shows START/END/REPORT and nothing else: a 200 and a
# 500 are indistinguishable.
logging.getLogger().setLevel(logging.INFO)


def handler(event, context):
    
    mcp = MCPServer("Jarvis")

    @mcp.tool()
    def hello() -> str:
        """Return a test greeting."""
        return "Hello from Jarvis"

    # RFC 9728 protected resource metadata: the document that turns a bare 401
    # into a useful one.
    #
    # Claude is given only this server's URL. It has no way to know Cognito
    # exists, and no way to derive it — the API Gateway hostname and the
    # Cognito issuer share nothing. This document is the only channel that
    # connects the two, which is why the flow cannot work without it.
    #
    # custom_route bypasses authorization by design, and that is correct rather
    # than a hole: a client with no token has to be able to read this, or it
    # would need a token to discover how to obtain a token. Nothing secret is
    # published — the issuer URL and its signing keys are public by
    # construction, since they verify signatures and cannot produce them.
    #
    # `resource` must match the URL the user types into Claude byte for byte,
    # path included, or the client rejects the document.
    @mcp.custom_route("/.well-known/oauth-protected-resource/mcp", methods=["GET"])
    async def protected_resource_metadata(request: Request) -> JSONResponse:
        """Tell MCP clients which authorization server guards this resource."""
        return JSONResponse(
            {
                "resource": os.environ["MCP_RESOURCE_URL"],
                "authorization_servers": [os.environ["COGNITO_ISSUER"]],
                "scopes_supported": ["jarvis-mcp/tasks"],
                "bearer_methods_supported": ["header"],
            }
        )

    app = mcp.streamable_http_app(
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

    return Mangum(app)(event, context)