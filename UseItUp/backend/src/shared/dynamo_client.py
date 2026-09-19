"""DynamoDB single-table client.

Wraps boto3 DynamoDB calls for get/put/query/delete operations
against the AppData table (PK + SK single-table design).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key

from .constants import TABLE_NAME

logger = logging.getLogger(__name__)

_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(TABLE_NAME)


# ============================================
# HELPERS
# ============================================

def _serialize(value: Any) -> Any:
    """Convert Python types to DynamoDB-compatible types."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    return value


def _deserialize(value: Any) -> Any:
    """Convert DynamoDB types back to Python types."""
    if isinstance(value, Decimal):
        return float(value) if value != int(value) else int(value)
    if isinstance(value, list):
        return [_deserialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _deserialize(v) for k, v in value.items()}
    return value


def _to_item(data: dict) -> dict:
    """Prepare a dict for DynamoDB put."""
    serialized = _serialize(data)
    # Remove None values
    return {k: v for k, v in serialized.items() if v is not None}


# ============================================
# CRUD OPERATIONS
# ============================================

def put_item(
    pk: str,
    sk: str,
    data: dict,
    extra_attrs: Optional[dict] = None,
) -> dict:
    """Put an item into DynamoDB."""
    item = {
        "PK": pk,
        "SK": sk,
        **_to_item(data),
    }
    if extra_attrs:
        item.update(_to_item(extra_attrs))

    _table.put_item(Item=item)
    logger.info("Put item PK=%s SK=%s", pk, sk)
    return item


def get_item(pk: str, sk: str) -> Optional[dict]:
    """Get a single item by PK + SK."""
    resp = _table.get_item(Key={"PK": pk, "SK": sk})
    item = resp.get("Item")
    if item:
        return _deserialize(item)
    return None


def query_items(
    pk: str,
    sk_prefix: Optional[str] = None,
    sk_between: Optional[tuple[str, str]] = None,
    filter_expression: Optional[Attr] = None,
    index_name: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """Query items by PK with optional SK conditions."""
    key_condition = Key("PK").eq(pk)

    if sk_prefix:
        key_condition = key_condition & Key("SK").begins_with(sk_prefix)
    elif sk_between:
        key_condition = key_condition & Key("SK").between(*sk_between)

    kwargs: dict[str, Any] = {
        "KeyConditionExpression": key_condition,
    }

    if filter_expression:
        kwargs["FilterExpression"] = filter_expression
    if index_name:
        kwargs["IndexName"] = index_name
    if limit:
        kwargs["Limit"] = limit

    items = []
    last_evaluated_key = None

    while True:
        if last_evaluated_key:
            kwargs["ExclusiveStartKey"] = last_evaluated_key

        resp = _table.query(**kwargs)
        items.extend(resp.get("Items", []))
        last_evaluated_key = resp.get("LastEvaluatedKey")

        if not last_evaluated_key:
            break
        if limit and len(items) >= limit:
            break

    return _deserialize(items)


def query_gsi1(
    gsi1pk: str,
    gsi1sk_prefix: Optional[str] = None,
) -> list[dict]:
    """Query GSI1 by GSI1PK with optional GSI1SK prefix."""
    key_condition = Key("GSI1PK").eq(gsi1pk)

    if gsi1sk_prefix:
        key_condition = key_condition & Key("GSI1SK").begins_with(gsi1sk_prefix)

    resp = _table.query(
        IndexName="GSI1",
        KeyConditionExpression=key_condition,
    )
    return _deserialize(resp.get("Items", []))


def update_item(
    pk: str,
    sk: str,
    updates: dict,
) -> dict:
    """Update specific attributes on an item."""
    if not updates:
        return {}

    serialized = _to_item(updates)
    update_expr_parts = []
    expr_attr_values = {}
    expr_attr_names = {}

    for i, (key, value) in enumerate(serialized.items()):
        placeholder = f"#f{i}"
        value_placeholder = f":v{i}"
        update_expr_parts.append(f"{placeholder} = {value_placeholder}")
        expr_attr_names[placeholder] = key
        expr_attr_values[value_placeholder] = value

    resp = _table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression=f"SET {', '.join(update_expr_parts)}",
        ExpressionAttributeNames=expr_attr_names,
        ExpressionAttributeValues=expr_attr_values,
        ReturnValues="ALL_NEW",
    )

    return _deserialize(resp.get("Attributes", {}))


def delete_item(pk: str, sk: str) -> None:
    """Delete an item by PK + SK."""
    _table.delete_item(Key={"PK": pk, "SK": sk})
    logger.info("Deleted item PK=%s SK=%s", pk, sk)


def scan(
    filter_expression: Optional[Attr] = None,
    projection_expression: Optional[str] = None,
    index_name: Optional[str] = None,
) -> list[dict]:
    """Full table scan with optional filter."""
    kwargs: dict[str, Any] = {}

    if filter_expression:
        kwargs["FilterExpression"] = filter_expression
    if projection_expression:
        kwargs["ProjectionExpression"] = projection_expression
    if index_name:
        kwargs["IndexName"] = index_name

    items = []
    last_evaluated_key = None

    while True:
        if last_evaluated_key:
            kwargs["ExclusiveStartKey"] = last_evaluated_key

        resp = _table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        last_evaluated_key = resp.get("LastEvaluatedKey")

        if not last_evaluated_key:
            break

    return _deserialize(items)
