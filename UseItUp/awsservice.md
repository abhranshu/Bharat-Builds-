# AWS Services Used in UseItUp

UseItUp is a serverless, AI-powered food-waste prevention app built entirely on AWS. Below is a comprehensive list of every AWS service used across the frontend, backend, and infrastructure.

---

## Core Services

| # | AWS Service | Purpose | Details |
|---|-------------|---------|---------|
| 1 | **AWS Lambda** | Serverless compute | 10 Python 3.12 functions (ARM64), one per API endpoint and event trigger |
| 2 | **Amazon API Gateway** | REST API | `UseItUp-api-dev` — serves all HTTP endpoints with CORS enabled |
| 3 | **Amazon DynamoDB** | NoSQL database | Single-table design (`UseItUp-dev`), PAY_PER_REQUEST billing, GSI1, Point-in-Time Recovery |
| 4 | **Amazon S3** | Object storage | Two buckets: frontend static hosting (`useitup-frontend-*`) and image uploads (`useitup-uploads-*`) |
| 5 | **Amazon CloudFront** | CDN / content delivery | Serves the frontend (`E12OPYNPLA8CHN`), Origin Access Control (OAC) to S3 |

---

## AI / Machine Learning

| # | AWS Service | Purpose | Details |
|---|-------------|---------|---------|
| 6 | **Amazon Bedrock** | Generative AI | Amazon Nova 2 Lite (`global.amazon.nova-2-lite-v1:0`) via Converse API — recipe generation, ingredient normalization from bill text, fridge photo vision analysis |
| 7 | **Amazon Textract** | Document OCR | `AnalyzeExpense` API — extracts line items, quantities, and prices from grocery bill images |

---

## Event-Driven / Scheduling

| # | AWS Service | Purpose | Details |
|---|-------------|---------|---------|
| 8 | **Amazon EventBridge** | Scheduled events | Daily cron rule (7:30 AM IST) triggers the expiry-check Lambda |
| 9 | **Amazon SNS** | Notifications | `UseItUp-expiry-nudges-dev` — sends expiry notification messages for food items approaching their end-of-life |

---

## Infrastructure & DevOps

| # | AWS Service | Purpose | Details |
|---|-------------|---------|---------|
| 10 | **AWS SAM (Serverless Application Model)** | Infrastructure as Code | `template.yaml` defines the entire backend stack — Lambda functions, DynamoDB, S3, SNS, EventBridge, API Gateway |
| 11 | **AWS IAM** | Access control | Execution roles for each Lambda function (DynamoDB CRUD, S3 read, Bedrock invoke, Textract analyze, SNS publish) |
| 12 | **AWS CloudFormation** | Stack management | Backend deployed via SAM (which uses CloudFormation under the hood) |

---

## Lambda Functions

| Function | Trigger | AWS Services Used |
|----------|---------|-------------------|
| `GetUploadUrlFunction` | API Gateway (`POST /upload-url`) | S3, DynamoDB |
| `IngestBillFunction` | S3 event (`*_bill.jpg`) | S3, Textract, Bedrock, DynamoDB |
| `IngestFridgePhotoFunction` | S3 event (`*_fridge.jpg`) | S3, Bedrock (Vision), DynamoDB |
| `AddInventoryFunction` | API Gateway (`POST /inventory`) | DynamoDB |
| `GetInventoryFunction` | API Gateway (`GET /inventory`) | DynamoDB |
| `MarkCookedFunction` | API Gateway (`POST /cooked`) | DynamoDB |
| `GenerateRecipesFunction` | API Gateway (`POST /recipes/generate`) | DynamoDB, Bedrock |
| `GetNutritionSummaryFunction` | API Gateway (`GET /nutrition`) | DynamoDB |
| `UpdateProfileFunction` | API Gateway (`PUT /profile`) | DynamoDB |
| `ExpiryCheckCronFunction` | EventBridge (daily cron) | DynamoDB, SNS |

---

## S3 Buckets

| Bucket | Purpose |
|--------|---------|
| `useitup-frontend-574748894960` | Frontend static assets (HTML/CSS/JS) served via CloudFront |
| `useitup-uploads-dev-574748894960` | User-uploaded images (grocery bills, fridge photos) processed by Lambda |

---

## Data Flow Summary

```
Frontend (S3 → CloudFront)
    │
    ├── Upload photo → API Gateway → Lambda (get_upload_url) → presigned S3 URL
    │                                     │
    │                                     ▼
    │                               S3 (upload bucket)
    │                                     │
    │                    ┌────────────────┴────────────────┐
    │                    ▼                                 ▼
    │            S3 trigger: *bill.jpg             S3 trigger: *fridge.jpg
    │                    │                                 │
    │                    ▼                                 ▼
    │              Lambda: ingest_bill             Lambda: ingest_fridge_photo
    │                    │                                 │
    │                    ▼                                 ▼
    │            Textract AnalyzeExpense        Bedrock Vision (Nova 2 Lite)
    │                    │                                 │
    │                    ▼                                 ▼
    │              Bedrock (normalize)            Bedrock (normalize)
    │                    │                                 │
    │                    └────────────────┬────────────────┘
    │                                     ▼
    │                               DynamoDB
    │
    ├── GET /inventory ──────────→ Lambda → DynamoDB
    ├── POST /recipes/generate ──→ Lambda → Bedrock + DynamoDB
    ├── POST /cooked ────────────→ Lambda → DynamoDB
    ├── GET /nutrition ──────────→ Lambda → DynamoDB
    ├── PUT /profile ────────────→ Lambda → DynamoDB
    └── POST /inventory ─────────→ Lambda → DynamoDB

EventBridge (daily cron) → Lambda: expiry_check_cron → DynamoDB → SNS (notifications)
```

---

## Total AWS Services: 12

1. AWS Lambda
2. Amazon API Gateway
3. Amazon DynamoDB
4. Amazon S3
5. Amazon CloudFront
6. Amazon Bedrock
7. Amazon Textract
8. Amazon EventBridge
9. Amazon SNS
10. AWS SAM
11. AWS IAM
12. AWS CloudFormation (via SAM)
