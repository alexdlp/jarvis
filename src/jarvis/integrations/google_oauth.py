import json
import os

import boto3
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

def load_google_oauth_client_config() -> dict:
    """Read the shared Google OAuth client configuration from AWS."""

    # Read the parameter name configured through Terraform
    parameter_name = os.environ["GOOGLE_OAUTH_CLIENT_PARAMETER_NAME"]

    # Create a client for AWS Systerms Manager.
    # In Lambda, boto3 uses the function's execution role.
    ssm = boto3.client("ssm")

    # Retrieve the parameter and ask AWS to decrypt its value.
    response = ssm.get_parameter(
        Name = parameter_name,
        WithDecryption = True,
    )

    # Convert the stored JSON text into a Python dictionary
    return json.loads(response["Parameter"]["Value"])


def build_google_authorization(state: str) -> tuple[str, str]:
    """Build the authorization URL and return its private PKCE verifier."""

    # Read the shared client configuration from Parameter Store.
    config = load_google_oauth_client_config()

    # Use the single callback registered in the shared Google configuration.
    redirect_uri = config["web"]["redirect_uris"][0]

    # Prepare Google's OAuth flow with the selected Calendar permission.
    flow = Flow.from_client_config(
        config,
        scopes=["https://www.googleapis.com/auth/calendar.events.owned"],
        redirect_uri=redirect_uri,
        state=state,
        autogenerate_code_verifier=True,
    )

    # Request renewable access and show the consent screen when connecting.
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )

    # The caller will store the verifier privately to complete this operation.
    return authorization_url, flow.code_verifier

def exchange_google_authorization_code(
    code: str,
    code_verifier: str,
) -> Credentials:
    """Exchange Google's authorization code for access credentials."""

    # Retrieve our application's shared OAuth configuration.
    config = load_google_oauth_client_config()

    # Reconstruct the flow using the same permissions and callback.
    flow = Flow.from_client_config(
        config,
        scopes=["https://www.googleapis.com/auth/calendar.events.owned"],
        redirect_uri=config["web"]["redirect_uris"][0],

        # Reuse the original verifier recovered from the pending request.
        code_verifier=code_verifier,

        # Do not generate a different verifier for this exchange.
        autogenerate_code_verifier=False,
    )

    # Send the code to Google's token endpoint, waiting at most ten seconds.
    # The library includes the client credentials and original verifier.
    flow.fetch_token(
        code=code,
        timeout=10,
    )

    # Return the credentials obtained from Google's response.
    return flow.credentials