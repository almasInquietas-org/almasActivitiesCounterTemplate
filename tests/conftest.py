import os
import pytest
import boto3
from moto import mock_aws
from api import api_config as config, auth, rate_limiter

# Ensure dummy credentials and test region are set before any boto3 client initializes
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"
os.environ["AWS_REGION"] = "eu-west-1"

# Force DEV table names and test defaults for tests
os.environ["ATHLETES_TABLE_NAME"] = "ATHLETES_DEV"
os.environ["ACTIVITIES_TABLE_NAME"] = "ACTIVITIES_DEV"
os.environ["INTERVALS_OAUTH_BASE_URL"] = "https://intervals.icu"
os.environ["AUTH_TOLERANCE_SECONDS"] = "300"
os.environ["TOKEN_TTL_SECONDS"] = "300"
os.environ["RATE_LIMIT_MAX"] = "30"
os.environ["RATE_LIMIT_WINDOW"] = "60"
os.environ["CORS_ALLOWED_ORIGINS"] = "*"
os.environ["GOAL_KM"] = "500.0"
os.environ["LAST_ACT"] = "10"
os.environ["TITLE"] = "Almas Inquietas Activities"


@pytest.fixture(autouse=True)
def reset_global_test_state(monkeypatch):
    """
    Ensure rate limiter and auth tokens are cleared before each test,
    and config values are initialized to test defaults.
    """
    auth.clear_tokens()
    rate_limiter.clear_history()

    monkeypatch.setattr(config, "AWS_REGION", "eu-west-1")
    monkeypatch.setattr(config, "ATHLETES_TABLE_NAME", "ATHLETES_DEV")
    monkeypatch.setattr(config, "ACTIVITIES_TABLE_NAME", "ACTIVITIES_DEV")
    monkeypatch.setattr(config, "INTERVALS_OAUTH_BASE_URL", "https://intervals.icu")
    monkeypatch.setattr(config, "INTERVALS_CLIENT_ID", "")
    monkeypatch.setattr(config, "INTERVALS_CLIENT_SECRET", "")
    monkeypatch.setattr(config, "INTERVALS_WEBHOOK_SECRET", "")
    monkeypatch.setattr(config, "API_KEY", "")
    monkeypatch.setattr(config, "API_SIGNING_SECRET", "")
    monkeypatch.setattr(config, "AUTH_TOLERANCE_SECONDS", 300)
    monkeypatch.setattr(config, "TOKEN_TTL_SECONDS", 300)
    monkeypatch.setattr(config, "RATE_LIMIT_MAX", 30)
    monkeypatch.setattr(config, "RATE_LIMIT_WINDOW", 60)
    monkeypatch.setattr(config, "CORS_ALLOWED_ORIGINS", ["*"])
    monkeypatch.setattr(config, "GOAL_KM", 500.0)
    monkeypatch.setattr(config, "LAST_ACT", 10)
    monkeypatch.setattr(config, "TITLE", "Almas Inquietas Activities")
    monkeypatch.setattr(config, "CHECKPOINTS", [])
    monkeypatch.setattr(config, "ACT_TYPE_FILTER", "")
    monkeypatch.setattr(config, "ACT_TITLE_FILTER", "")
    monkeypatch.setattr(config, "START_DATE", "")
    monkeypatch.setattr(config, "CLUB_FILTER", "")


@pytest.fixture(scope="session")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"


@pytest.fixture
def dynamodb_mock(aws_credentials):
    """Provides a mocked DynamoDB resource with ATHLETES and ACTIVITIES tables initialized."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="eu-west-1")

        # Create ATHLETES table (PK: athlete_id [String])
        athletes_table = dynamodb.create_table(
            TableName="ATHLETES_DEV",
            KeySchema=[{"AttributeName": "athlete_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "athlete_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        athletes_table.wait_until_exists()

        # Create ACTIVITIES table (PK: activity_id [String])
        activities_table = dynamodb.create_table(
            TableName="ACTIVITIES_DEV",
            KeySchema=[{"AttributeName": "activity_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "activity_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        activities_table.wait_until_exists()

        yield dynamodb
