"""EventBridge-triggered daily cron.

Scans all households for items expiring within 24-48 hours
and sends SNS notifications to nudge users.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any

import boto3

from src.shared import dynamo_client
from src.shared.constants import (
    PK_PREFIX_HOUSEHOLD,
    SK_PREFIX_ITEM,
    SNS_TOPIC_ARN,
)
from src.shared.ingredient_catalog import get_canonical_name
from src.shared.expiry_predictor import days_until_expiry, is_expiring_soon

logger = logging.getLogger(__name__)

_sns = boto3.client("sns")


def handler(event, context):
    """Lambda handler triggered by EventBridge Schedule."""
    try:
        today = date.today()
        tomorrow = today + timedelta(days=1)
        day_after = today + timedelta(days=2)

        logger.info("Running expiry check for %s", today.isoformat())

        # Scan all ITEM# records
        all_items = dynamo_client.scan()

        # Group expiring items by household
        household_expiring: dict[str, list[dict]] = {}

        for item in all_items:
            sk = item.get("SK", "")
            if not sk.startswith(SK_PREFIX_ITEM):
                continue

            pk = item.get("PK", "")
            if not pk.startswith(PK_PREFIX_HOUSEHOLD):
                continue

            household_id = pk.replace(PK_PREFIX_HOUSEHOLD, "")

            predicted_expiry_str = item.get("predicted_expiry", "")
            try:
                predicted_expiry = date.fromisoformat(predicted_expiry_str)
            except (ValueError, TypeError):
                continue

            if is_expiring_soon(predicted_expiry, within_days=2, reference_date=today):
                if household_id not in household_expiring:
                    household_expiring[household_id] = []

                days = days_until_expiry(predicted_expiry, today)
                status = "expired" if days < 0 else f"{days} day{'s' if days != 1 else ''}"

                household_expiring[household_id].append({
                    "ingredient_id": item.get("ingredient_id", ""),
                    "name": get_canonical_name(item.get("ingredient_id", "")),
                    "quantity_g": item.get("quantity_g", 0),
                    "predicted_expiry": predicted_expiry_str,
                    "days_until_expiry": days,
                    "status": status,
                })

        if not household_expiring:
            logger.info("No expiring items found across any household")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "No expiring items",
                    "households_notified": 0,
                }),
            }

        # Send SNS notifications per household
        notified_count = 0
        for household_id, items in household_expiring.items():
            message = _build_notification_message(household_id, items)

            if SNS_TOPIC_ARN:
                try:
                    _sns.publish(
                        TopicArn=SNS_TOPIC_ARN,
                        Subject=f"UseItUp: {len(items)} item(s) expiring soon",
                        Message=message,
                        MessageAttributes={
                            "household_id": {
                                "DataType": "String",
                                "StringValue": household_id,
                            },
                        },
                    )
                    notified_count += 1
                    logger.info(
                        "Sent expiry notification for household=%s (%d items)",
                        household_id,
                        len(items),
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to send SNS for household=%s: %s",
                        household_id,
                        exc,
                    )
            else:
                logger.warning(
                    "SNS_TOPIC_ARN not set, skipping notification for household=%s",
                    household_id,
                )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Expiry check completed",
                "households_with_expiring_items": len(household_expiring),
                "households_notified": notified_count,
            }),
        }

    except Exception as exc:
        logger.error("Expiry check failed: %s", exc)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal server error",
                "detail": str(exc),
                "status_code": 500,
            }),
        }


def _build_notification_message(household_id: str, items: list[dict]) -> str:
    """Build a human-readable SNS notification message."""
    lines = [
        f"UseItUp — Expiry Alert for Household {household_id[:8]}...",
        "",
        "The following items in your fridge are expiring soon:",
        "",
    ]

    for item in sorted(items, key=lambda x: x["days_until_expiry"]):
        lines.append(
            f"  • {item['name']} ({item['quantity_g']}g) — {item['status']}"
        )

    lines.extend([
        "",
        "Don't let them go to waste!",
        "Open UseItUp to get recipe ideas using these ingredients.",
        "",
        f"Items: {len(items)}",
    ])

    return "\n".join(lines)
