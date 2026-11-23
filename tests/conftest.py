import dataclasses
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
os.environ["AWS_DEFAULT_REGION"] = "eu-north-1"
os.environ["AWS_REGION"] = "eu-north-1"

# Force DEV table names and test CORS origin before api_config initializes
os.environ["ATHLETES_TABLE_NAME"] = "ATHLETES_DEV"
os.environ["ACTIVITIES_TABLE_NAME"] = "ACTIVITIES_DEV"
os.environ["CORS_ALLOWED_ORIGINS"] = "*"


@pytest.fixture(autouse=True)
def reset_global_test_state(monkeypatch):
    """
    Ensure rate limiter and auth tokens are cleared before each test,
    and config values are reset to clean load_config() defaults.
    """
    auth.clear_tokens()
    rate_limiter.clear_history()

    default_cfg = config.load_config({
        "AWS_REGION": "eu-north-1",
        "ATHLETES_TABLE_NAME": "ATHLETES_DEV",
        "ACTIVITIES_TABLE_NAME": "ACTIVITIES_DEV",
        "CORS_ALLOWED_ORIGINS": "*",
    })

    monkeypatch.setattr(config, "CONFIG", default_cfg)
    for field in dataclasses.fields(config.AppConfig):
        val = getattr(default_cfg, field.name)
        if isinstance(val, tuple):
            val = list(val)
        monkeypatch.setattr(config, field.name, val)


@pytest.fixture(scope="session")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-north-1"


@pytest.fixture
def dynamodb_mock(aws_credentials):
    """Provides a mocked DynamoDB resource with ATHLETES and ACTIVITIES tables initialized."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="eu-north-1")

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
