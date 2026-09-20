"""Returns current household inventory with expiry status."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.shared import dynamo_client
from src.shared.constants import (
    PK_PREFIX_HOUSEHOLD,
    SK_PREFIX_ITEM,
)
from src.shared.ingredient_catalog import get_canonical_name
from src.shared.expiry_predictor import days_until_expiry, expiry_status_label
from src.shared.models import GetInventoryResponse, Ingredient

logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
}


def handler(event, context):
    """Lambda handler for GET /inventory?household_id=xxx."""
    try:
        query_params = event.get("queryStringParameters") or {}
        household_id = query_params.get("household_id")

        if not household_id:
            return {
                "statusCode": 400,
                "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "Missing required parameter: household_id",
                    "status_code": 400,
                }),
            }

        # Query all ITEM# records for the household
        pk = f"{PK_PREFIX_HOUSEHOLD}{household_id}"
        items = dynamo_client.query_items(pk=pk, sk_prefix=SK_PREFIX_ITEM)

        # Build ingredient list with expiry info
        ingredients = []
        for item in items:
            from datetime import date as date_type

            predicted_expiry_str = item.get("predicted_expiry", "")
            try:
                predicted_expiry = date_type.fromisoformat(predicted_expiry_str)
                days_left = days_until_expiry(predicted_expiry)
                status = expiry_status_label(predicted_expiry)
            except (ValueError, TypeError):
                days_left = None
                status = "unknown"

            ingredient = Ingredient(
                ingredient_id=item.get("ingredient_id", ""),
                name=get_canonical_name(item.get("ingredient_id", "")),
                quantity_g=float(item.get("quantity_g", 0)),
                purchase_date=item.get("purchase_date", ""),
                predicted_expiry=item.get("predicted_expiry", ""),
                source=item.get("source", "bill"),
                expiry_confidence=item.get("expiry_confidence", "high"),
            )
            ingredients.append(ingredient)

        # Sort by expiry (soonest first)
        ingredients.sort(key=lambda x: x.predicted_expiry)

        response = GetInventoryResponse(
            household_id=household_id,
            items=ingredients,
            count=len(ingredients),
        )

        return {
            "statusCode": 200,
            "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
            "body": response.model_dump_json(),
        }

    except Exception as exc:
        logger.error("Error fetching inventory: %s", exc)
        return {
            "statusCode": 500,
            "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Internal server error",
                "detail": str(exc),
                "status_code": 500,
            }),
        }
