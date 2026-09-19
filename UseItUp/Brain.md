# Brain.md — UseItUp Architecture & Knowledge Base

This is the single source of truth for **why** things are built the way they are.
For **how** to run/deploy, see `README.md` and `deployment.md`.

---

## The Problem

Indian households waste enormous amounts of food. The average Indian family
throws away 15-20% of purchased produce because:

- They forget what they bought
- They don't know when things expire
- They don't know what to cook with what they have
- Grocery bills are discarded instead of tracked

**UseItUp** solves this with AI: scan your fridge or upload a grocery bill,
and the system does the rest.

---

## The Solution — Two Parts

### Part 1: Cinematic Landing Page

A scroll-scrubbed image sequence that tells the story visually.
The user scrolls through a "movie" of food being wasted, a fridge being opened,
and a meal being cooked. At the end, a CTA invites them to try the app.

**Why this approach:**
- Apple-style product pages feel premium and build emotional connection
- The scroll-scrub technique is proven (Apple,why.zero.university)
- 192 frames at 12fps ≈ 16 seconds of animation — enough for a short story
- GSAP ScrollTrigger handles all the complexity with minimal code

### Part 2: AI Backend

A serverless API that processes food images, extracts ingredients, predicts
expiry, generates recipes, and tracks nutrition.

**Why serverless:**
- Cost: pay only for requests, no idle servers
- Scale: handles 10 or 10,000 users with zero config
- SAM: infrastructure-as-code, testable locally, deployable in one command

---

## Architecture Decisions

### Frontend

#### Why GSAP over CSS animations?
CSS animations can't scrub to scroll position. GSAP ScrollTrigger maps
scroll progress (0→1) to frame index (0→191) with `scrub: true`.
This is the only way to get smooth scroll-driven playback without
requestAnimationFrame loops.

#### Why Canvas instead of `<img>` tag swapping?
- Canvas gives pixel-perfect control over cover-fit rendering
- No DOM thrashing (192 img tags would be 192 reflows)
- `drawImage()` is hardware-accelerated
- Single element, single paint per frame

#### Why ES modules with Vite?
- `import gsap from "gsap"` works natively in Vite
- No build-step workarounds needed
- Tree-shaking removes unused GSAP features
- Hot reload during dev

#### Why `window.gsap` didn't work
The initial implementation tried to access GSAP via `window.gsap` (the CDN
approach). But since GSAP was installed via npm, Vite bundles it as an ES
module — `window.gsap` is undefined. The fix was proper imports:

```js
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
```

#### Why blur-to-sharp text entrance?
A flat opacity fade feels like a web page. A `blur(8px) → blur(0)` transition
mimics a camera focusing — it feels cinematic and matches the visual language
of the video frames themselves. The easing `cubic-bezier(0.16, 1, 0.3, 1)`
has a fast start and slow settle, like a dolly shot landing.

#### Why separate text overlay from CTA?
The text lines (0-90% progress) tell the story. The CTA (95-100%) is the
conversion moment. If they overlapped, the CTA would compete with the last
narrative beat. By keeping them in separate z-index layers and using
progress-based visibility, the CTA only appears when the story is done.

### Backend

#### Why single-table DynamoDB?
- One table = one billing entity, one scaling knob
- Access patterns are all known upfront (no ad-hoc queries)
- GSI1 handles catalog queries independent of household
- DynamoDB is cheaper and faster than RDS for this access pattern

#### Why Textract + Bedrock (two AI services)?
- **Textract** is purpose-built for receipts — it extracts line items,
  vendor names, dates, and totals with high accuracy
- **Bedrock Vision** is general-purpose — it can identify ingredients
  from fridge photos where Textract would see nothing
- Using both gives the best result for each input type

