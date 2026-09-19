"""Unit tests for ingesting S3 key parsing.

The S3 key encodes the upload type as a filename suffix
(``_bill.jpg`` / ``_fridge.jpg``) so bucket notifications can route bills and
fridge photos to different functions.
"""

import json
import os
from pathlib import Path

# Configure a dummy AWS environment before importing the handler modules, which
# create boto3 clients at import time.
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("TABLE_NAME", "UseItUp-dev")

from src.functions.ingest_bill.app import _parse_bill_key
from src.functions.ingest_fridge_photo.app import _parse_fridge_key

SAMPLE_EVENT = (
    Path(__file__).resolve().parents[1] / "events" / "s3_bill_upload.json"
)


class TestParseBillKey:
    def test_valid_bill_key(self):
        assert _parse_bill_key(
            "uploads/hh-test123/abc123_20250115103000_bill.jpg"
        ) == ("hh-test123", "abc123")

    def test_fridge_photo_is_rejected(self):
        assert _parse_bill_key(
            "uploads/hh-test123/abc123_20250115103000_fridge.jpg"
        ) is None

    def test_plain_jpg_without_tag_is_rejected(self):
        assert _parse_bill_key("uploads/hh-test123/abc123.jpg") is None

    def test_malformed_key_is_rejected(self):
        assert _parse_bill_key("abc123_20250115103000_bill.jpg") is None

    def test_matches_sample_event(self):
        event = json.loads(SAMPLE_EVENT.read_text())
        key = event["Records"][0]["s3"]["object"]["key"]
        assert _parse_bill_key(key) == ("hh-test123", "abc123")


class TestParseFridgeKey:
    def test_valid_fridge_key(self):
        assert _parse_fridge_key(
            "uploads/hh-test123/abc123_20250115103000_fridge.jpg"
        ) == ("hh-test123", "abc123")

    def test_bill_is_rejected(self):
        assert _parse_fridge_key(
            "uploads/hh-test123/abc123_20250115103000_bill.jpg"
        ) is None

    def test_malformed_key_is_rejected(self):
        assert _parse_fridge_key("abc123_20250115103000_fridge.jpg") is None
