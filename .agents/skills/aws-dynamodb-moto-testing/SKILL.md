---
name: aws-dynamodb-moto-testing
description: >-
  Guidelines and patterns for AWS Lambda Function URLs (v1.0 and v2.0), DynamoDB
  operations with boto3 (ATHLETES and ACTIVITIES tables), Decimal conversion,
  idempotent conditional writes, and local unit testing with pytest and moto.
  Use when editing api/db.py, api/services.py, api/backend_source.py, or tests/conftest.py.
---

# AWS Lambda, DynamoDB & Moto Testing Skill

## 1. DynamoDB Table Conventions (`api/db.py`)

### Table Access Pattern
Resolve tables via a helper or module-level `boto3.resource('dynamodb', region_name=config.AWS_REGION)` using `config.ATHLETES_TABLE_NAME` and `config.ACTIVITIES_TABLE_NAME`.

### Table 1: `ATHLETES_<ENV>` (PK: `athlete_id` [String])
- **Upsert Athlete & Club Membership (`save_athlete`):**
  - Fetch existing record (or use `update_item` / `put_item`) so that `clubs` remains a deduplicated list of strings (e.g., `["almas_inquietas", "secondary_club"]`).
  - Always store `athlete_id` as `str`, `athlete_name` as `str`, `access_token` as `str`, `clubs` as `list[str]`, and `updated_at` as ISO 8601 UTC string.
- **Lookup Athlete (`get_athlete`):**
  - Use `table.get_item(Key={'athlete_id': str(athlete_id)})` for $O(1)$ retrieval during webhook ingestion.
  - Return `response.get('Item')` (or `None` if not found).

### Table 2: `ACTIVITIES_<ENV>` (PK: `activity_id` [String])
- **Numeric Types in DynamoDB:**
  - `boto3` rejects Python `float` types. Always convert floats via `Decimal(str(round(val, 2)))`.
  - Distance from Intervals.icu is in **meters**; convert to km via `Decimal(str(round(distance_meters / 1000, 2)))`.
- **Idempotent Activity Insert (`save_activity`):**
  - Always use `ConditionExpression='attribute_not_exists(activity_id)'`.
  - Catch `botocore.exceptions.ClientError` where `e.response['Error']['Code'] == 'ConditionalCheckFailedException'` and return `False` (duplicate webhook delivery).
  - Return `True` when newly inserted.

## 2. Collision-Free Athlete Ranking (`api/services.py`)
- Group athlete statistics by `item.get('athlete_id')` (fallback to `item.get('athlete')` only if `athlete_id` is absent) so two athletes with the same display name never merge on the leaderboard.
- Output each ranked entry as:
  ```json
  {
    "athlete_name": "Daniel Fernandez",
    "currentKm": 123.45,
    "lastIncrement": 10.5
  }
  ```
  where `lastIncrement` is the `distance_km` of that athlete's activity with the highest `start_date`.

## 3. Lambda Function URL Event Parsing (`api/backend_source.py`)
Support both AWS Lambda Function URL payload v1.0 and v2.0:
- **HTTP Method:** `event.get('requestContext', {}).get('http', {}).get('method') or event.get('httpMethod', 'GET')`
- **Path:** `event.get('rawPath') or event.get('path', '/')`
- **Query Params:** `event.get('queryStringParameters') or {}`
- **Headers:** Normalize all keys to lowercase: `{k.lower(): v for k, v in (event.get('headers') or {}).items()}`
- **Client IP:** `event.get('requestContext', {}).get('http', {}).get('sourceIp') or event.get('requestContext', {}).get('identity', {}).get('sourceIp', '0.0.0.0')`
- **Body:** `event.get('body') or ''` (decode base64 if `event.get('isBase64Encoded')` is `True`).

## 4. Pytest + Moto Fixture Pattern (`tests/conftest.py`)
- Set dummy AWS credentials via `os.environ` (`AWS_ACCESS_KEY_ID='testing'`, `AWS_SECRET_ACCESS_KEY='testing'`, `AWS_DEFAULT_REGION='eu-west-1'`) **before** importing `api` modules.
- Use `with mock_aws():` (from `moto`) to create both `config.ATHLETES_TABLE_NAME` (`KeySchema=[{'AttributeName': 'athlete_id', 'KeyType': 'HASH'}]`) and `config.ACTIVITIES_TABLE_NAME` (`KeySchema=[{'AttributeName': 'activity_id', 'KeyType': 'HASH'}]`) with `BillingMode='PAY_PER_REQUEST'`.