#### Why deterministic nutrition calculation (not LLM)?
LLMs are great at generating recipes but terrible at math. If you ask
Claude "how many calories in 150g of paneer?", it might say 200 or 400.
The IFCT (Indian Food Composition Tables) data is authoritative. By
computing nutrition from catalog data, we get reproducible, accurate macros
every time.

#### Why retry Bedrock JSON responses once?
Claude sometimes wraps JSON in markdown fences or adds explanatory text.
The first attempt parses with fence-stripping. If that fails, the retry
prompt explicitly says "respond with ONLY valid JSON." One retry catches
99% of cases. Two retries would add latency for diminishing returns.

#### Why 70% shelf life discount for fridge photos?
When you upload a bill, you know the purchase date — full shelf life applies.
When you photograph a fridge, you don't know when items were bought. Using
70% of shelf life is a conservative heuristic: it errs on the side of
"use it soon" rather than "it's probably fine." This is configurable.

#### Why EventBridge Scheduler instead of CloudWatch Events?
EventBridge Scheduler supports cron expressions with timezone targeting
(7 AM IST = `cron(30 1 * * ? *)`). CloudWatch Events doesn't support
timezone-aware scheduling as cleanly.

---

## Data Model

### DynamoDB Key Design

```
PK                          SK                     Purpose
─────────────────────────────────────────────────────────────
HH#<household_id>          ITEM#<item_id>         Ingredient in fridge
HH#<household_id>          PROFILE                 User preferences
HH#<household_id>          COOKED#<timestamp>     Meal log
HH#<household_id>          UPLOAD#<image_id>      Upload tracking
CAT#<ingredient_id>        META                   Catalog entry
```

### Why this key scheme?
- All household data clusters under `HH#<id>` — single query gets everything
- `COOKED#<timestamp>` sorts chronologically — "today's meals" is a range query
- `CAT#<id>` isolates the catalog — can be scanned independently via GSI1
- Item IDs include the ingredient_id for quick lookups without a second query

### IFCT Data

The Indian Food Composition Tables (IFCT) provide authoritative nutrition
data for Indian ingredients. We store `per_100g` macros in the catalog and
scale deterministically:

```
nutrition = (ifct_macros_per_100g × grams) / 100
```

The catalog ships with 20 common Indian ingredients. The seed script loads
them into DynamoDB. Adding more is a catalog update, not a code change.

---

## Frame Sequence Architecture

### How it works

```
CloudFront CDN
    ↓ serves
Browser preloads 192 images
    ↓ stores in
Array: images[0] → images[191]
    ↓ scroll drives
GSAP ScrollTrigger: scroll % → seq.frame (integer)
    ↓ triggers
Canvas drawImage(images[seq.frame])
```

### Why grouped prefixes (c1, c2, c3a, c3b)?
The animation was produced in 4 clips. Each clip was exported as a
separate batch. The prefix groups map to these production batches:
- `c1` (1-48): Fridge closed, neglect
- `c2` (49-96): Door opens, produce revealed
- `c3a` (97-144): Push-in transition
- `c3b` (145-192): Plated meal reveal

This keeps production files organized and allows re-exporting individual
clips without re-rendering the entire sequence.

### Why `scrub: 0.5`?
Scrub smoothing. A value of `0` means instant frame response (jarring).
A value of `1` means significant lag (feels unresponsive). `0.5` is the
sweet spot — smooth but connected to the user's scroll input.

### Why `snap: "frame"`?
Without snapping, GSAP interpolates between frames (e.g., frame 42.7).
The canvas draws `images[42]` (floor). Snapping ensures frame numbers
are integers, so each scroll position maps to exactly one frame.

### Why `end: "+=4000"`?
The total scroll distance in pixels. 4000px ≈ 4 viewport heights on a
1080p screen. This means 192 frames over ~4 scrolls — each scroll shows
~48 frames (one clip). The user gets a comfortable pace without feeling
rushed or bored.

---

## Error Handling Philosophy

