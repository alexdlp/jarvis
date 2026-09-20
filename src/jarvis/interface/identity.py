from __future__ import annotations

from mcp.server.mcpserver.context import Context


def get_authenticated_user_id(ctx: Context) -> str:
    """Return the authenticated caller's immutable Cognito user ID.

    The ID is read from the JWT claims validated upstream by API Gateway.

    Raises:
        KeyError: If the Lambda/API Gateway authentication context is missing.
    """
    # Mangum exposes the original Lambda event through the ASGI scope.
    # The JWT has already been validated upstream, so no token decoding or
    # verification is performed here.
    request = ctx.request_context.request
    event = request.scope["aws.event"]

    # Fail loudly if the authentication chain is incomplete. Falling back to
    # another identity would risk reading or writing data under the wrong user.
    return event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
