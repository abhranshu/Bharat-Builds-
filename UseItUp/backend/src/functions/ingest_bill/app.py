"""S3-triggered: Processes grocery bills via Textract AnalyzeExpense.

Flow:
1. Download image from S3
2. Call Textract AnalyzeExpense to extract line items
3. Call Bedrock to map raw items → canonical ingredient_ids
4. Use expiry_predictor to compute expiry dates
5. Write ITEM# records to DynamoDB
6. Update UPLOAD# record status to "processed"
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
    SK_META,
    SK_PREFIX_ITEM,
    SK_PREFIX_PROFILE,
    SK_PREFIX_UPLOAD,
    UPLOAD_SUFFIX_BILL,
)
from src.shared.textract_client import analyze_expense, TextractExpenseResult
from src.shared.bedrock_client import invoke_bedrock
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

        # Defensive check: the S3 notification filters on the _bill.jpg suffix,
        # but re-verify in case the function is invoked with another object.
        parsed_key = _parse_bill_key(key)
        if parsed_key is None:
            logger.warning("Ignoring non-bill object: %s", key)
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Ignored: not a bill upload"}),
            }

        household_id, image_id = parsed_key

        logger.info("Processing bill upload: household=%s image=%s", household_id, image_id)

        # Step 1: Download image from S3
        image_obj = _s3.get_object(Bucket=bucket, Key=key)
        image_bytes = image_obj["Body"].read()

        # Step 2: Analyze with Textract
        expense_result: TextractExpenseResult = analyze_expense(image_bytes)

        # Step 2.5: Load household profile for custom valid items
        pk = f"{PK_PREFIX_HOUSEHOLD}{household_id}"
        profile = dynamo_client.get_item(pk=pk, sk=SK_PREFIX_PROFILE) or {}
        custom_items = profile.get("additional_valid_ingredients") or []

        # Step 3: Map raw items → canonical ingredient_ids via Bedrock
        raw_items = [item.to_dict() for item in expense_result.items]
        normalized_items = _normalize_items_with_bedrock(raw_items, custom_items=custom_items)

        # Step 4: Determine purchase date
        purchase_date = date.today()
        if expense_result.transaction_date:
            try:
                purchase_date = date.fromisoformat(expense_result.transaction_date)
            except (ValueError, TypeError):
                try:
                    purchase_date = datetime.strptime(
                        expense_result.transaction_date, "%d/%m/%Y"
                    ).date()
                except (ValueError, TypeError):
                    pass

        # Step 5: Write ITEM# records
        written_count = 0
        for item in normalized_items:
            ingredient_id = item["ingredient_id"]
            if not is_valid_ingredient(ingredient_id, custom_items):
                logger.info("Skipping invalid item not in catalog or custom items: %s", ingredient_id)
                continue
            quantity_g = item.get("quantity_g", 500)  # Default 500g if unknown

            predicted_expiry, confidence = predict_expiry(
                ingredient_id, purchase_date, source="bill"
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
                    "purchase_date": purchase_date.isoformat(),
                    "predicted_expiry": predicted_expiry.isoformat(),
                    "source": "bill",
                    "expiry_confidence": confidence,
                },
                extra_attrs={
                    "GSI1PK": f"{PK_PREFIX_CATALOG}{ingredient_id}",
                    "GSI1SK": household_id,
                },
            )
            written_count += 1

        # Step 6: Update UPLOAD# record status
        upload_pk = f"{PK_PREFIX_HOUSEHOLD}{household_id}"
        upload_sk = f"{SK_PREFIX_UPLOAD}{image_id}"

        dynamo_client.update_item(
            pk=upload_pk,
            sk=upload_sk,
            updates={
                "status": "processed",
                "item_count": written_count,
                "processed_at": datetime.utcnow().isoformat(),
                "raw_output": expense_result.to_dict(),
            },
        )

        logger.info(
            "Bill processed: %d items written for household=%s",
            written_count,
            household_id,
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Bill processed successfully",
                "items_extracted": written_count,
            }),
        }

    except ValueError as exc:
        logger.warning("Bill processing failed (validation): %s", exc)
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Could not process this image as a bill",
                "detail": str(exc),
                "status_code": 400,
            }),
        }

    except Exception as exc:
        logger.error("Bill processing failed: %s", exc)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal server error",
                "detail": str(exc),
                "status_code": 500,
            }),
        }


def _parse_bill_key(key: str) -> Optional[tuple[str, str]]:
    """Parse an S3 key of the form
    ``uploads/{household_id}/{image_id}_{timestamp}_bill.jpg``.

    Returns ``(household_id, image_id)``, or ``None`` if the key is not a
    bill upload (e.g. a fridge photo).
    """
    parts = key.split("/")
    if len(parts) < 3 or not parts[2].endswith(UPLOAD_SUFFIX_BILL):
        return None
    return parts[1], parts[2].split("_")[0]


def _normalize_items_with_bedrock(
    raw_items: list[dict],
    custom_items: list[str] | None = None,
) -> list[dict]:
    """Map raw Textract items to canonical ingredient_ids via Bedrock."""
    catalog_text = get_expanded_catalog_prompt(custom_items)

    prompt = f"""Map each of these grocery bill items to a canonical ingredient
from the catalog and additional valid ingredients below. Return ONLY a JSON array.

VALID INGREDIENTS:
{catalog_text}

BILL ITEMS:
{json.dumps(raw_items, indent=2)}

Return a JSON array where each element has:
- "ingredient_id": one of the valid IDs from the catalog or additional valid ingredients (lowercase_with_underscores)
- "quantity_g": estimated quantity in grams (use 500 as default if not on the bill)
- "original_name": the raw name from the bill

Rules:
- You MUST use only ingredient_ids that exist in the catalog or additional valid ingredients above
- If you cannot match an item to the valid ingredients, skip it
- Combine duplicate items into a single entry with summed quantities
- Return ONLY the JSON array, nothing else"""

    result = invoke_bedrock(prompt=prompt, force_json=True)

    if isinstance(result, list):
        return result

    return []
