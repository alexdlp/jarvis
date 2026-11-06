import os
import secrets

from mcp.server.mcpserver.context import Context

from jarvis.integrations.google_oauth import build_google_authorization
from jarvis.interface.identity import get_authenticated_user_id
from jarvis.storage.google_oauth import save_google_oauth_request


def connect_google_calendar(ctx: Context) -> dict[str, str]:
    """Start connecting the authenticated user's Google Calendar.

    Return the authorization link for the user to open in their browser.
    """

    # Identify the caller using the Cognito token validated by API Gateway.
    user_id = get_authenticated_user_id(ctx)

    # Read the originating deployment's identifier, provided by Terraform.
    workspace = os.environ["JARVIS_WORKSPACE"]

    # Identify this attempt and preserve its originating deployment.
    state = f"{workspace}.{secrets.token_urlsafe(32)}"

    # Build the Google authorization link and generate its private verifier.
    authorization_url, code_verifier = build_google_authorization(state)

    # Store the pending request before allowing the user to begin authorizing.
    save_google_oauth_request(
        user_id=user_id,
        state=state,
        code_verifier=code_verifier,
    )

    # Share the authorization link while keeping the verifier on the server.
    return {"authorization_url": authorization_url}