"""S3-triggered: Processes fridge photos via Bedrock Vision.

Flow:
1. Download image from S3
2. Call Bedrock Vision to identify ingredients
3. Map to canonical ingredient_ids constrained to catalog
4. Use current date as fallback purchase_date (estimated confidence)
5. Predict expiry dates
6. Write ITEM# records to DynamoDB
7. Update UPLOAD# record status to "processed"
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Optional
from urllib.parse import unquote

import boto3

from src.shared import dynamo_client
from src.shared.constants import (
    PK_PREFIX_HOUSEHOLD,
    PK_PREFIX_CATALOG,
    SK_PREFIX_ITEM,
    SK_PREFIX_PROFILE,
    SK_PREFIX_UPLOAD,
    UPLOAD_SUFFIX_FRIDGE,
)
from src.shared.bedrock_client import invoke_bedrock_vision
from src.shared.ingredient_catalog import (
    get_catalog_for_prompt,
    get_expanded_catalog_prompt,
    is_valid_ingredient,
)
from src.shared.expiry_predictor import predict_expiry

logger = logging.getLogger(__name__)

_s3 = boto3.client("s3")


def handler(event, context):
    """Lambda handler triggered by S3 ObjectCreated."""
    try:
        # Parse S3 event
        record = event["Records"][0]
        bucket = record["s3"]["bucket"]["name"]
        # S3 event keys are URL-encoded; decode before parsing.
        key = unquote(record["s3"]["object"]["key"])

        # Defensive check: the S3 notification filters on the _fridge.jpg
        # suffix, but re-verify in case the function is invoked with another
        # object.
        parsed_key = _parse_fridge_key(key)
        if parsed_key is None:
            logger.warning("Ignoring non-fridge-photo object: %s", key)
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {"message": "Ignored: not a fridge photo"}
                ),
            }

        household_id, image_id = parsed_key

        logger.info("Processing fridge photo: household=%s image=%s", household_id, image_id)

        # Step 1: Download image from S3
        image_obj = _s3.get_object(Bucket=bucket, Key=key)
        image_bytes = image_obj["Body"].read()

        # Step 2: Analyze with Bedrock Vision
        pk = f"{PK_PREFIX_HOUSEHOLD}{household_id}"
        profile = dynamo_client.get_item(pk=pk, sk=SK_PREFIX_PROFILE) or {}
        custom_items = profile.get("additional_valid_ingredients") or []

        catalog_text = get_expanded_catalog_prompt(custom_items)

        vision_prompt = f"""Analyze this fridge photo and identify all visible food ingredients.

For each ingredient you find, return it as a JSON object with:
- "ingredient_id": MUST be one of the valid IDs from the catalog or additional valid ingredients below (lowercase_with_underscores)
- "estimated_quantity_g": your best guess of the quantity in grams

VALID INGREDIENTS:
{catalog_text}

Rules:
- Only include items you can ACTUALLY SEE in the image
- You MUST use only ingredient_ids from the valid ingredients list above
- If you see something not in the valid ingredients list, skip it
- Estimate quantity realistically (a full tomato ≈ 150g, a handful of coriander ≈ 30g)
- Return ONLY a JSON array of objects, nothing else"""

        result = invoke_bedrock_vision(
            image_bytes=image_bytes,
            image_format="jpeg",
            prompt=vision_prompt,
            system_prompt=(
                "You are a food recognition AI for Indian households. "
                "Identify ingredients from photos of fridge contents."
            ),
        )

        if not isinstance(result, list):
            logger.warning("Bedrock returned non-array: %s", type(result))
            result = []

        # Step 3: Use current date as fallback purchase_date
        photo_date = date.today()

        # Step 4: Write ITEM# records
        written_count = 0
        for item in result:
            ingredient_id = item.get("ingredient_id", "")
            if not ingredient_id:
                continue
            if not is_valid_ingredient(ingredient_id, custom_items):
                logger.info("Skipping invalid item not in catalog or custom items: %s", ingredient_id)
                continue

            quantity_g = item.get("estimated_quantity_g", 200)

            # For fridge photos, confidence is "estimated"
            predicted_expiry, confidence = predict_expiry(
                ingredient_id, photo_date, source="fridge_photo"
            )

            item_id = f"{ingredient_id}_{image_id}"
            pk = f"{PK_PREFIX_HOUSEHOLD}{household_id}"
            sk = f"{SK_PREFIX_ITEM}{item_id}"

            dynamo_client.put_item(
                pk=pk,
                sk=sk,
                data={
                    "ingredient_id": ingredient_id,
                    "quantity_g": quantity_g,
                    "purchase_date": photo_date.isoformat(),
                    "predicted_expiry": predicted_expiry.isoformat(),
                    "source": "fridge_photo",
                    "expiry_confidence": confidence,
                },
                extra_attrs={
                    "GSI1PK": f"{PK_PREFIX_CATALOG}{ingredient_id}",
                    "GSI1SK": household_id,
                },
            )
            written_count += 1

        # Step 5: Update UPLOAD# record status
        upload_pk = f"{PK_PREFIX_HOUSEHOLD}{household_id}"
        upload_sk = f"{SK_PREFIX_UPLOAD}{image_id}"

        dynamo_client.update_item(
            pk=upload_pk,
            sk=upload_sk,
            updates={
                "status": "processed",
                "item_count": written_count,
                "processed_at": datetime.utcnow().isoformat(),
                "raw_output": {"identified_items": result},
            },
        )

        logger.info(
            "Fridge photo processed: %d items for household=%s",
            written_count,
            household_id,
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Fridge photo processed successfully",
                "items_identified": written_count,
            }),
        }

    except Exception as exc:
        logger.error("Fridge photo processing failed: %s", exc)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal server error",
                "detail": str(exc),
                "status_code": 500,
            }),
        }


def _parse_fridge_key(key: str) -> Optional[tuple[str, str]]:
    """Parse an S3 key of the form
    ``uploads/{household_id}/{image_id}_{timestamp}_fridge.jpg``.

    Returns ``(household_id, image_id)``, or ``None`` if the key is not a
    fridge photo (e.g. a bill).
    """
    parts = key.split("/")
    if len(parts) < 3 or not parts[2].endswith(UPLOAD_SUFFIX_FRIDGE):
        return None
    return parts[1], parts[2].split("_")[0]
