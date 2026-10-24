import json
from decimal import Decimal
import pytest
from api.utils import DecimalEncoder


def test_decimal_encoder_integers():
    data = {"int_val": Decimal("10.00"), "real_int": Decimal("42")}
    encoded = json.dumps(data, cls=DecimalEncoder)
    assert encoded == '{"int_val": 10, "real_int": 42}'


def test_decimal_encoder_floats():
    data = {"float_val": Decimal("10.55")}
    encoded = json.dumps(data, cls=DecimalEncoder)
    assert encoded == '{"float_val": 10.55}'


def test_decimal_encoder_nested_and_standard_types():
    data = {
        "athlete": "Daniel",
        "distance": Decimal("12.30"),
        "points": Decimal("100.0"),
        "items": [Decimal("1.0"), Decimal("2.5")],
    }
    encoded = json.dumps(data, cls=DecimalEncoder)
    parsed = json.loads(encoded)
    assert parsed["athlete"] == "Daniel"
    assert parsed["distance"] == 12.3
    assert parsed["points"] == 100
    assert parsed["items"] == [1, 2.5]
