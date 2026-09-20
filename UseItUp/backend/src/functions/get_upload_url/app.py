"""Generates a presigned S3 PUT URL for image upload."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta

import boto3
from pydantic import ValidationError

from src.shared.constants import (
    BUCKET_NAME,
    SK_PREFIX_UPLOAD,
    PK_PREFIX_HOUSEHOLD,
    UPLOAD_TAG_BILL,
    UPLOAD_TAG_FRIDGE,
)
from src.shared.dynamo_client import put_item
from src.shared.models import GetUploadUrlRequest, GetUploadUrlResponse


logger = logging.getLogger(__name__)

_s3 = boto3.client("s3")


def handler(event, context):
    """Lambda handler for POST /upload-url."""

    try:
        # API Gateway normally provides the request body as a JSON string.
        # Some direct Lambda invocations/tests may provide it as a dict.
        raw_body = event.get("body")

        if raw_body is None:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "error": "Request body is required"
                }),
            }

        # Handle both API Gateway string bodies and direct Lambda dict bodies.
        if isinstance(raw_body, dict):
            body = raw_body
        else:
            body = json.loads(raw_body)

        if not isinstance(body, dict):
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "error": "Request body must be a JSON object"
                }),
            }

        # Validate request using Pydantic model.
        request = GetUploadUrlRequest(**body)

        # Generate unique image ID.
        image_id = str(uuid.uuid4())[:12]
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        # Build S3 key.
        # The upload type goes in the filename suffix so the S3
        # ObjectCreated notifications can filter on it.
        if request.upload_type.value == "bill":
            tag = UPLOAD_TAG_BILL
        else:
            tag = UPLOAD_TAG_FRIDGE

        s3_key = (
            f"uploads/{request.household_id}/"
            f"{image_id}_{timestamp}_{tag}.jpg"
        )

        # Generate presigned PUT URL (1 hour TTL).
        presigned_url = _s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": s3_key,
                "ContentType": "image/jpeg",
            },
            ExpiresIn=3600,
        )

        # Write UPLOAD# record to DynamoDB.
        pk = f"{PK_PREFIX_HOUSEHOLD}{request.household_id}"
        sk = f"{SK_PREFIX_UPLOAD}{image_id}"

        put_item(
            pk=pk,
            sk=sk,
            data={
                "image_id": image_id,
                "status": "pending",
                "upload_type": request.upload_type.value,
                "household_id": request.household_id,
                "s3_key": s3_key,
            },
        )

        logger.info(
            "Generated upload URL for household=%s type=%s image=%s",
            request.household_id,
            request.upload_type.value,
            image_id,
        )

        response = GetUploadUrlResponse(
            upload_url=presigned_url,
            image_id=image_id,
            expires_in=3600,
        )

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": response.model_dump_json(),
        }

    except json.JSONDecodeError as exc:
        logger.warning("Invalid JSON request body: %s", exc)

        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "error": "Invalid JSON request body",
                "detail": str(exc),
                "status_code": 400,
            }),
        }

    except ValidationError as exc:
        logger.warning("Validation error: %s", exc)
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "error": "Validation error",
                "detail": str(exc),
                "status_code": 400,
            }),
        }

    except Exception as exc:
        logger.exception(
            "Error generating upload URL: %s",
            exc
        )

        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "error": "Internal server error",
                "detail": str(exc),
                "status_code": 500,
            }),
        }