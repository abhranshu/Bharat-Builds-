# UseItUp — Resume Content Pack

> Everything below is fact-checked against the actual code in this repo
> (11 Lambda handlers, 95 unit tests, 192 hero frames, ~6,100 LOC, 12 AWS services).

---

## 1. READY-TO-PASTE PROJECT ENTRY (full version)

**UseItUp — AI-Powered Kitchen Intelligence & Food-Waste Reduction System** | *Bharat Builds Hackathon 2025*
*Python 3.12 · AWS Lambda · DynamoDB · Amazon Bedrock (Nova 2 Lite) · Textract · API Gateway · EventBridge · SNS · S3 · CloudFront · AWS SAM · Vanilla JS · Vite · GSAP*

- Architected and deployed a fully serverless, event-driven "kitchen operating system" on AWS (SAM/CloudFormation, `ap-south-1`) comprising **11 Python 3.12 Lambda microservices**, an 8-route API Gateway REST API, a single-table DynamoDB store, and S3-triggered async ingestion pipelines — all within the hackathon build window.
- Built a **multi-modal AI ingestion engine**: browser uploads go straight to Amazon S3 via presigned PUT URLs, where suffix-based S3 event triggers route receipts to **Textract `AnalyzeExpense`** and fridge photos to **Amazon Bedrock Nova 2 Lite Vision**; raw OCR/vision output is then normalized by Bedrock into a canonical catalog of **22 Indian staples with bilingual (Hindi/English) aliases** (*dhania, tamatar, atta, aloo*).
- Shipped a **proactive expiry-prediction subsystem**: a dynamic shelf-life engine computes per-ingredient expiry dates on ingest, and an **EventBridge daily cron → Lambda → Amazon SNS** pipeline pushes expiry nudges to households before food spoils — turning a stateless chatbot interaction into a scheduled, stateful system.
- Eliminated LLM hallucination in nutrition by building a **deterministic IFCT-2017 (ICMR-NIN) macro engine** that computes calories, protein, carbs, fat, and fiber from ingredient gram-weights in Python, instead of prompting a model for estimates; recipes are generated with Bedrock (**temperature 0.2**) strictly constrained to what is actually in the user's inventory plus their dietary profile (Vegetarian / Vegan / Eggetarian / Non-Veg / Jain), meal type, and prep-time limit.
- Closed the loop end-to-end: **"Mark as Cooked"** atomically deducts exact ingredient quantities from DynamoDB, logs macros against daily targets, and refreshes the live inventory view — delivering a photo → inventory → recipe → cooking → updated-inventory feedback cycle.
- Hardened reliability with **95 pytest unit tests** covering Bedrock invocation/retry, Textract parsing, DynamoDB serialization, expiry logic, and catalog validation, plus a **Pydantic-validated JSON retry loop** that auto-reprompts the model on malformed output, and a **3.75 MB inline-image byte guard** before every vision call.
- Delivered a **192-frame scroll-scrubbed cinematic hero** (Apple-style technique) using GSAP ScrollTrigger + HTML5 Canvas at 60 FPS, with chunked preloading and a progress-gated loader, served as immutable assets from **S3 behind CloudFront with Origin Access Control**.


---

## 2. CONDENSED VERSION (3 bullets — best if space is tight)

**UseItUp — AI Kitchen Intelligence & Food-Waste Reduction System** | *Bharat Builds Hackathon 2025*
*AWS Lambda · Amazon Bedrock (Nova 2 Lite) · Textract · DynamoDB · API Gateway · EventBridge · SNS · S3/CloudFront · AWS SAM · Python 3.12 · Vanilla JS + Vite + GSAP*

- Built and deployed a serverless, event-driven food-waste prevention platform on AWS — **11 Python Lambda microservices**, API Gateway REST API, DynamoDB single-table design, and S3-triggered ingestion — developed at the **Bharat Builds Hackathon 2025**.
- Engineered a multi-modal AI pipeline (**Textract `AnalyzeExpense` for grocery bills + Bedrock Nova 2 Lite Vision for fridge photos**) that converts real-world captures into a persistent household inventory, then drives an **EventBridge cron + SNS** job that proactively warns users before perishable items expire.
- Replaced hallucination-prone LLM nutrition estimates with a **deterministic IFCT-2017 (ICMR-NIN) macro calculator**, enforced strictly inventory-constrained recipe generation, and validated the system with **95 pytest unit tests** plus a Pydantic-guarded JSON retry loop.

---

## 3. ULTRA-SHORT VERSION (1–2 lines, for a dense "Projects" list)

**UseItUp — Serverless AI Food-Waste Prevention System** *(Bharat Builds Hackathon 2025)* — Built an 11-Lambda AWS serverless platform that ingests grocery bills and fridge photos (AWS Textract + Amazon Bedrock Vision) into a persistent DynamoDB inventory, proactively nudges users before food expires (EventBridge + SNS), and generates inventory-constrained recipes with deterministic IFCT-2017 nutrition; full SAM/CloudFormation IaC and 95 unit tests.

