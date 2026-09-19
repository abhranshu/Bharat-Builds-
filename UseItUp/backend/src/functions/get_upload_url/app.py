"""Generates a presigned S3 PUT URL for image upload."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta

import boto3

from src.shared.constants import BUCKET_NAME, SK_PREFIX_UPLOAD, PK_PREFIX_HOUSEHOLD
from src.shared.dynamo_client import put_item
from src.shared.models import GetUploadUrlRequest, GetUploadUrlResponse

logger = logging.getLogger(__name__)

_s3 = boto3.client("s3")


def handler(event, context):
    """Lambda handler for GET /upload-url."""
    try:
        body = json.loads(event.get("body", "{}"))
        request = GetUploadUrlRequest(**body)

        # Generate unique image ID
        image_id = str(uuid.uuid4())[:12]
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        # Build S3 key
        if request.upload_type.value == "bill":
            prefix = "bill_"
        else:
            prefix = "fridge_"

        s3_key = f"uploads/{request.household_id}/{prefix}{image_id}_{timestamp}.jpg"

        # Generate presigned PUT URL (1 hour TTL)
        presigned_url = _s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": s3_key,
                "ContentType": "image/jpeg",
            },
            ExpiresIn=3600,
        )

        # Write UPLOAD# record to DynamoDB
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
            "headers": {"Content-Type": "application/json"},
            "body": response.model_dump_json(),
        }

    except Exception as exc:
        logger.error("Error generating upload URL: %s", exc)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Internal server error",
                "detail": str(exc),
                "status_code": 500,
            }),
        }
