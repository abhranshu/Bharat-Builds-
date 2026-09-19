# UseItUp Backend

AI-powered food-waste and nutrition backend for Indian households.

## Architecture

```
User uploads photo → API Gateway → Lambda → S3
                                        ↓
                              Textract / Bedrock Vision
                                        ↓
                              Ingredient normalization (Bedrock)
                                        ↓
                              DynamoDB (single-table design)
                                        ↓
                              Recipe generation (Bedrock) + Nutrition calc (IFCT)
                                        ↓
                              Expiry check (EventBridge) → SNS notifications
```

## Tech Stack

- **Runtime:** Python 3.12
- **IaC:** AWS SAM
- **Compute:** AWS Lambda (one function per endpoint)
- **API:** API Gateway REST API
- **Database:** DynamoDB (single-table design)
- **Storage:** S3 (image uploads)
- **AI:** Amazon Bedrock (Amazon Nova 2 Lite, Converse API) + Amazon Textract
- **Scheduling:** EventBridge Scheduler
- **Notifications:** SNS
- **Validation:** Pydantic
- **Testing:** pytest

## API Endpoints

| Method | Path | Description | Trigger |
|--------|------|-------------|---------|
| `POST` | `/upload-url` | Generate presigned S3 PUT URL | API Gateway |
| `GET` | `/inventory?household_id=xxx` | Get household inventory | API Gateway |
| `POST` | `/cooked` | Mark recipe as cooked, deduct ingredients | API Gateway |
| `POST` | `/recipes/generate` | Generate AI recipes from inventory | API Gateway |
| `GET` | `/nutrition?household_id=xxx` | Daily nutrition summary | API Gateway |
| `PUT` | `/profile` | Update household profile | API Gateway |
| `S3` | `uploads/*/*_bill.jpg` | Process grocery bill (Textract) | S3 trigger |
| `S3` | `uploads/*/*_fridge.jpg` | Process fridge photo (Bedrock Vision) | S3 trigger |
| `EventBridge` | `rate(1 day)` | Daily expiry check + SNS nudge | Schedule |

## DynamoDB Single-Table Design

**Table:** AppData | **PK:** `PK` (string) | **SK:** `SK` (string)

| PK | SK | Data |
|----|-----|------|
| `HH#<household_id>` | `ITEM#<item_id>` | ingredient_id, quantity_g, purchase_date, predicted_expiry, source |
| `HH#<household_id>` | `PROFILE` | diet_type, household_size, language, daily targets |
| `HH#<household_id>` | `COOKED#<iso_timestamp>` | recipe_name, ingredients_used, nutrition_totals |
| `HH#<household_id>` | `UPLOAD#<image_id>` | status, raw_output |
| `CAT#<ingredient_id>` | `META` | canonical_name, aliases, shelf_life_days, IFCT macros |

## Local Development

### Prerequisites

- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) installed
- Docker installed (for `sam local`)
- Python 3.12
- DynamoDB Local (via Docker)

### Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install pytest

# 2. Start DynamoDB Local
docker run -p 8000:8000 amazon/dynamodb-local

# 3. Create local table
aws dynamodb create-table \
  --table-name UseItUp-dev \
  --attribute-definitions \
    AttributeName=PK,AttributeType=S \
    AttributeName=SK,AttributeType=S \
    AttributeName=GSI1PK,AttributeType=S \
    AttributeName=GSI1SK,AttributeType=S \
  --key-schema \
    AttributeName=PK,KeyType=HASH \
    AttributeName=SK,KeyType=RANGE \
  --global-secondary-indexes \
    IndexName=GSI1,KeySchema=[{AttributeName=GSI1PK,KeyType=HASH},{AttributeName=GSI1SK,KeyType=RANGE}],Projection={ProjectionType=ALL} \
  --billing-mode PAY_PER_REQUEST \
  --endpoint-url http://localhost:8000

# 4. Seed the catalog
TABLE_NAME=UseItUp-dev \
DYNAMODB_ENDPOINT_URL=http://localhost:8000 \
AWS_DEFAULT_REGION=us-east-1 \
AWS_ACCESS_KEY_ID=local \
AWS_SECRET_ACCESS_KEY=local \
python scripts/seed_dynamo.py

# 5. Build and start the API
sam build
sam local start-api --warm-containers EAGER

# 6. Test
curl http://127.0.0.1:3000/inventory?household_id=hh-test123
```

### Testing Individual Functions

```bash
# Test get_upload_url
sam local invoke GetUploadUrlFunction \
  --event tests/events/api_get_upload_url.json

# Test ingest_bill
sam local invoke IngestBillFunction \
  --event tests/events/s3_bill_upload.json

# Test get_inventory
sam local invoke GetInventoryFunction \
  --event tests/events/api_get_inventory.json
```

### Running Tests

```bash
# Unit tests (no AWS required)
pytest tests/unit/ -v

# With coverage
pytest tests/unit/ -v --cov=src/shared
```

## Deployment

### First Deploy

```bash
# Build
sam build

# Deploy (guided — walks you through options)
sam deploy --guided

# Or deploy with defaults
sam deploy \
  --stack-name UseItUp-dev \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides EnvironmentName=dev
```

### Subsequent Deploys

```bash
sam build && sam deploy
```

### Seed Catalog in Production

```bash
TABLE_NAME=UseItUp-dev \
AWS_DEFAULT_REGION=us-east-1 \
python scripts/seed_dynamo.py
```

### Get Stack Outputs

```bash
sam list stack-outputs --stack-name UseItUp-dev
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TABLE_NAME` | DynamoDB table name | `UseItUp-dev` |
| `BUCKET_NAME` | S3 upload bucket name | — |
| `SNS_TOPIC_ARN` | SNS topic for expiry notifications | — |
| `BEDROCK_MODEL_ID` | Bedrock model / inference profile ID (Amazon Nova 2 Lite) | `global.amazon.nova-2-lite-v1:0` |

## Error Handling

- All Lambda functions wrap logic in try/except
- 400 for Pydantic validation errors
- 500 for AWS service failures
- Raw exception text never exposed to client
- Bedrock calls retry once on malformed JSON responses
- Textract handles non-receipt images with clear error messages

## Cost Estimate (per month, low traffic)

| Service | Free Tier | Estimate |
|---------|-----------|----------|
| Lambda | 1M requests | ~$0 |
| DynamoDB | 25 GB + 25 RCU/WCU | ~$0 |
| S3 | 5 GB + 20K requests | ~$0 |
| Bedrock | Pay per token | ~$2-10 |
| Textract | 1K pages/month | ~$0 |
| API Gateway | 1M calls | ~$1 |
| SNS | 1M publishes | ~$0 |
| EventBridge | 14M events | ~$0 |