---

## 4. ONE-LINE PITCH (for Summary/Objective sections and elevator pitches)

> "UseItUp isn't an AI that answers questions about your food — it's a serverless kitchen operating system that remembers what you own, predicts what you'll waste, and tells you what to cook before it's too late."

---

## 5. ATS KEYWORD / SKILLS LINE (paste under the project or into your Skills section)

`AWS Lambda` · `AWS SAM` · `CloudFormation` · `Amazon API Gateway` · `Amazon DynamoDB (single-table design, GSI, PITR)` · `Amazon S3 (presigned URLs, event notifications)` · `Amazon CloudFront (OAC)` · `Amazon Bedrock (Nova 2 Lite, Converse API, multimodal vision)` · `AWS Textract` · `Amazon EventBridge (cron)` · `Amazon SNS` · `IAM` · `Python 3.12` · `Boto3` · `Pydantic` · `pytest` · `Serverless & Event-Driven Architecture` · `REST API Design` · `Prompt Engineering + JSON Schema Validation` · `JavaScript (ES Modules)` · `Vite` · `GSAP ScrollTrigger` · `HTML5 Canvas` · `CDN Asset Optimization`

---

## 6. LINKEDIN / GITHUB PROJECT SECTION (slightly more narrative)

**UseItUp — AI-Powered Kitchen Intelligence & Food-Waste Reduction System**
*Built at the Bharat Builds Hackathon (2025) — Serverless AWS · Multi-Modal AI · Python*

Every year India wastes roughly 40% of the food it produces, and most households have no idea what is actually sitting in their fridge until it spoils. UseItUp is a persistent, proactive layer on top of that problem: snap a photo of a crumpled grocery receipt or an open fridge, and the system builds a living inventory.

Under the hood: presigned S3 uploads trigger a suffix-routed ingestion pipeline — AWS Textract `AnalyzeExpense` for thermal receipts and Amazon Bedrock Nova 2 Lite Vision for fridge photos — with Bedrock normalizing messy OCR text into a canonical catalogue of 22 Indian staples (*dhania, tamatar, atta, aloo*). A shelf-life engine stamps each item with a predicted expiry date, and a daily EventBridge cron fans out SNS nudges before anything spoils. Recipes are generated at temperature 0.2 and strictly constrained to what the household already owns, respecting Jain/Vegan/Eggetarian/Vegetarian profiles — and their macros come from a deterministic IFCT-2017 (ICMR-NIN) calculator rather than model guesswork. Marking a meal "cooked" deducts exact quantities and updates the day's nutrition bars.

11 Lambda microservices, DynamoDB single-table design with a GSI answering "which households have this ingredient?", infrastructure as code via AWS SAM, 95 pytest unit tests, and a 192-frame scroll-scrubbed GSAP/Canvas hero sequence served through CloudFront.


---

## 7. TALKING POINTS (for interviews and judge-style follow-ups)

