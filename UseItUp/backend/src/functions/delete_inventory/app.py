"""Delete an ingredient from household inventory."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from src.shared import dynamo_client
from src.shared.constants import PK_PREFIX_HOUSEHOLD, SK_PREFIX_ITEM
from src.shared.models import DeleteInventoryRequest, DeleteInventoryResponse

logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
}


def handler(event, context):
    """Lambda handler for DELETE /inventory."""
    try:
        data: dict[str, Any] = {}

        # Support both JSON body and query string parameters
        if event.get("body"):
            raw_body = event["body"]
            if isinstance(raw_body, str):
                try:
                    data = json.loads(raw_body)
                except json.JSONDecodeError as exc:
                    return {
                        "statusCode": 400,
                        "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
                        "body": json.dumps({"error": "Invalid JSON body", "detail": str(exc)}),
                    }
            elif isinstance(raw_body, dict):
                data = raw_body

        # Merge or fallback to queryStringParameters
        query_params = event.get("queryStringParameters") or {}
        for key, val in query_params.items():
            if key not in data or not data[key]:
                data[key] = val

        if not data.get("household_id"):
            return {
                "statusCode": 400,
                "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "Missing required field: household_id",
                    "status_code": 400,
                }),
            }

        request = DeleteInventoryRequest(**data)

        if not request.item_sk and not request.ingredient_id:
            return {
                "statusCode": 400,
                "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "Provide either item_sk or ingredient_id to delete",
                    "status_code": 400,
                }),
            }

        pk = f"{PK_PREFIX_HOUSEHOLD}{request.household_id}"
        deleted_sk = None

        if request.item_sk:
            sk = request.item_sk
            if not sk.startswith(SK_PREFIX_ITEM):
                sk = f"{SK_PREFIX_ITEM}{sk}"
            dynamo_client.delete_item(pk=pk, sk=sk)
            deleted_sk = sk
            logger.info("Deleted inventory item %s for household=%s", sk, request.household_id)
        elif request.ingredient_id:
            # Look up matching ITEM# records for this ingredient
            existing_items = dynamo_client.query_items(pk=pk, sk_prefix=SK_PREFIX_ITEM)
            matching = [
                it for it in existing_items
                if it.get("ingredient_id") == request.ingredient_id
                or it.get("SK", "").startswith(f"{SK_PREFIX_ITEM}{request.ingredient_id}")
            ]
            for it in matching:
                sk = it.get("SK", "")
                if sk:
                    dynamo_client.delete_item(pk=pk, sk=sk)
                    deleted_sk = sk
                    logger.info("Deleted inventory item %s for household=%s", sk, request.household_id)

        response = DeleteInventoryResponse(
            message="Removed item from inventory.",
            household_id=request.household_id,
            deleted_sk=deleted_sk,
            ingredient_id=request.ingredient_id,
        )

        return {
            "statusCode": 200,
            "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
            "body": response.model_dump_json(),
        }

    except ValidationError as exc:
        logger.warning("Validation error in delete_inventory: %s", exc)
        return {
            "statusCode": 400,
            "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Validation error",
                "detail": str(exc),
                "status_code": 400,
            }),
        }

    except Exception as exc:
        logger.error("Error deleting inventory item: %s", exc)
        return {
            "statusCode": 500,
            "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Internal server error",
                "detail": str(exc),
                "status_code": 500,
            }),
        }
