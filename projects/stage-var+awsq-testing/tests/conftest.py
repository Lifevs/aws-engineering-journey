import os
import uuid
import boto3
import pytest

TABLE_NAME = "LambdaEventTable"
REGION = os.environ.get("AWS_REGION", "us-east-1")

# Fixed IDs so tests can reference them deterministically
SEED_ID = f"test-{uuid.uuid4()}"
SEED_SORT_1 = "2026-07-01"
SEED_SORT_2 = "2026-07-02"


@pytest.fixture(scope="session")
def api_base_url():
    """
    Reads API_BASE_URL and STAGE from env.
    API_BASE_URL should be the full base, e.g.:
      https://k9vv820z63.execute-api.us-east-1.amazonaws.com
    STAGE defaults to 'dev'.
    """
    base = os.environ["API_BASE_URL"].rstrip("/")
    stage = os.environ.get("STAGE", "dev")
    return f"{base}/{stage}"


@pytest.fixture(scope="session")
def ddb_table():
    return boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)


@pytest.fixture(autouse=True)
def seed_and_teardown(ddb_table):
    """Seed two items before every test, delete them after."""
    items = [
        {"id": SEED_ID, "createdAt": SEED_SORT_1, "name": "Alpha", "score": 42},
        {"id": SEED_ID, "createdAt": SEED_SORT_2, "name": "Beta",  "score": 7},
    ]
    for item in items:
        ddb_table.put_item(Item=item)

    yield  # test runs here

    for item in items:
        ddb_table.delete_item(Key={"id": item["id"], "createdAt": item["createdAt"]})
