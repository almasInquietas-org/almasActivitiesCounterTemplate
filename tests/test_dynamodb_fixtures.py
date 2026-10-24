import pytest
from moto import mock_aws
from api import api_config


def test_dynamodb_fixtures_tables_created(dynamodb_mock):
    """Verify that moto initializes ATHLETES_DEV and ACTIVITIES_DEV tables."""
    table_names = [table.name for table in dynamodb_mock.tables.all()]
    assert api_config.ATHLETES_TABLE_NAME in table_names
    assert api_config.ACTIVITIES_TABLE_NAME in table_names

    athletes_table = dynamodb_mock.Table(api_config.ATHLETES_TABLE_NAME)
    assert athletes_table.key_schema == [{"AttributeName": "athlete_id", "KeyType": "HASH"}]

    activities_table = dynamodb_mock.Table(api_config.ACTIVITIES_TABLE_NAME)
    assert activities_table.key_schema == [{"AttributeName": "activity_id", "KeyType": "HASH"}]
