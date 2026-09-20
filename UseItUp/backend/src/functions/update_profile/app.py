"""Updates household profile settings."""

from __future__ import annotations

import json
import logging

from src.shared import dynamo_client
from src.shared.constants import (
    PK_PREFIX_HOUSEHOLD,
    SK_PREFIX_PROFILE,
    DEFAULT_DAILY_CALORIE_TARGET,
    DEFAULT_DAILY_PROTEIN_TARGET,
    DEFAULT_HOUSEHOLD_SIZE,
    DEFAULT_LANGUAGE,
    DEFAULT_DIET_TYPE,
)
from pydantic import ValidationError
from src.shared.models import UpdateProfileRequest, UpdateProfileResponse, HouseholdProfile

logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
}


def handler(event, context):
    """Lambda handler for PUT /profile."""
    try:
        raw_body = event.get("body", "{}")
        if isinstance(raw_body, str):
            try:
                body = json.loads(raw_body)
            except json.JSONDecodeError as exc:
                return {
                    "statusCode": 400,
                    "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
                    "body": json.dumps({"error": "Invalid JSON body", "detail": str(exc)}),
                }
        elif isinstance(raw_body, dict):
            body = raw_body
        else:
            return {
                "statusCode": 400,
                "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
                "body": json.dumps({"error": "Request body must be a JSON object"}),
            }
        request = UpdateProfileRequest(**body)

        pk = f"{PK_PREFIX_HOUSEHOLD}{request.household_id}"

        # Build updates from non-None fields
        updates = {}
        if request.diet_type is not None:
            updates["diet_type"] = request.diet_type.value
        if request.household_size is not None:
            updates["household_size"] = request.household_size
        if request.language is not None:
            updates["language"] = request.language
        if request.daily_calorie_target is not None:
            updates["daily_calorie_target"] = request.daily_calorie_target
        if request.daily_protein_target is not None:
            updates["daily_protein_target"] = request.daily_protein_target

        if not updates:
            return {
                "statusCode": 400,
                "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "No fields to update",
                    "status_code": 400,
                }),
            }

        # Get existing profile or create default
        existing = dynamo_client.get_item(pk=pk, sk=SK_PREFIX_PROFILE) or {}

        # Merge updates
        merged = {
            "diet_type": updates.get("diet_type", existing.get("diet_type", DEFAULT_DIET_TYPE)),
            "household_size": updates.get("household_size", existing.get("household_size", DEFAULT_HOUSEHOLD_SIZE)),
            "language": updates.get("language", existing.get("language", DEFAULT_LANGUAGE)),
            "daily_calorie_target": updates.get(
                "daily_calorie_target",
                existing.get("daily_calorie_target", DEFAULT_DAILY_CALORIE_TARGET),
            ),
            "daily_protein_target": updates.get(
                "daily_protein_target",
                existing.get("daily_protein_target", DEFAULT_DAILY_PROTEIN_TARGET),
            ),
        }

        # Write to DynamoDB
        dynamo_client.put_item(
            pk=pk,
            sk=SK_PREFIX_PROFILE,
            data=merged,
        )

        profile = HouseholdProfile(**merged)

        response = UpdateProfileResponse(
            message="Profile updated successfully",
            profile=profile,
        )

        return {
            "statusCode": 200,
            "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
            "body": response.model_dump_json(),
        }

    except ValidationError as exc:
        logger.warning("Validation error: %s", exc)
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
        logger.error("Error updating profile: %s", exc)
        return {
            "statusCode": 500,
            "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Internal server error",
                "detail": str(exc),
                "status_code": 500,
            }),
        }
