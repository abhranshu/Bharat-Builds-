# Scroll-Scrubbed Image Sequence Website — Project Brief

Reference: [why.zero.university](https://why.zero.university/)

## What this actually is

Not live 3D, not a video player. It's a **scroll-scrubbed image sequence**:
a pre-rendered/filmed animation broken into individual still frames, drawn
one at a time onto an HTML5 `<canvas>`, where **scroll position selects
which frame is shown**. Same technique Apple used for AirPods/iPhone
product pages. The "movie" feeling comes entirely from the direction and
choreography inside the frames — not from any clever web tech.

Pipeline: `Animate/film → export frame sequence → store in S3/CloudFront
→ preload in browser → GSAP ScrollTrigger maps scroll % to frame index →
draw to canvas`

---

## Step-by-step build order

### 1. Lock the story and shot list before producing anything
Decide what happens frame-by-frame: what the hand does, what it points at,
what it touches, how the "camera" moves. Storyboard it, even roughly.
Directing this well matters more than any code in this project.

### 2. Choose your production method
- **3D render (Blender)** — full control, most polish, most time. Best if
  you can model/animate.
- **Filmed** — faster, needs a camera and steady rig, good if the story
  works as live action.
- **After Effects / 2D layered** — middle ground, no 3D modeling needed.

### 3. Produce and export as a raw frame sequence — never via a compressed video
- **Blender:** Output Properties → File Format → PNG or JPEG (not FFmpeg
  Video). Turn **motion blur off** in render settings for crisp stills.
- **Filmed:** shoot at **high shutter speed (1/500s+)** to avoid motion
  blur baked into frames, at your camera's highest-bitrate mode.
- Never extract frames from an already-compressed/exported video if you
  can avoid it — every re-encode loses detail permanently.

### 4. Pick frame rate and count for a 10–15 sec sequence
- **12fps (recommended default):** 120–180 frames
- 15fps: 150–225 frames
- 24fps (heaviest, rarely needed for scroll playback): 240–360 frames

### 5. If extracting from existing video anyway
```bash
ffmpeg -i source.mp4 -vf "fps=12" -q:v 2 frames/frame_%04d.jpg
```
- `-q:v 2` = high JPEG quality (scale 1–31, lower is better)
- Don't add a `scale=` filter unless resizing is truly needed — resolution
  lost to the source video's compression can't be recovered
- If blur persists, the source isn't sharp enough — re-render/re-shoot
  with motion blur off, or try AI upscaling (Topaz Video AI) as a
  last resort (works on soft frames, not motion-smeared ones)

### 6. Compress frames for web before upload
- Export as **JPG**, not PNG (no alpha needed, much smaller)
- Target 60–75% quality, resized to actual display width (don't ship
  raw render resolution)
- Consider sampling every 2nd/3rd frame if the eye can't tell the
  difference — halves asset count
- Check total folder size (`du -sh frames/`) early — know your load
  budget before building the full sequence

### 7. Store frames in S3 + CloudFront — not git
Git isn't built for binaries — every commit duplicates the full file,
repo bloats permanently, clones slow down.

```bash
aws s3 sync ./frames s3://your-site-assets/frames/v1/ \
  --cache-control "public, max-age=31536000, immutable"
```
- Front the bucket with **CloudFront** (Origin Access Control, not a
  public bucket) — never serve frames directly from S3
- Version by path (`frames/v1/`, `frames/v2/`) when you re-render, so a
  redeploy can't mix old and new frames
- Add the local frames folder to `.gitignore`:
  ```
  /public/frames/
  ```
- Keep frames on local disk during active dev; sync to S3 only when
  testing the real loading experience or deploying

### 8. Build the canvas + scroll-scrub logic
```html
<canvas id="hero-canvas"></canvas>
```
```js
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
gsap.registerPlugin(ScrollTrigger);

const canvas = document.getElementById("hero-canvas");
const ctx = canvas.getContext("2d");
const frameCount = 180; // match your actual sequence length
const images = [];
const seq = { frame: 0 };

function currentFrame(index) {
  return `https://your-cloudfront-url/frames/v1/frame_${(index + 1)
    .toString().padStart(3, "0")}.jpg`;
}

for (let i = 0; i < frameCount; i++) {
  const img = new Image();
  img.src = currentFrame(i);
  images.push(img);
}

function render() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(images[seq.frame], 0, 0, canvas.width, canvas.height);
}
images[0].onload = render;

gsap.to(seq, {
  frame: frameCount - 1,
  snap: "frame",
  ease: "none",
  scrollTrigger: {
    trigger: "#hero-section",
    start: "top top",
    end: "bottom bottom",
    scrub: 0.5,
    pin: true, // locks canvas in viewport while the "movie" plays
  },
  onUpdate: render,
});
```

### 9. Handle loading properly — this is what makes or breaks the illusion
- Show a **loading screen with progress %** until every frame is loaded
  — never let a user scroll into an unready sequence
- For long sequences, lazy-load in chunks: first ~30 frames unblock
  scroll, rest load in background
- `pin: true` is what creates the "movie" feel — canvas stays locked
  while scroll distance drives the frame index; page continues only
  once the sequence finishes

### 10. Deploy the site itself
Static build (Vite etc.) → two AWS options:
- **Amplify Hosting** — connect GitHub repo, auto build/deploy, HTTPS +
  CDN included. Fastest path.
- **S3 + CloudFront manually** — more setup, more control, demonstrates
  CDN/origin architecture if that matters for your context.
  ```bash
  aws s3 sync dist/ s3://your-bucket-name
  ```
  CloudFront distribution → origin = bucket (via OAC) → default root
  object `index.html`.

---

## Checklist before you start producing frames
- [ ] Story/shot list locked
- [ ] Production method chosen (3D / filmed / AE)
- [ ] Motion blur OFF at capture/render time
- [ ] Frame rate decided (start at 12fps)
- [ ] S3 bucket + CloudFront distribution created
- [ ] `.gitignore` updated to exclude frames folder
- [ ] Compression pipeline tested on a handful of frames first
- [ ] Loading screen built before wiring up the full sequence