### Backend
- Every Lambda wraps logic in try/except
- 400 for client errors (Pydantic validation)
- 500 for server errors (AWS failures)
- Never expose raw exception text — generic message + log the detail
- Bedrock: retry once on malformed JSON, then fail with clear message
- Textract: distinguish "not a receipt" from "server error"

### Frontend
- Loader counts errored frames as loaded (so loading always finishes)
- Canvas `render()` guards against missing/unfinished images
- Text overlay silently handles missing data attributes
- CTA visibility is progress-based, not frame-based (more robust)

---

## Cost Model

### Landing Page
- Amplify Hosting: free tier covers it (5 GB storage, 15 GB/month)
- CloudFront for frames: free tier (1 TB/month)
- Total: effectively $0/month for a landing page

### Backend (per month, ~1000 users)
| Service | Free Tier | Actual |
|---------|-----------|--------|
| Lambda | 1M requests | $0 |
| DynamoDB | 25 GB + 25 RCU | $0 |
| S3 | 5 GB | $0 |
| Bedrock | Pay per token | ~$20-50 |
| Textract | 1K pages/month | ~$5-15 |
| API Gateway | 1M calls | $1 |
| SNS | 1M publishes | $0 |
| EventBridge | 14M events | $0 |

**Total: ~$25-65/month** for ~1000 active users.

The cost scales linearly. Bedrock is the main variable — each recipe
generation uses ~2K tokens input + ~1K tokens output.

---

## What's NOT Implemented Yet

### Deliberate scope cuts
- [ ] Camera capture (placeholder cards only)
- [ ] Image upload UI (backend ready, frontend pending)
- [ ] User authentication (household_id is currently passed as param)
- [ ] WhatsApp/SMS notifications (SNS only, no channel integration)
- [ ] Multi-language support (profile has `language` field, not wired to prompts)
- [ ] Share recipes / social features
- [ ] Grocery list generation
- [ ] Price tracking from bills

### Not planned
- [ ] Real-time chatbot interface
- [ ] Meal planning / calendar
- [ ] Restaurant integration

---

## Key Learnings

1. **GSAP + npm requires ES imports, not window globals.** This is the #1
   gotcha when moving from CDN to Vite. The build succeeds either way,
   but the animation silently fails.

2. **Cover-fit on canvas requires manual math.** There's no CSS
   `object-fit` equivalent for canvas `drawImage()`. The aspect ratio
   comparison and offset calculation is ~20 lines of code that must
   handle both "wider than canvas" and "taller than canvas" cases.

3. **Frame loading must complete before ScrollTrigger init.** If you
   register ScrollTrigger before all images are in memory, the first
   frame renders blank and the animation stutters. The loader is not
   optional — it's load-bearing.

4. **LLMs are unreliable for nutrition math.** A recipe generation prompt
   that asks Claude to calculate calories will give different answers each
   time. Always use deterministic calculation from authoritative data.

5. **Textract is great at receipts, terrible at fridge photos.** Bedrock
   Vision is the opposite. Don't try to use one service for both —
   they have fundamentally different input characteristics.

6. **DynamoDB single-table design is simpler than it looks.** The key
   insight: PK clusters related data, SK provides the sort order. That's
   it. The complexity people complain about comes from trying to make
   one table do too many things. For this app, two key prefixes
   (`HH#` and `CAT#`) cover everything.

---

## References

- [GSAP ScrollTrigger Docs](https://gsap.com/docs/v3/Plugins/ScrollTrigger/)
- [Why.Zero University](https://why.zero.university/) — scroll-sequence reference
- [Indian Food Composition Tables](https://www.nnmb.res.in/) — IFCT data source
- [AWS SAM Docs](https://docs.aws.amazon.com/serverless-application-model/)
- [Amazon Textract AnalyzeExpense](https://docs.aws.amazon.com/textract/latest/dg/ExpenseAnalysis.html)
- [Amazon Bedrock](https://docs.aws.amazon.com/bedrock/)
