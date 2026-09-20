"""Manually add an ingredient to household inventory."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from pydantic import BaseModel, Field, field_validator

from src.shared import dynamo_client
from src.shared.constants import PK_PREFIX_HOUSEHOLD, SK_PREFIX_ITEM
from src.shared.ingredient_catalog import (
    get_shelf_life,
    get_canonical_name,
    get_all_ingredient_ids,
)
from src.shared.models import UploadType

logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
}


class AddInventoryRequest(BaseModel):
    household_id: str = Field(..., min_length=1)
    ingredient_id: str = Field(..., min_length=1)
    quantity_g: float = Field(..., gt=0)

    @field_validator("ingredient_id")
    @classmethod
    def validate_ingredient_id(cls, v: str) -> str:
        v = v.strip().lower().replace(" ", "_")
        if v not in get_all_ingredient_ids():
            raise ValueError(
                f"Unknown ingredient '{v}'. "
                f"Valid IDs: {', '.join(sorted(get_all_ingredient_ids()))}"
            )
        return v


def handler(event, context):
    """Lambda handler for POST /inventory — add a single ingredient."""
    try:
        raw_body = event.get("body", "{}")
        if isinstance(raw_body, str):
            body = json.loads(raw_body)
        elif isinstance(raw_body, dict):
            body = raw_body
        else:
            return {
                "statusCode": 400,
                "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
                "body": json.dumps({"error": "Request body must be a JSON object"}),
            }

        request = AddInventoryRequest(**body)

        pk = f"{PK_PREFIX_HOUSEHOLD}{request.household_id}"
        today = date.today()
        shelf_life = get_shelf_life(request.ingredient_id)
        predicted_expiry = today + timedelta(days=shelf_life)

        ingredient_sk = f"{SK_PREFIX_ITEM}{request.ingredient_id}_{today.isoformat()}"

        dynamo_client.put_item(
            pk=pk,
            sk=ingredient_sk,
            data={
                "ingredient_id": request.ingredient_id,
                "quantity_g": request.quantity_g,
                "purchase_date": today.isoformat(),
                "predicted_expiry": predicted_expiry.isoformat(),
                "source": UploadType.BILL.value,
                "expiry_confidence": "high",
            },
        )

        logger.info(
            "Added %s (%.0fg) for household=%s",
            request.ingredient_id,
            request.quantity_g,
            request.household_id,
        )

        return {
            "statusCode": 200,
            "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
            "body": json.dumps({
                "message": f"Added {get_canonical_name(request.ingredient_id)} ({request.quantity_g}g)",
                "ingredient_id": request.ingredient_id,
                "quantity_g": request.quantity_g,
                "predicted_expiry": predicted_expiry.isoformat(),
            }),
        }

    except Exception as exc:
        logger.error("Error adding inventory item: %s", exc)
        status = 400 if "validation" in str(type(exc).__name__).lower() else 500
        return {
            "statusCode": status,
            "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Validation error" if status == 400 else "Internal server error",
                "detail": str(exc),
                "status_code": status,
            }),
        }
