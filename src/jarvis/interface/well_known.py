"""The documents served under /.well-known/.

RFC 8615 reserves that path prefix for metadata a client is expected to find
without being told where to look, which is exactly the situation here: the
server has to answer a question asked by a client that has no credentials yet.

Kept apart from the MCP server itself because it is not MCP. These are OAuth
documents that happen to be served by the same function, and they change for
entirely different reasons than the tools do.
"""

import os

from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse


def register(mcp: MCPServer) -> None:
    """Attach the well-known documents to an MCP server."""

    # RFC 9728 protected resource metadata: the document that turns a bare 401
    # into a useful one.
    #
    # A client is given only this server's URL. It has no way to know Cognito
    # exists, and no way to derive it — the API Gateway hostname and the
    # Cognito issuer share nothing. This document is the only channel that
    # connects the two, which is why the flow cannot work without it.
    #
    # API Gateway's JWT authorizer is a managed component whose 401 carries no
    # body and no headers we can add, so the client cannot be pointed here from
    # the refusal. It falls back to looking at this conventional path instead,
    # which is why the path is fixed rather than chosen.
    #
    # custom_route bypasses authorization by design, and that is correct rather
    # than a hole: a client with no token has to be able to read this, or it
    # would need a token to discover how to obtain a token. Nothing secret is
    # published — the issuer URL and its signing keys are public by
    # construction, since they verify signatures and cannot produce them.
    @mcp.custom_route("/.well-known/oauth-protected-resource/mcp", methods=["GET"])
    async def protected_resource_metadata(request: Request) -> JSONResponse:
        """Tell MCP clients which authorization server guards this resource."""
        return JSONResponse(
            {
                # Must match the URL typed into the client byte for byte, path
                # included, or the document is rejected as describing something
                # else.
                "resource": os.environ["MCP_RESOURCE_URL"],
                # A list, but only the first entry is ever used.
                "authorization_servers": [os.environ["MCP_AUTH_SERVER_URL"]],
                "scopes_supported": ["jarvis-mcp/tasks"],
                # The token travels in the Authorization header. Putting it in
                # a query string is forbidden — URLs end up in logs.
                "bearer_methods_supported": ["header"],
            }
        )

    @mcp.custom_route("/.well-known/oauth-authorization-server", methods=["GET"])
    async def authorization_server_metadata(request: Request) -> JSONResponse:
        """Expose OAuth authorization server metadata."""
        return JSONResponse(
            {
                "issuer": os.environ["COGNITO_ISSUER"],
                "authorization_endpoint": (
                    f"{os.environ['COGNITO_DOMAIN_URL']}/oauth2/authorize"
                ),
                "token_endpoint": (
                    f"{os.environ['COGNITO_DOMAIN_URL']}/oauth2/token"
                ),
                "code_challenge_methods_supported": ["S256"],
                "response_types_supported": ["code"],
                "grant_types_supported": [
                    "authorization_code",
                    "refresh_token",
                ],
            }
        )