| If they ask… | Say this |
|---|---|
| "Why not just use ChatGPT?" | A chatbot is stateless and reactive — close the tab and the context is gone. UseItUp persists inventory in DynamoDB, runs a scheduled cron, and pushes notifications; it has memory, a clock, and a feedback loop. |
| "How do you stop the LLM hallucinating nutrition?" | We never ask the model for numbers. Ingredient gram-weights are multiplied against a deterministic IFCT-2017 (ICMR-NIN) table in Python; the model only parses and generates text. |
| "Why single-table DynamoDB?" | One table models household profile, inventory items, cooked meals, upload state and catalogue metadata via composite `PK`/`SK` keys, keeping access patterns to a single-digit-millisecond query. A GSI1 on `CAT#{ingredient_id}` answers the reverse "which households have this?" query. |
| "How is ingestion reliable?" | S3 event notifications decouple upload from processing, so the HTTP request returns instantly (presigned PUT); the UI polls an `UPLOAD#{image_id}` state record until it flips from `pending` to `processed`. |
| "What about bad model output?" | Every response is validated against Pydantic schemas; on invalid JSON or Markdown-wrapped output the Bedrock client immediately retries with an enforced format constraint. |
| "Why not just OCR everything?" | Receipts and fridge interiors are opposites — receipts are text-dense line items (Textract's strength), fridges need visual object recognition. We route each to the right AI service instead of forcing one model to do both. |
| "How did you test a serverless app?" | 95 pytest unit tests with mocked Boto3 clients — covering Bedrock retry logic, Textract line-item parsing, DynamoDB serialization, expiry-prediction math and catalogue validation — runnable via `python -m pytest` in under a second. |
| "What would you do with more time?" | Real push notifications per household (currently a shared SNS topic), a proper food-waste analytics dashboard, regional-language bill support, and swapping the demo household id for Cognito-authenticated users. |

---

## 8. NUMBERS YOU CAN SAFELY CLAIM (all verified inside this repo)

| Claim | Verified value | Source |
|---|---|---|
| AWS Lambda functions | **11** | `UseItUp/backend/template.yaml` |
| API Gateway routes | **8** (`/upload-url`, `GET\|POST\|DELETE /inventory`, `/recipes/generate`, `/cooked`, `/nutrition`, `/profile`) | `template.yaml` |
| Unit tests | **95** (pytest) | `UseItUp/backend/tests/unit/` |
| Ingredient catalogue | **22** Indian staples with Hindi/English aliases + IFCT macros | `backend/src/shared/ingredient_catalog.py` |
| Hero animation frames | **192** | `UseItUp/src/heroScrollSequence.js` |
| Hand-written code | **~6,100 lines** (≈3,600 backend Python, ≈2,500 frontend JS/CSS/HTML) | `wc -l` over `UseItUp/src` |
| Lambda runtime | **Python 3.12, arm64** (AWS Graviton) | `template.yaml` |
| Model | **Amazon Bedrock — Amazon Nova 2 Lite** (`global.amazon.nova-2-lite-v1:0`) via the Converse API | `shared/bedrock_client.py` |
| Inference temperature | **0.2** (deterministic, hallucination-resistant) | `shared/bedrock_client.py` |
| Cron schedule | **Daily `cron(30 1 * * ? *)`** = 7:00 AM IST | `template.yaml` |
| Diet profiles | **5** — Vegetarian, Non-Veg, Vegan, Eggetarian, Jain | `readMe.md` |
| AWS services used | **12** — Lambda, API Gateway, DynamoDB, S3, CloudFront, Bedrock, Textract, EventBridge, SNS, SAM, IAM, CloudFormation | `UseItUp/awsservice.md` |
| Live infra components | Deployed SAM stack `UseItUp-dev` in `ap-south-1` + a live CloudFront distribution serving the frontend | `samconfig.toml`, `heroScrollSequence.js` |



---

## 9. HONESTY NOTES (read before submitting)

- ✅ **Do** say: "Built at the **Bharat Builds Hackathon** (2025) — designed, architected and deployed end-to-end during the event."
- ✅ **Do** keep the "designed / architected / built / deployed" framing — that is accurate. The repo ships a real AWS SAM deployment config (`UseItUp-dev`, `ap-south-1`) and the frontend pulls its 192 frames from a live CloudFront distribution, so "deployed on AWS" is defensible.
- ⚠️ The **40% waste / ~$14B** figures come from the project's own problem statement (cited industry estimates for India). If asked, attribute them as "published industry estimates" — never as your own measurement.
- ⚠️ **Do not claim users, MAU, downloads, revenue, or "used by X households."** None exist; the demo household id is literally `hh-demo`.
- ⚠️ **Do not claim model training / custom ML models.** This project *integrates* managed AI services (Bedrock, Textract); it trains nothing. Say "multi-modal AI integration", "prompt engineering with schema validation", and "deterministic nutrition computation" instead.
- ⚠️ Older docs in the repo say "10 Lambda functions" in places; **11** is correct per `template.yaml`. Use 11.
- ⚠️ If you didn't personally write the frontend animation sequence, phrase that bullet as "shipped/integrated" rather than "implemented from scratch" — and be ready to explain ScrollTrigger's `scrub` + `pin` behaviour either way.
- 💡 **Strongest prep:** be able to open `backend/template.yaml` and trace one request end-to-end — upload → S3 event → Textract/Bedrock → DynamoDB → recipe → `Mark as Cooked`. That single walkthrough defends every bullet above.

---

## 10. SUGGESTED PLACEMENT IN YOUR RESUME

1. **Projects section (top project):** use Section 1 (full) if you have ~6 bullets of space, else Section 2 (condensed).
2. **Resume header / Summary:** drop the one-liner pitch in Section 4 and add "Bharat Builds Hackathon 2025 participant" to your achievements line.
3. **Skills section:** paste the condensed subset of Section 5 — at minimum: `AWS (Lambda, API Gateway, DynamoDB, S3, CloudFront, Bedrock, Textract, EventBridge, SNS, SAM)`, `Python`, `Serverless Architecture`, `REST APIs`, `JavaScript/GSAP`, `pytest`.
4. **LinkedIn → Projects:** use Section 6, and put the GitHub repo URL from `git remote -v` (`https://github.com/abhranshu/Bharat-Builds-.git`) in the "Associated with" field.
5. **Achievements/Awards:** "Built and shipped **UseItUp** — a serverless, multi-modal AI food-waste reduction platform — at the **Bharat Builds Hackathon (2025)**."

