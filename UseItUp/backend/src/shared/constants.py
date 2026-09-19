"""Environment configuration constants."""

import os

# DynamoDB
TABLE_NAME: str = os.environ.get("TABLE_NAME", "UseItUp-dev")

# S3
BUCKET_NAME: str = os.environ.get("BUCKET_NAME", "useitup-uploads-dev")

# SNS
SNS_TOPIC_ARN: str = os.environ.get("SNS_TOPIC_ARN", "")

# Bedrock
BEDROCK_MODEL_ID: str = os.environ.get(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-sonnet-4-20250514-v1:0",
)
BEDROCK_REGION: str = os.environ.get("AWS_REGION", "us-east-1")

# Textract
TEXTRACT_REGION: str = os.environ.get("AWS_REGION", "us-east-1")

# DynamoDB key prefixes
PK_PREFIX_HOUSEHOLD = "HH#"
PK_PREFIX_CATALOG = "CAT#"
SK_PREFIX_ITEM = "ITEM#"
SK_PREFIX_PROFILE = "PROFILE"
SK_PREFIX_COOKED = "COOKED#"
SK_PREFIX_UPLOAD = "UPLOAD#"
SK_META = "META"

# Upload paths
UPLOAD_PREFIX_BILL = "bill_"
UPLOAD_PREFIX_FRIDGE = "fridge_"

# Defaults
DEFAULT_DAILY_CALORIE_TARGET = 2000
DEFAULT_DAILY_PROTEIN_TARGET = 60  # grams
DEFAULT_HOUSEHOLD_SIZE = 4
DEFAULT_LANGUAGE = "en"
DEFAULT_DIET_TYPE = "vegetarian"
