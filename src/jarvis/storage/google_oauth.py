# Get the current time to calculate the request's expiration.
from time import time

# Handle errors returned by AWS and failures when contacting it.
from botocore.exceptions import BotoCoreError, ClientError

# Reuse the existing table connection and persistence error type.
from jarvis.storage.dynamodb import PersistenceError, create_table

from google.oauth2.credentials import Credentials


def save_google_oauth_request(
    user_id: str,
    state: str,
    code_verifier: str,
) -> None:
    """Store a pending Google authorization request."""

    # Reference the existing application table; do not create a new one.
    table = create_table()

    try:
        table.put_item(
            Item={
                # Find this request using the state returned by Google.
                "pk": f"OAUTH#GOOGLE#{state}",

                # Identify the pending request within that partition.
                "sk": "REQUEST",

                # Distinguish this record from tasks.
                "entity": "google_oauth_request",

                # Associate the request with the authenticated Jarvis user.
                "user_id": user_id,

                # Preserve the original verifier for the token exchange.
                "code_verifier": code_verifier,

                # Allow ten minutes to complete the authorization.
                "expires_at": int(time()) + 600,
            },

            # Reject the write if a record with these keys already exists.
            ConditionExpression=(
                "attribute_not_exists(pk) AND attribute_not_exists(sk)"
            ),
        )
    except (BotoCoreError, ClientError) as error:
        # Use the same persistence error type as the task storage code.
        raise PersistenceError(
            "Could not store the Google OAuth request"
        ) from error

class InvalidGoogleOAuthRequest(ValueError):
    """The authorization request is missing, expired, or already consumed."""


def consume_google_oauth_request(state: str) -> dict:
    """Retrieve a valid pending request and prevent it from being reused."""

    # Reference this deployment's existing DynamoDB table.
    table = create_table()

    try:
        response = table.delete_item(
            # Locate the request using the state returned by Google.
            Key={
                "pk": f"OAUTH#GOOGLE#{state}",
                "sk": "REQUEST",
            },

            # Accept only requests whose expiration is still in the future.
            ConditionExpression="expires_at > :now",
            ExpressionAttributeValues={
                ":now": int(time()),
            },

            # Return the stored data while deleting the pending request.
            ReturnValues="ALL_OLD",
        )
    except ClientError as error:
        # A missing or expired request cannot satisfy the condition.
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise InvalidGoogleOAuthRequest(
                "Google authorization request is missing or expired."
            ) from error

        # Other AWS refusals are storage failures.
        raise PersistenceError(
            "Could not consume the Google OAuth request"
        ) from error
    except BotoCoreError as error:
        # Preserve the original cause when AWS cannot be reached.
        raise PersistenceError(
            "Could not consume the Google OAuth request"
        ) from error

    # The returned record contains the user ID and original verifier.
    return response["Attributes"]

def save_google_credentials(
    user_id: str,
    credentials: Credentials,
) -> None:
    """Store one Google connection for the specified Jarvis user."""

    # Require renewable access before replacing any existing connection.
    if not credentials.refresh_token:
        raise ValueError(
            "Google did not return a refresh token. Please reconnect."
        )

    # Reference this deployment's existing DynamoDB table.
    table = create_table()

    try:
        table.put_item(
            Item={
                # Associate the connection with its Jarvis user.
                "pk": f"U#{user_id}",

                # Use the Google integration key reserved in our data model.
                "sk": "INT#google",
                "entity": "google_credentials",

                # Preserve the token used to call Calendar.
                "access_token": credentials.token,

                # Preserve the token used to renew access later.
                "refresh_token": credentials.refresh_token,

                # Store the access token's UTC expiration as ISO text.
                "token_expiry": credentials.expiry.isoformat(),
            },
        )
    except (BotoCoreError, ClientError) as error:
        # Keep the original AWS error available for debugging.
        raise PersistenceError(
            "Could not store the Google credentials"
        ) from error