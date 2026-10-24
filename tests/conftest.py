import os
import pytest
import boto3
from moto import mock_aws

# Ensure dummy credentials and test region are set before any boto3 client initializes
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"
os.environ["AWS_REGION"] = "eu-west-1"

# Force DEV table names for tests
os.environ["ATHLETES_TABLE_NAME"] = "ATHLETES_DEV"
os.environ["ACTIVITIES_TABLE_NAME"] = "ACTIVITIES_DEV"


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
