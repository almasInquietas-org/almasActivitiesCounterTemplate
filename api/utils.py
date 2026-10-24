"""
utils.py - Custom JSON encoders and utility functions.
"""
import json
from decimal import Decimal
from typing import Any


class DecimalEncoder(json.JSONEncoder):
    """
    JSON encoder that converts Decimal objects returned by DynamoDB
    to int (if whole number) or float.
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)
