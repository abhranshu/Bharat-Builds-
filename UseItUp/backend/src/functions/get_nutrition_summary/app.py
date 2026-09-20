"""Returns daily nutrition summary — macro totals vs targets."""

from __future__ import annotations

import json
import logging
from datetime import date

from src.shared import dynamo_client
from src.shared.constants import (
    PK_PREFIX_HOUSEHOLD,
    SK_PREFIX_COOKED,
    SK_PREFIX_PROFILE,
)
from src.shared.models import GetNutritionSummaryResponse, NutritionInfo

logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
}

DEFAULT_TARGETS = {
    "daily_calorie_target": 2000.0,
    "daily_protein_target": 60.0,
    "daily_carbs_target": 300.0,
    "daily_fat_target": 65.0,
    "daily_fiber_target": 25.0,
}


def handler(event, context):
    """Lambda handler for GET /nutrition?household_id=xxx."""
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

        pk = f"{PK_PREFIX_HOUSEHOLD}{household_id}"

        # Get profile targets
        profile = dynamo_client.get_item(pk=pk, sk=SK_PREFIX_PROFILE) or {}

        targets = NutritionInfo(
            calories=profile.get("daily_calorie_target", DEFAULT_TARGETS["daily_calorie_target"]),
            protein=profile.get("daily_protein_target", DEFAULT_TARGETS["daily_protein_target"]),
            carbs=profile.get("daily_carbs_target", DEFAULT_TARGETS["daily_carbs_target"]),
            fat=profile.get("daily_fat_target", DEFAULT_TARGETS["daily_fat_target"]),
            fiber=profile.get("daily_fiber_target", DEFAULT_TARGETS["daily_fiber_target"]),
        )

        # Get today's cooked records
        today_iso = date.today().isoformat()
        cooked_records = dynamo_client.query_items(
            pk=pk, sk_prefix=f"{SK_PREFIX_COOKED}{today_iso}"
        )

        # Sum consumed nutrition
        consumed = NutritionInfo()
        for record in cooked_records:
            totals = record.get("nutrition_totals", {})
            consumed.calories += totals.get("calories", 0)
            consumed.protein += totals.get("protein", 0)
            consumed.carbs += totals.get("carbs", 0)
            consumed.fat += totals.get("fat", 0)
            consumed.fiber += totals.get("fiber", 0)

        # Compute remaining
        remaining = NutritionInfo(
            calories=round(max(0, targets.calories - consumed.calories), 1),
            protein=round(max(0, targets.protein - consumed.protein), 1),
            carbs=round(max(0, targets.carbs - consumed.carbs), 1),
            fat=round(max(0, targets.fat - consumed.fat), 1),
            fiber=round(max(0, targets.fiber - consumed.fiber), 1),
        )

        # Round consumed values
        consumed.calories = round(consumed.calories, 1)
        consumed.protein = round(consumed.protein, 1)
        consumed.carbs = round(consumed.carbs, 1)
        consumed.fat = round(consumed.fat, 1)
        consumed.fiber = round(consumed.fiber, 1)

        response = GetNutritionSummaryResponse(
            household_id=household_id,
            date=date.today(),
            consumed=consumed,
            targets=targets,
            remaining=remaining,
        )

        return {
            "statusCode": 200,
            "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
            "body": response.model_dump_json(),
        }

    except Exception as exc:
        logger.error("Error fetching nutrition summary: %s", exc)
        return {
            "statusCode": 500,
            "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Internal server error",
                "detail": str(exc),
                "status_code": 500,
            }),
        }
