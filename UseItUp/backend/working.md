# UseItUp Backend — Complete Working Documentation

This document explains **exactly how every part of the backend works**,
from the moment a user uploads a photo to the moment they get a recipe.
Read this to understand the full system before modifying any code.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Infrastructure](#2-infrastructure)
3. [Data Model](#3-data-model)
4. [API Endpoints — Request/Response Flow](#4-api-endpoints)
5. [Lambda Functions — Internal Logic](#5-lambda-functions)
6. [Shared Modules](#6-shared-modules)
7. [AI Integration (Bedrock + Textract)](#7-ai-integration)
8. [Scheduled Jobs](#8-scheduled-jobs)
9. [Error Handling](#9-error-handling)
10. [Local Development](#10-local-development)
11. [Deployment](#11-deployment)

---

## 1. System Overview

### What the backend does

The UseItUp backend is a serverless API that:

1. Accepts photos of grocery bills or fridge contents
2. Uses AI to extract ingredients from those photos
3. Stores ingredients in a database with predicted expiry dates
4. Generates recipes constrained to what the user has
5. Computes nutrition per serving from IFCT data
6. Tracks daily nutrition against targets
7. Sends daily notifications when items are about to expire

### Request flow (happy path)

```
User                    API Gateway              Lambda                   AWS Services
  │                          │                      │                         │
  │── POST /upload-url ──────▶│── get_upload_url ────▶│── S3 presigned URL     │
  │◀── {upload_url, img_id} ──│◀─────────────────────│◀── put_item to DynamoDB │
  │                          │                      │                         │
  │── PUT upload_url ──────────────────────────────────────────────────────────▶ S3
  │                          │                      │                         │
  │                    [S3 ObjectCreated event]      │                         │
  │                          │── ingest_bill ────────▶│── Textract AnalyzeExpense
  │                          │   OR                  │── Bedrock normalize     │
  │                          │── ingest_fridge_photo ▶│── expiry_predictor     │
  │                          │                      │── put_item × N          │
  │                          │                      │                         │
  │── POST /recipes/generate ▶│── generate_recipes ──▶│── query inventory      │
  │                          │                      │── query profile         │
  │                          │                      │── Bedrock generate      │
  │                          │                      │── nutrition_calculator  │
  │◀── {recipes} ────────────│◀─────────────────────│◀────────────────────────│
  │                          │                      │                         │
  │── POST /cooked ──────────▶│── mark_cooked ───────▶│── decrement quantities │
  │                          │                      │── write COOKED# record  │
  │◀── {inventory, nutrition}│◀─────────────────────│◀────────────────────────│
```

---

## 2. Infrastructure

All infrastructure is defined in `template.yaml` (AWS SAM).

### Resources created

| Resource | Type | Purpose |
|----------|------|---------|
| `AppDataTable` | DynamoDB | Single-table for all data |
| `UploadBucket` | S3 | Image storage (bills + fridge photos) |
| `ExpiryNotificationsTopic` | SNS | Daily expiry nudge messages |
| `CommonDepsLayer` | Lambda Layer | Shared Python packages |
| `ApiGateway` | API Gateway | HTTP routing for 6 endpoints |
| `GetUploadUrlFunction` | Lambda | Generates presigned S3 URLs |
| `IngestBillFunction` | Lambda | Processes bills via Textract |
| `IngestFridgePhotoFunction` | Lambda | Processes fridge photos via Bedrock |
| `GetInventoryFunction` | Lambda | Returns household inventory |
| `MarkCookedFunction` | Lambda | Deducts ingredients, logs meal |
| `GenerateRecipesFunction` | Lambda | AI recipe generation |
| `GetNutritionSummaryFunction` | Lambda | Daily nutrition totals |
| `UpdateProfileFunction` | Lambda | Updates household settings |
| `ExpiryCheckCronFunction` | Lambda | Daily expiry scan + SNS |
| `ExpiryCheckScheduleRule` | EventBridge Rule | Triggers cron at 7 AM IST |

### Environment variables (injected into all Lambdas)

```
TABLE_NAME       → UseItUp-dev
BUCKET_NAME      → useitup-uploads-dev-ACCOUNT_ID
SNS_TOPIC_ARN    → arn:aws:sns:us-east-1:ACCOUNT:UseItUp-expiry-nudges-dev
BEDROCK_MODEL_ID → anthropic.claude-sonnet-4-20250514-v1:0
AWS_REGION       → us-east-1
```

### IAM permissions per function

| Function | S3 | DynamoDB | Textract | Bedrock | SNS |
|----------|-----|----------|----------|---------|-----|
| get_upload_url | CRUD | CRUD | — | — | — |
| ingest_bill | Read | CRUD | AnalyzeExpense | InvokeModel | — |
| ingest_fridge_photo | Read | CRUD | — | InvokeModel | — |
| get_inventory | — | Read | — | — | — |
| mark_cooked | — | CRUD | — | — | — |
| generate_recipes | — | Read | — | InvokeModel | — |
| get_nutrition_summary | — | Read | — | — | — |
| update_profile | — | CRUD | — | — | — |
| expiry_check_cron | — | Read | — | — | Publish |

---

## 3. Data Model

### DynamoDB single-table design

**Table name:** `UseItUp-dev`

**Key schema:**
- Partition key (PK): String
- Sort key (SK): String

**GSI1:**
- GSI1PK: String
- GSI1SK: String

### Entity map

Every row in DynamoDB has a `PK` and `SK`. The prefix tells you what entity it is:

```
PK                          SK                     What it stores
─────────────────────────────────────────────────────────────────────
HH#<household_id>          ITEM#<item_id>         An ingredient in the fridge
HH#<household_id>          PROFILE                 User preferences
HH#<household_id>          COOKED#<timestamp>     A meal that was cooked
HH#<household_id>          UPLOAD#<image_id>      Upload tracking record
CAT#<ingredient_id>        META                   Catalog entry (canonical data)
```

### ITEM# record (ingredient in fridge)

```json
{
  "PK": "HH#abc123",
  "SK": "ITEM#tomato_xyz789",
  "GSI1PK": "CAT#tomato",
  "GSI1SK": "abc123",
  "ingredient_id": "tomato",
  "quantity_g": 450.0,
  "purchase_date": "2025-01-15",
  "predicted_expiry": "2025-01-22",
  "source": "bill",
  "expiry_confidence": "high"
}
```

**Key fields:**
- `ingredient_id`: Matches the catalog entry (e.g., "tomato", "paneer")
- `quantity_g`: How many grams the user has
- `predicted_expiry`: Computed by `expiry_predictor.py`
- `source`: "bill" (high confidence) or "fridge_photo" (estimated)
- `GSI1PK/GSI1SK`: Allow querying all items for an ingredient across households

### PROFILE record

```json
{
  "PK": "HH#abc123",
  "SK": "PROFILE",
  "diet_type": "vegetarian",
  "household_size": 4,
  "language": "en",
  "daily_calorie_target": 2000.0,
  "daily_protein_target": 60.0
}
```

### COOKED# record

```json
{
  "PK": "HH#abc123",
  "SK": "COOKED#2025-01-15T12:30:00",
  "recipe_name": "Tomato Paneer",
  "ingredients_used": [
    {"ingredient_id": "tomato", "name": "Tomato", "grams": 200},
    {"ingredient_id": "paneer", "name": "Paneer", "grams": 150}
  ],
  "nutrition_totals": {
    "calories": 420.0,
    "protein": 28.5,
    "carbs": 12.0,
    "fat": 30.0,
    "fiber": 3.0
  },
  "servings_cooked": 2
}
```

### UPLOAD# record

```json
{
  "PK": "HH#abc123",
  "SK": "UPLOAD#img_xyz789",
  "image_id": "img_xyz789",
  "status": "processed",
  "upload_type": "bill",
  "household_id": "abc123",
  "s3_key": "uploads/abc123/bill_img_xyz789_20250115103000.jpg",
  "item_count": 8,
  "processed_at": "2025-01-15T10:31:00",
  "raw_output": { ... }
}
```

### CAT# record (catalog entry)

```json
{
  "PK": "CAT#tomato",
  "SK": "META",
  "GSI1PK": "CAT#tomato",
  "GSI1SK": "tomato",
  "ingredient_id": "tomato",
  "canonical_name": "Tomato",
  "aliases": ["tomatoes", "tamatar", "red tomato"],
  "shelf_life_days": 7,
  "category": "vegetable",
  "ifct_macros_per_100g": {
    "calories": 20,
    "protein": 0.9,
    "carbs": 3.9,
    "fat": 0.2,
    "fiber": 1.2
  }
}
```

### How the key scheme works

**Querying all ingredients for a household:**
```
PK = HH#abc123
SK begins_with ITEM#
→ Returns all ingredients for this household
```

**Querying today's cooked meals:**
```
PK = HH#abc123
SK begins_with COOKED#2025-01-15
→ Returns all meals cooked today
```

**Querying all catalog entries:**
```
GSI1PK begins_with CAT#
→ Returns all catalog items (independent of household)
```

**Deleting an ingredient when quantity hits zero:**
```
DeleteItem(PK=HH#abc123, SK=ITEM#tomato_xyz789)
```

---

## 4. API Endpoints

### POST /upload-url

**Purpose:** Generate a presigned S3 URL for uploading an image.

**Request:**
```json
{
  "household_id": "abc123",
  "upload_type": "bill"
}
```

`upload_type` must be `"bill"` or `"fridge_photo"`.

**What happens:**
1. Validates input with Pydantic (`GetUploadUrlRequest`)
2. Generates a unique `image_id` (UUID, 12 chars)
3. Builds S3 key: `uploads/{household_id}/{prefix}{image_id}_{timestamp}.jpg`
4. Generates presigned PUT URL (1 hour TTL)
5. Writes `UPLOAD#` record to DynamoDB with `status: "pending"`
6. Returns `{upload_url, image_id, expires_in}`

**Response:**
```json
{
  "upload_url": "https://useitup-uploads-dev-xxx.s3.amazonaws.com/uploads/abc123/bill_img123_20250115103000.jpg?X-Amz-...",
  "image_id": "img123",
  "expires_in": 3600
}
```

**The client then does a direct HTTP PUT to `upload_url` with the image bytes.**

---

### GET /inventory?household_id=xxx

**Purpose:** Return all ingredients currently in the household's fridge.

**Request:** Query parameter `household_id` (required).

**What happens:**
1. Queries DynamoDB: `PK = HH#{household_id}`, `SK begins_with ITEM#`
2. For each item, computes `days_until_expiry` and `expiry_status`
3. Sorts by predicted expiry (soonest first)
4. Returns the full ingredient list

**Response:**
```json
{
  "household_id": "abc123",
  "items": [
    {
      "ingredient_id": "coriander",
      "name": "Coriander",
      "quantity_g": 30.0,
      "purchase_date": "2025-01-15",
      "predicted_expiry": "2025-01-20",
      "source": "fridge_photo",
      "expiry_confidence": "estimated"
    },
    {
      "ingredient_id": "tomato",
      "name": "Tomato",
      "quantity_g": 450.0,
      "purchase_date": "2025-01-15",
      "predicted_expiry": "2025-01-22",
      "source": "bill",
      "expiry_confidence": "high"
    }
  ],
  "count": 2
}
```

---

### POST /recipes/generate

**Purpose:** Generate AI recipes constrained to the user's inventory.

**Request:**
```json
{
  "household_id": "abc123",
  "meal_type": "lunch",
  "prep_time_preference": 30
}
```

`meal_type`: `"breakfast"`, `"lunch"`, `"dinner"`, `"snack"`
`prep_time_preference`: 5–120 minutes

**What happens (step by step):**

1. **Query inventory** — gets all `ITEM#` records, sorted by expiry (soonest first)
2. **Query profile** — gets `PROFILE` record for diet type and nutrition targets
3. **Query today's meals** — gets all `COOKED#2025-01-15*` records
4. **Compute nutrition gap** — `remaining = targets - consumed`
5. **Build Bedrock prompt** — includes:
   - Available ingredients with quantities and days until expiry
   - Diet type constraint
   - Prep time limit
   - Remaining nutrition gap
   - Instruction to prioritize soonest-expiring items
6. **Invoke Bedrock** — Claude generates 2-3 recipes as structured JSON
7. **Parse response** — validates JSON, extracts recipe objects
8. **Calculate nutrition deterministically** — for each recipe, uses `nutrition_calculator.py` with IFCT data (NOT the LLM's output)
9. **Generate "why this" reasons** — templated strings like "Uses your coriander expiring in 2 days"
10. **Return recipes** with per-serving nutrition

**Response:**
```json
{
  "household_id": "abc123",
  "recipes": [
    {
      "name": "Tomato Paneer Stir Fry",
      "ingredients": [
        {"ingredient_id": "tomato", "name": "Tomato", "grams": 200},
        {"ingredient_id": "paneer", "name": "Paneer", "grams": 150},
        {"ingredient_id": "oil", "name": "Cooking Oil", "grams": 15}
      ],
      "steps": [
        "Cut tomatoes into wedges and paneer into cubes.",
        "Heat oil in a pan over medium heat.",
        "Add tomatoes and cook for 3 minutes.",
        "Add paneer and cook for 5 minutes.",
        "Season with salt and serve."
      ],
      "prep_time_minutes": 15,
      "servings": 2,
      "nutrition_per_serving": {
        "calories": 245.0,
        "protein": 18.5,
        "carbs": 8.0,
        "fat": 16.0,
        "fiber": 2.0
      },
      "reason": "Uses your Tomato expiring in 7 days. Uses 215g from your fridge."
    }
  ],
  "nutrition_gap": {
    "calories": 1510.0,
    "protein": 23.0,
    "carbs": 0.0,
    "fat": 0.0,
    "fiber": 0.0
  }
}
```

---

### POST /cooked

**Purpose:** Mark a recipe as cooked — deducts ingredients and logs the meal.

**Request:**
```json
{
  "household_id": "abc123",
  "recipe": {
    "name": "Tomato Paneer Stir Fry",
    "ingredients": [
      {"ingredient_id": "tomato", "name": "Tomato", "grams": 200},
      {"ingredient_id": "paneer", "name": "Paneer", "grams": 150}
    ],
    "steps": [],
    "prep_time_minutes": 15,
    "servings": 2
  },
  "servings_cooked": 2
}
```

**What happens:**

1. For each ingredient in the recipe:
   - Find the matching `ITEM#` record in DynamoDB
   - Calculate `used_qty = ingredient.grams × servings_cooked`
   - Subtract from `quantity_g`
   - If quantity hits 0 → **delete the record**
   - If quantity > 0 → **update the record**
2. Compute nutrition totals using `nutrition_calculator.py`
3. Write a `COOKED#` record with timestamp, recipe name, ingredients used, and nutrition
4. Query today's `COOKED#` records to compute updated daily totals
5. Return updated inventory and daily nutrition

**Response:**
```json
{
  "message": "Marked 'Tomato Paneer Stir Fry' as cooked for 2 servings",
  "updated_inventory": [],
  "daily_nutrition": {
    "calories": 420.0,
    "protein": 28.5,
    "carbs": 12.0,
    "fat": 30.0,
    "fiber": 3.0
  }
}
```

---

### GET /nutrition?household_id=xxx

**Purpose:** Return daily nutrition summary — consumed vs targets.

**What happens:**
1. Query profile for daily targets (default: 2000 kcal, 60g protein)
2. Query today's `COOKED#` records
3. Sum all `nutrition_totals` from today's meals
4. Compute `remaining = targets - consumed`
5. Return consumed, targets, and remaining

**Response:**
```json
{
  "household_id": "abc123",
  "date": "2025-01-15",
  "consumed": {
    "calories": 420.0,
    "protein": 28.5,
    "carbs": 12.0,
    "fat": 30.0,
    "fiber": 3.0
  },
  "targets": {
    "calories": 2000.0,
    "protein": 60.0,
    "carbs": 300.0,
    "fat": 65.0,
    "fiber": 25.0
  },
  "remaining": {
    "calories": 1580.0,
    "protein": 31.5,
    "carbs": 288.0,
    "fat": 35.0,
    "fiber": 22.0
  }
}
```

---

### PUT /profile

**Purpose:** Update household profile settings.

**Request:**
```json
{
  "household_id": "abc123",
  "diet_type": "vegan",
  "household_size": 3,
  "daily_calorie_target": 1800,
  "daily_protein_target": 50
}
```

All fields except `household_id` are optional — only provided fields are updated.

**What happens:**
1. Validate input with Pydantic
2. Fetch existing profile (or use defaults)
3. Merge provided fields into existing profile
4. Write merged profile to DynamoDB
5. Return updated profile

**Response:**
```json
{
  "message": "Profile updated successfully",
  "profile": {
    "diet_type": "vegan",
    "household_size": 3,
    "language": "en",
    "daily_calorie_target": 1800.0,
    "daily_protein_target": 50.0
  }
}
```

---

## 5. Lambda Functions — Internal Logic

### get_upload_url (`src/functions/get_upload_url/app.py`)

```
Input → Validate with Pydantic → Generate UUID → Build S3 key
→ Generate presigned URL → Write UPLOAD# to DynamoDB → Return URL
```

**Key details:**
- S3 key pattern: `uploads/{household_id}/{bill_|fridge_}{uuid}_{timestamp}.jpg`
- Presigned URL TTL: 1 hour (3600 seconds)
- The UPLOAD# record starts as `status: "pending"` and is updated to `"processed"` by the ingest functions

---

### ingest_bill (`src/functions/ingest_bill/app.py`)

**Trigger:** S3 ObjectCreated event on `uploads/*/bill_*.jpg`

```
S3 event → Download image → Textract AnalyzeExpense
→ Extract line items (name, quantity, price, date)
→ Bedrock prompt: map raw items → canonical ingredient_ids
→ For each item: expiry_predictor(purchase_date, shelf_life)
→ Write ITEM# records to DynamoDB
→ Update UPLOAD# status to "processed"
```

**Texextract output:**
- Vendor name
- Transaction date
- Line items: {name, quantity, price, unit_price}

**Bedrock normalization prompt:**
The prompt includes the full catalog of valid `ingredient_id`s. Claude maps raw bill strings like "TOMATO 500G" to `{"ingredient_id": "tomato", "quantity_g": 500}`. It can only use IDs from the catalog — it cannot invent new ones.

**Expiry prediction:**
- Purchase date comes from Textract's transaction date
- Shelf life comes from the catalog (e.g., tomato = 7 days)
- `predicted_expiry = purchase_date + shelf_life_days`
- Confidence: `"high"` (bill-derived)

---

### ingest_fridge_photo (`src/functions/ingest_fridge_photo/app.py`)

**Trigger:** S3 ObjectCreated event on `uploads/*/fridge_*.jpg`

```
S3 event → Download image → Bedrock Vision (image + prompt)
→ Identify ingredients + estimate quantities
→ Map to catalog ingredient_ids
→ expiry_predictor(photo_date, shelf_life × 0.7)
→ Write ITEM# records to DynamoDB
→ Update UPLOAD# status to "processed"
```

**Key difference from bill processing:**
- No Textract (fridge photos aren't receipts)
- Bedrock Vision sees the image directly
- No purchase date available → uses today's date as fallback
- Shelf life is discounted to 70% (conservative estimate)
- Confidence: `"estimated"`

**Bedrock Vision prompt:**
```
Analyze this fridge photo and identify all visible food ingredients.
For each ingredient, return:
- "ingredient_id": MUST be from the catalog
- "estimated_quantity_g": best guess in grams

CATALOG: [list of valid IDs]
Rules:
- Only include items you can ACTUALLY SEE
- You MUST use catalog IDs only
- Estimate realistically (full tomato ≈ 150g)
```

---

### generate_recipes (`src/functions/generate_recipes/app.py`)

**The most complex function.** Combines inventory, profile, nutrition gap, and AI generation.

```
1. Query ITEM# records → sort by expiry (soonest first)
2. Query PROFILE → diet type, nutrition targets
3. Query COOKED# (today) → compute consumed nutrition
4. Build prompt: ingredients + constraints + gap
5. Invoke Bedrock → structured JSON recipes
6. For each recipe:
   a. Parse ingredients list
   b. nutrition_calculator (deterministic, IFCT data)
   c. Generate "why this" reason
7. Return recipes with nutrition_per_serving
```

**The prompt sent to Claude:**
```
Generate 2-3 recipes for a vegetarian lunch.

AVAILABLE INGREDIENTS (sorted by expiry):
- Tomato (tomato): 450g, expires in 7 days
- Paneer (paneer): 200g, expires in 3 days
- Oil (oil): 500ml, expires in 365 days

CONSTRAINTS:
- Diet type: vegetarian
- Maximum prep time: 30 minutes
- Servings: 2
- Remaining daily calories: 1580 kcal
- Remaining daily protein: 31.5g
- Prioritize ingredients that expire soonest

Return a JSON array of recipes. Each recipe must have:
- "name": recipe name
- "ingredients": array of {ingredient_id, grams}
- "steps": cooking instructions
- "prep_time_minutes": estimated time
- "servings": number of servings

Return ONLY the JSON array.
```

**Why nutrition is calculated separately:**
The prompt asks Claude to list ingredients with quantities. Then `nutrition_calculator.py` computes macros from IFCT data. This separation ensures:
- Nutrition is deterministic (same inputs → same output)
- No LLM hallucination on calorie counts
- IFCT data is authoritative for Indian ingredients

---

### mark_cooked (`src/functions/mark_cooked/app.py`)

```
1. For each ingredient in recipe:
   a. Find matching ITEM# record
   b. Calculate used_qty = grams × servings_cooked
   c. new_qty = current_qty - used_qty
   d. If new_qty ≤ 0 → delete_item
   e. If new_qty > 0 → update_item(quantity_g: new_qty)
2. Compute nutrition_totals via nutrition_calculator
3. Write COOKED# record with timestamp
4. Query today's COOKED# records → sum nutrition
5. Return updated inventory + daily nutrition
```

**Important behavior:**
- Ingredients are deducted per-serving, not per-recipe
- If you cook 2 servings of a recipe that uses 200g tomato per serving, 400g is deducted
- When quantity hits exactly 0, the record is deleted (not kept with 0g)

---

### get_inventory (`src/functions/get_inventory/app.py`)

```
1. Query PK=HH#{id}, SK begins_with ITEM#
2. For each item:
   a. Get canonical name from catalog
   b. Compute days_until_expiry
   c. Compute expiry_status (expired/urgent/warning/fresh)
3. Sort by predicted_expiry ascending
4. Return list
```

---

### get_nutrition_summary (`src/functions/get_nutrition_summary/app.py`)

```
1. Query PROFILE for daily targets (or use defaults)
2. Query COOKED# records for today (SK begins_with COOKED#YYYY-MM-DD)
3. Sum nutrition_totals from all today's meals
4. Compute remaining = targets - consumed
5. Return consumed, targets, remaining
```

---

### update_profile (`src/functions/update_profile/app.py`)

```
1. Validate input (only non-None fields)
2. Fetch existing profile (or use defaults)
3. Merge: existing values + new values
4. Write merged profile to DynamoDB
5. Return updated profile
```

**Defaults (when no profile exists):**
- diet_type: `"vegetarian"`
- household_size: `4`
- language: `"en"`
- daily_calorie_target: `2000`
- daily_protein_target: `60`

---

### expiry_check_cron (`src/functions/expiry_check_cron/app.py`)

**Trigger:** EventBridge Schedule (daily at 7 AM IST)

```
1. Scan ALL items in DynamoDB
2. Filter: predicted_expiry within next 0-2 days
3. Group expiring items by household
4. For each household:
   a. Build notification message
   b. Publish to SNS topic
5. Return count of households notified
```

**Notification message format:**
```
UseItUp — Expiry Alert for Household abc123...

The following items in your fridge are expiring soon:

  • Coriander (30g) — 1 day
  • Paneer (200g) — 0 days

Don't let them go to waste!
Open UseItUp to get recipe ideas using these ingredients.
```

**SNS message attributes:**
- `household_id`: String — allows downstream filtering (e.g., Lambda → push notification)

---

## 6. Shared Modules

### `models.py` — Pydantic Data Models

| Model | Purpose |
|-------|---------|
| `UploadType` | Enum: `bill`, `fridge_photo` |
| `UploadStatus` | Enum: `pending`, `processed`, `failed` |
| `DietType` | Enum: `vegetarian`, `vegan`, `non_vegetarian`, `eggetarian`, `jain` |
| `MealType` | Enum: `breakfast`, `lunch`, `dinner`, `snack` |
| `Ingredient` | Single ingredient in inventory |
| `CatalogItem` | Catalog entry with IFCT macros |
| `MacrosPer100g` | Nutrition per 100g |
| `NutritionInfo` | Aggregated nutrition (calories, protein, carbs, fat, fiber) |
| `RecipeIngredient` | Ingredient used in a recipe |
| `Recipe` | Full recipe with steps, nutrition, reason |
| `HouseholdProfile` | Diet type, targets, language |
| `CookedRecord` | Log of a cooked meal |
| `UploadRecord` | Upload tracking |
| `GetUploadUrlRequest/Response` | API models |
| `GetInventoryResponse` | API model |
| `MarkCookedRequest/Response` | API models |
| `GenerateRecipesRequest/Response` | API models |
| `GetNutritionSummaryResponse` | API model |
| `UpdateProfileRequest/Response` | API models |
| `ErrorResponse` | Standard error format |

All API inputs are validated through Pydantic before any logic runs. Invalid requests return 400 with a descriptive error.

---

### `dynamo_client.py` — DynamoDB Operations

Wraps boto3 DynamoDB calls with serialization helpers.

| Function | What it does |
|----------|-------------|
| `put_item(pk, sk, data)` | Write an item (auto-serializes dates, floats) |
| `get_item(pk, sk)` | Read a single item |
| `query_items(pk, sk_prefix)` | Query all items under a PK with SK prefix |
| `query_gsi1(gsi1pk)` | Query GSI1 (for catalog lookups) |
| `update_item(pk, sk, updates)` | Update specific attributes (not full replace) |
| `delete_item(pk, sk)` | Delete an item |
| `scan(filter_expression)` | Full table scan (used by expiry_check_cron) |

**Serialization:**
- Python `date` → DynamoDB string `"2025-01-15"`
- Python `float` → DynamoDB `Decimal("3.14")`
- `None` values are stripped before write
- On read, `Decimal` → Python `float`/`int`

---

### `bedrock_client.py` — AI Model Invocations

| Function | Purpose |
|----------|---------|
| `invoke_claude(prompt)` | Basic text completion |
| `invoke_claude_json(prompt)` | Text completion with strict JSON parsing + retry |
| `invoke_claude_vision(image_bytes)` | Image + text input (for fridge photos) |

**JSON parsing retry logic:**
1. Send prompt with "respond with valid JSON only" system prompt
2. Parse response → strip markdown fences if present
3. If JSON parse fails → retry once with stricter prompt reminder
4. If still fails → raise ValueError (caught by Lambda handler → 500)

---

### `textract_client.py` — Receipt Parsing

| Class/Function | Purpose |
|----------------|---------|
| `analyze_expense(image_bytes)` | Call Textract AnalyzeExpense API |
| `TextractExpenseItem` | Parsed line item (name, quantity, price) |
| `TextractExpenseResult` | Full result (vendor, date, total, items) |

**Textract extracts:**
- Vendor name (from summary fields)
- Transaction date (from summary fields)
- Total amount (from summary fields)
- Line items: name, quantity, price, unit price (from line item groups)

**Error handling:**
- No documents detected → ValueError ("not a receipt")
- No line items found → ValueError ("could not extract items")

---

### `ingredient_catalog.py` — Ingredient Data

**Two sources:**
1. **Static catalog** (`STATIC_CATALOG`): 20 Indian ingredients with IFCT macros, hardcoded as Python dicts
2. **DynamoDB catalog**: Same data loaded into DynamoDB via `seed_dynamo.py`

**Lookup functions:**
| Function | Purpose |
|----------|---------|
| `get_shelf_life(ingredient_id)` | Days until expiry (default: 7) |
| `get_macros_per_100g(ingredient_id)` | IFCT nutrition data |
| `get_canonical_name(ingredient_id)` | Human-readable name |
| `get_all_aliases()` | Map alias → ingredient_id |
| `search_by_name(name)` | Find ID by name or alias |
| `get_catalog_for_prompt()` | Compact text for Bedrock prompts |

**Catalog is loaded into Lambda memory at cold start** and cached. It's small (~20 items) and read-heavy, so this is more efficient than querying DynamoDB on every request.

---

### `expiry_predictor.py` — Expiry Date Logic

```
predict_expiry(ingredient_id, purchase_date, source):
    shelf_life = catalog[ingredient_id].shelf_life_days
    
    if source == "fridge_photo":
        shelf_life = shelf_life × 0.7  # conservative estimate
        confidence = "estimated"
    else:
        confidence = "high"
    
    predicted_expiry = purchase_date + shelf_life
    return predicted_expiry, confidence
```

**Status labels:**
- `expired`: days_until_expiry < 0
- `urgent`: days_until_expiry = 0-1
- `warning`: days_until_expiry = 2-3
- `fresh`: days_until_expiry > 3

---

### `nutrition_calculator.py` — Deterministic Macro Calculation

```
For each ingredient in recipe:
    macros = catalog[ingredient_id].ifct_macros_per_100g
    factor = grams / 100
    nutrition += macros × factor

per_serving = total / servings
```

**Why this is NOT in the LLM:**
- LLMs give different calorie answers each time
- IFCT data is authoritative for Indian ingredients
- Deterministic: same recipe → same nutrition, always

---

## 7. AI Integration

### Bedrock (Claude) — Used for:
1. **Bill normalization** — mapping raw Textract strings to catalog IDs
2. **Fridge photo analysis** — identifying ingredients from images
3. **Recipe generation** — creating constrained recipes

### Textract (AnalyzeExpense) — Used for:
1. **Receipt parsing** — extracting line items, vendor, date, total

### Why two AI services?
- Textract is purpose-built for receipts (high accuracy)
- Bedrock Vision handles general images (fridge photos)
- Using one for the other's job would fail (Textract can't see food, Bedrock can't parse receipts)

---

## 8. Scheduled Jobs

### Expiry Check Cron

**Schedule:** Daily at 7 AM IST (`cron(30 1 * * ? *)`)

**What it does:**
1. Scans all DynamoDB items
2. Filters for items expiring within 0-2 days
3. Groups by household
4. Sends SNS notification per household

**SNS message → downstream:**
- SNS → Lambda → Push notification (mobile)
- SNS → SES → Email
- SNS → WhatsApp Business API (future)

---

## 9. Error Handling

### Per-function pattern

Every Lambda follows this pattern:

```python
def handler(event, context):
    try:
        # Parse input
        # Validate with Pydantic (400 on failure)
        # Business logic
        # Return 200
    except SomeKnownError as exc:
        # Return 400 with clear message
    except Exception as exc:
        # Log error
        # Return 500 with generic message
        # Never expose raw exception to client
```

### Bedrock error handling

```python
# invoke_claude_json:
1. Send prompt
2. Parse response
3. If JSON fails → retry once with stricter prompt
4. If still fails → ValueError (Lambda returns 500)
```

### Textract error handling

```python
# analyze_expense:
1. Call Textract
2. If no documents → ValueError("not a receipt")
3. If no line items → ValueError("could not extract items")
4. Client receives clear error message they can show to user
```

---

## 10. Local Development

### Prerequisites
- Docker (for DynamoDB Local + SAM)
- Python 3.12
- AWS SAM CLI

### Step-by-step

```bash
# 1. Start DynamoDB Local
docker run -p 8000:8000 amazon/dynamodb-local

# 2. Create table
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
    IndexName=GSI1,KeySchema=[...],Projection={ProjectionType=ALL} \
  --billing-mode PAY_PER_REQUEST \
  --endpoint-url http://localhost:8000

# 3. Seed catalog
TABLE_NAME=UseItUp-dev \
DYNAMODB_ENDPOINT_URL=http://localhost:8000 \
AWS_DEFAULT_REGION=us-east-1 \
AWS_ACCESS_KEY_ID=local \
AWS_SECRET_ACCESS_KEY=local \
python scripts/seed_dynamo.py

# 4. Run API locally
sam build
sam local start-api

# 5. Test
curl http://127.0.0.1:3000/inventory?household_id=hh-test123

# 6. Run unit tests (no AWS needed)
pytest tests/unit/ -v
```

---

## 11. Deployment

### Frontend (Amplify)
```bash
cd UseItUp
git init && git add . && git commit -m "Deploy"
gh repo create useitup --public --source=. --remote=origin --push
# Connect to Amplify Console → auto-detects Vite → deploy
```

### Backend (SAM)
```bash
cd backend
sam build
sam deploy --guided
# Follow prompts: stack name, region, confirm changeset

# Seed catalog in production
TABLE_NAME=UseItUp-dev python scripts/seed_dynamo.py
```

### Post-deploy verification
```bash
# Get API endpoint
sam list stack-outputs --stack-name UseItUp-dev

# Test upload URL
curl -X POST https://xxx.execute-api.us-east-1.amazonaws.com/dev/upload-url \
  -H "Content-Type: application/json" \
  -d '{"household_id":"test123","upload_type":"bill"}'

# Test inventory
curl https://xxx.execute-api.us-east-1.amazonaws.com/dev/inventory?household_id=test123
```
