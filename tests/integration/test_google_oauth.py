"""Integration test against the deployed DynamoDB table."""

import json
import secrets
import subprocess
from pathlib import Path
from time import time

import pytest

from jarvis.storage.dynamodb import create_table
from jarvis.storage.google_oauth import save_google_oauth_request


@pytest.fixture
def dynamodb_table(monkeypatch):
    """Configure access to the current branch's deployed table."""

    # Locate the repository independently of the terminal's directory.
    project_root = Path(__file__).resolve().parents[2]

    # Reuse Make's existing logic to select this branch's workspace.
    subprocess.run(
        ["make", "select-workspace"],
        cwd=project_root,
        check=True,
    )

    # Read the selected workspace's Terraform state.
    state_output = subprocess.check_output(
        ["terraform", "-chdir=infra", "state", "pull"],
        cwd=project_root,
        text=True,
    )

    # Find our DynamoDB resource in that deployment.
    resource = next(
        resource
        for resource in json.loads(state_output)["resources"]
        if resource["type"] == "aws_dynamodb_table"
        and resource["name"] == "main"
    )
    attributes = resource["instances"][0]["attributes"]

    # Configure the table and region using the deployed resource's data.
    # An ARN contains: arn:partition:service:region:account:resource.
    monkeypatch.setenv("JARVIS_TABLE_NAME", attributes["name"])
    monkeypatch.setenv(
        "AWS_DEFAULT_REGION",
        attributes["arn"].split(":")[3],
    )

    # Discard any table reference cached by an earlier test.
    create_table.cache_clear()

    try:
        # Provide the configured table to the test.
        yield create_table()
    finally:
        # Leave no cached table reference for subsequent tests.
        create_table.cache_clear()


def test_saves_and_reads_a_google_oauth_request(dynamodb_table):
    # Use unique test values to avoid collisions with other requests.
    state = "storage-check." + secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    user_id = "storage-check-user"

    # Use the table configured automatically by the fixture.
    table = dynamodb_table
    key = {"pk": f"OAUTH#GOOGLE#{state}", "sk": "REQUEST"}

    # Record the time before writing to check the ten-minute expiration.
    before = int(time())
    save_google_oauth_request(user_id, state, verifier)

    try:
        # Read immediately without relying on eventual consistency.
        item = table.get_item(
            Key=key,
            ConsistentRead=True,
        )["Item"]

        # Check the stored identity, verifier, and expiration.
        assert item["user_id"] == user_id
        assert item["code_verifier"] == verifier
        assert before + 600 <= item["expires_at"] <= int(time()) + 600
    finally:
        # Clean up this test's record even if an assertion fails.
        table.delete_item(Key=key)

    # Confirm that cleanup removed the record.
    response = table.get_item(Key=key, ConsistentRead=True)
    assert "Item" not in response
