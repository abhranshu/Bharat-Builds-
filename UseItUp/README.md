# UseItUp

**Stop wasting food. Start cooking smart.**

UseItUp is an AI-powered food-waste reduction app for Indian households. Upload a photo of your grocery bill or fridge, and the system extracts ingredients, predicts expiry dates, and generates recipes constrained to what you already own — with computed nutrition per serving.

---

## Live Demo

- **Landing page:** [useitup.app](https://useitup.app) *(coming soon)*
- **Frames served from:** CloudFront CDN

---

## Project Overview

```
UseItUp/
├── index.html              # Landing page entry
├── style.css               # Global styles + responsive
├── src/
│   ├── main.js             # Vite entry point
│   └── heroScrollSequence.js  # Canvas scroll animation + GSAP
├── backend/
│   ├── template.yaml       # SAM infrastructure
│   ├── src/functions/      # 9 Lambda functions
│   ├── src/shared/         # Shared models, clients, helpers
│   └── tests/              # Unit tests
└── deployment.md           # AWS deployment guide
```

---

## Tech Stack

### Frontend
| Layer | Technology |
|-------|-----------|
| Build | Vite |
| Language | Vanilla JavaScript (ES modules) |
| Animation | GSAP + ScrollTrigger |
| Rendering | HTML5 Canvas (image sequence) |
| Frames | 192 JPEGs on CloudFront CDN |

### Backend
| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| IaC | AWS SAM |
| Compute | AWS Lambda (one function per endpoint) |
| API | API Gateway REST API |
| Database | DynamoDB (single-table design) |
| Storage | S3 (image uploads) |
| AI | Amazon Bedrock (Claude) + Amazon Textract |
| Scheduling | EventBridge Scheduler |
| Notifications | SNS |
| Validation | Pydantic |

---

## Frontend — Cinematic Landing Page

A scroll-scrubbed image sequence landing page with:

- **Loading screen** with live progress bar (preloads all 192 frames)
- **Canvas rendering** with cover-fit (object-fit: cover)
- **GSAP ScrollTrigger** pins the hero and scrubs through frames on scroll
- **Text overlay** with 5 narrative lines that fade in/out at specific scroll percentages
- **CTA "Scan Your Fridge"** appears at 95% scroll progress
- **App entry section** with feature cards and early access CTA
- **Fraunces** editorial serif typography with warm off-white palette
- **Blur-to-sharp entrance** animations on text lines

### Running Locally

```bash
cd UseItUp
npm install
npm run dev
```

### Key Files

| File | Purpose |
|------|---------|
| `src/heroScrollSequence.js` | All animation logic: frame config, preloading, canvas rendering, GSAP setup, CTA reveal, text overlay |
| `src/main.js` | Entry point, imports and initializes hero sequence |
| `style.css` | All styles: loader, hero, text overlay, CTA, app entry, cards, footer |
| `index.html` | Markup: loader, hero section, canvas, text overlay, CTA, app entry |

### Frame Naming Convention

Frames use grouped prefixes, **not** sequential `frame_XXX`:

| Range | Prefix | Files |
|-------|--------|-------|
| 1–48 | `c1` | `c1_001.jpg` → `c1_048.jpg` |
| 49–96 | `c2` | `c2_001.jpg` → `c2_048.jpg` |
| 97–144 | `c3a` | `c3a_001.jpg` → `c3a_048.jpg` |
| 145–192 | `c3b` | `c3b_001.jpg` → `c3b_048.jpg` |

Served from: `https://d21m7w28iod98m.cloudfront.net/frames/v1/`

---

## Backend — AI Food-Waste API

### Core Flow

```
1. User uploads photo → presigned S3 URL
2. S3 triggers Lambda → Textract (bills) or Bedrock Vision (fridge photos)
3. AI extracts ingredients → maps to canonical IDs
4. Expiry dates predicted from catalog shelf life
5. User asks for recipes → Bedrock generates constrained to inventory
6. Nutrition calculated deterministically from IFCT data (not LLM)
7. User marks meal as cooked → inventory deducted
8. Daily cron checks expiring items → SNS notifications
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/upload-url` | Generate presigned S3 PUT URL |
| `GET` | `/inventory` | Get household inventory |
| `POST` | `/cooked` | Mark recipe as cooked |
| `POST` | `/recipes/generate` | Generate AI recipes |
| `GET` | `/nutrition` | Daily nutrition summary |
| `PUT` | `/profile` | Update household profile |
| `S3` | `uploads/*/bill_*` | Process grocery bill |
| `S3` | `uploads/*/fridge_*` | Process fridge photo |
| `EventBridge` | `rate(1 day)` | Expiry check + SNS nudge |

### Running Backend Locally

```bash
cd backend

# Install deps
pip install -r requirements.txt pytest

# Start DynamoDB Local
docker run -p 8000:8000 amazon/dynamodb-local

# Create table + seed catalog
python scripts/seed_dynamo.py

# Build and run
sam build
sam local start-api

# Run tests
pytest tests/unit/ -v
```

### DynamoDB Single-Table Design

| PK | SK | Data |
|----|-----|------|
| `HH#<id>` | `ITEM#<item>` | ingredient, quantity, expiry, source |
| `HH#<id>` | `PROFILE` | diet, household size, language, targets |
| `HH#<id>` | `COOKED#<ts>` | recipe name, ingredients used, nutrition |
| `HH#<id>` | `UPLOAD#<img>` | status, raw AI output |
| `CAT#<id>` | `META` | canonical name, aliases, shelf life, IFCT macros |

---

## Deployment

### Frontend (Amplify — recommended)

See `deployment.md` for full instructions.

```bash
cd UseItUp
git init && git add . && git commit -m "Initial deploy"
gh repo create useitup-landing --public --source=. --remote=origin --push
# Connect to Amplify Console → auto-detects Vite → deploy
```

### Backend (SAM)

```bash
cd backend
sam build
sam deploy --guided
```

---

## Project Docs

| File | Description |
|------|-------------|
| `README.md` | This file — project overview |
| `Brain.md` | Architecture decisions, knowledge base, how everything fits |
| `deployment.md` | Step-by-step AWS deployment guide (Amplify + S3/CloudFront) |
| `backend/README.md` | Backend-specific docs, API reference, local dev setup |
| `Info.md` | Original project brief (scroll-sequence technique) |

---

## Environment Variables

### Backend

| Variable | Description | Default |
|----------|-------------|---------|
| `TABLE_NAME` | DynamoDB table name | `UseItUp-dev` |
| `BUCKET_NAME` | S3 upload bucket | — |
| `SNS_TOPIC_ARN` | Expiry notification topic | — |
| `BEDROCK_MODEL_ID` | Claude model | `anthropic.claude-sonnet-4-20250514-v1:0` |

---

## License

Private project. Not for redistribution.
