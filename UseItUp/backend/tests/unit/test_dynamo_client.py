"""Unit tests for DynamoDB client helpers."""

import pytest

from src.shared.dynamo_client import _serialize, _deserialize, _to_item
from datetime import date, datetime
from decimal import Decimal


class TestSerialize:
    """Tests for _serialize function."""

    def test_date_serialization(self):
        """Dates should be serialized to ISO format strings."""
        result = _serialize(date(2025, 1, 15))
        assert result == "2025-01-15"

    def test_datetime_serialization(self):
        """Datetimes should be serialized to ISO format strings."""
        result = _serialize(datetime(2025, 1, 15, 10, 30, 0))
        assert result == "2025-01-15T10:30:00"

    def test_float_to_decimal(self):
        """Floats should be converted to Decimal."""
        result = _serialize(3.14)
        assert isinstance(result, Decimal)
        assert result == Decimal("3.14")

    def test_int_preserved(self):
        """Integers should be preserved as-is."""
        result = _serialize(42)
        assert result == 42
        assert isinstance(result, int)

    def test_bool_preserved(self):
        """Booleans should be preserved."""
        result = _serialize(True)
        assert result is True

    def test_string_preserved(self):
        """Strings should be preserved."""
        result = _serialize("hello")
        assert result == "hello"

    def test_none_filtered(self):
        """None should be preserved (filtered later by _to_item)."""
        result = _serialize(None)
        assert result is None

    def test_nested_dict(self):
        """Nested dicts should be recursively serialized."""
        result = _serialize({"date": date(2025, 1, 1), "value": 3.14})
        assert result == {"date": "2025-01-01", "value": Decimal("3.14")}

    def test_list_serialization(self):
        """Lists should be recursively serialized."""
        result = _serialize([date(2025, 1, 1), 3.14])
        assert result == ["2025-01-01", Decimal("3.14")]


class TestDeserialize:
    """Tests for _deserialize function."""

    def test_decimal_to_float(self):
        """Decimal should be converted to float."""
        result = _deserialize(Decimal("3.14"))
        assert result == 3.14
        assert isinstance(result, float)

    def test_integer_decimal(self):
        """Whole number Decimal should become int."""
        result = _deserialize(Decimal("42"))
        assert result == 42
        assert isinstance(result, int)

    def test_string_preserved(self):
        """Strings should be preserved."""
        result = _deserialize("hello")
        assert result == "hello"

    def test_nested_dict(self):
        """Nested dicts should be recursively deserialized."""
        result = _deserialize({"value": Decimal("3.14")})
        assert result == {"value": 3.14}

    def test_nested_list(self):
        """Lists should be recursively deserialized."""
        result = _deserialize([Decimal("3.14"), "hello"])
        assert result == [3.14, "hello"]


class TestToItem:
    """Tests for _to_item function."""

    def test_none_values_filtered(self):
        """None values should be removed from the output."""
        result = _to_item({"a": 1, "b": None, "c": "hello"})
        assert result == {"a": 1, "c": "hello"}

    def test_empty_dict(self):
        """Empty dict should return empty dict."""
        result = _to_item({})
        assert result == {}

    def test_nested_serialization(self):
        """Nested values should be serialized."""
        result = _to_item({"date": date(2025, 1, 1), "count": None, "name": "test"})
        assert result == {"date": "2025-01-01", "name": "test"}
