"""Environment configuration constants."""

import os

# DynamoDB
TABLE_NAME: str = os.environ.get("TABLE_NAME", "UseItUp-dev")

# S3
BUCKET_NAME: str = os.environ.get("BUCKET_NAME", "useitup-uploads-dev")

# SNS
SNS_TOPIC_ARN: str = os.environ.get("SNS_TOPIC_ARN", "")

# Bedrock
# Global cross-region inference profile for Amazon Nova 2 Lite, invoked via the
# Bedrock Runtime Converse API. A global profile is region-agnostic, so it
# resolves from any deployment region (including ap-south-1). Always supplied
# through the BEDROCK_MODEL_ID Lambda environment variable.
BEDROCK_MODEL_ID: str = os.environ.get(
    "BEDROCK_MODEL_ID",
    "global.amazon.nova-2-lite-v1:0",
)
BEDROCK_REGION: str = os.environ.get("AWS_REGION", "ap-south-1")

# Textract
TEXTRACT_REGION: str = os.environ.get("AWS_REGION", "ap-south-1")

# DynamoDB key prefixes
PK_PREFIX_HOUSEHOLD = "HH#"
PK_PREFIX_CATALOG = "CAT#"
SK_PREFIX_ITEM = "ITEM#"
SK_PREFIX_PROFILE = "PROFILE"
SK_PREFIX_COOKED = "COOKED#"
SK_PREFIX_UPLOAD = "UPLOAD#"
SK_META = "META"

# Upload paths
# The upload type is encoded as a filename *suffix* so S3 event notifications
# can filter on it (S3 supports prefix/suffix rules only, not mid-key globs):
#   uploads/{household_id}/{image_id}_{timestamp}_bill.jpg
#   uploads/{household_id}/{image_id}_{timestamp}_fridge.jpg
UPLOAD_TAG_BILL = "bill"
UPLOAD_TAG_FRIDGE = "fridge"
UPLOAD_SUFFIX_BILL = "_bill.jpg"
UPLOAD_SUFFIX_FRIDGE = "_fridge.jpg"

# Defaults
DEFAULT_DAILY_CALORIE_TARGET = 2000
DEFAULT_DAILY_PROTEIN_TARGET = 60  # grams
DEFAULT_HOUSEHOLD_SIZE = 4
DEFAULT_LANGUAGE = "en"
DEFAULT_DIET_TYPE = "vegetarian"
