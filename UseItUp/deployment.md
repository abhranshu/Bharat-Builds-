# AWS Deployment Guide — UseItUp

This guide covers deploying the UseItUp landing page to AWS. The site is a static Vite build (HTML/CSS/JS). Frames are already hosted on CloudFront.

---

## Prerequisites

- AWS CLI installed and configured (`aws configure`)
- Node.js 18+ installed
- Git repository on GitHub (or similar)

---

## Option A: AWS Amplify Hosting (Recommended)

Fastest path. Auto-builds from GitHub, serves over HTTPS + CloudFront CDN.

### Step 1 — Push to GitHub

```bash
cd UseItUp
git init
git add .
git commit -m "Initial commit"
gh repo create useitup-landing --public --source=. --remote=origin --push
```

### Step 2 — Connect to Amplify

1. Open the [AWS Amplify Console](https://console.aws.amazon.com/amplify/)
2. Click **New app → Host web app**
3. Select **GitHub** as the source
4. Authorize AWS Amplify to access your GitHub account
5. Select the `useitup-landing` repository
6. Select the `main` branch

### Step 3 — Build Settings

Amplify auto-detects Vite. Verify these settings:

- **Build command:** `npm run build`
- **Output directory:** `dist`
- **Node version:** 18 (set in build settings if needed)

```yaml
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - npm ci
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: dist
    files:
      - '**/*'
  cache:
    paths:
      - node_modules/**/*
```

### Step 4 — Deploy

Click **Save and deploy**. Amplify builds and deploys automatically.

On success you get a URL like:
```
https://main.d1234abcd5678.amplifyapp.com
```

### Step 5 — Custom Domain (Optional)

1. In Amplify Console → your app → **Domain management**
2. Add your domain (e.g. `useitup.app`)
3. Amplify provisions an SSL certificate automatically
4. Update DNS records at your registrar to point to Amplify

---

## Option B: S3 + CloudFront (Manual)

More control. Good for understanding the CDN/origin architecture.

### Step 1 — Build Locally

```bash
cd UseItUp
npm ci
npm run build
```

Output is in `dist/`.

### Step 2 — Create an S3 Bucket

```bash
# Create bucket (use a globally unique name)
aws s3 mb s3://useitup-landing --region us-east-1

# Enable versioning (optional, recommended)
aws s3api put-bucket-versioning \
  --bucket useitup-landing \
  --versioning-configuration Status=Enabled
```

### Step 3 — Upload the Build

```bash
aws s3 sync dist/ s3://useitup-landing \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "index.html" \
  --exclude "*.html"

# Upload index.html separately with no-cache (so updates deploy instantly)
aws s3 cp dist/index.html s3://useitup-landing/index.html \
  --cache-control "no-cache, no-store, must-revalidate" \
  --content-type "text/html"
```

### Step 4 — Block Public Access

```bash
aws s3api put-public-access-block \
  --bucket useitup-landing \
  --public-access-block-configuration \
    BlockPublicAcls=true,\
    IgnorePublicAcls=true,\
    BlockPublicPolicy=true,\
    RestrictPublicBuckets=true
```

### Step 5 — Create a CloudFront Distribution

1. Open [CloudFront Console](https://console.aws.amazon.com/cloudfront/)
2. Click **Create distribution**
3. **Origin domain:** select your S3 bucket (`useitup-landing.s3.amazonaws.com`)
4. **Origin access:** Origin access control settings (OAC)
   - Click **Create control setting** → use defaults → create
5. **Default cache behavior:**
   - Viewer protocol policy: Redirect HTTP to HTTPS
   - Allowed HTTP methods: GET, HEAD
   - Cache policy: CachingOptimized (managed)
6. **Settings:**
   - Alternate domain name (CNAME): add your domain if needed
   - Custom SSL certificate: use ACM certificate for your domain
7. Click **Create distribution**

### Step 6 — Update S3 Bucket Policy

When CloudFront creates the OAC, it gives you a bucket policy. Add it:

```bash
aws s3api put-bucket-policy \
  --bucket useitup-landing \
  --policy '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "AllowCloudFrontServicePrincipal",
        "Effect": "Allow",
        "Principal": {
          "Service": "cloudfront.amazonaws.com"
        },
        "Action": "s3:GetObject",
        "Resource": "arn:aws:s3:::useitup-landing/*",
        "Condition": {
          "StringEquals": {
            "AWS:SourceArn": "arn:aws:cloudfront::ACCOUNT_ID:distribution/DISTRIBUTION_ID"
          }
        }
      }
    ]
  }'
```

Replace `ACCOUNT_ID` and `DISTRIBUTION_ID` with your values.

### Step 7 — Set Default Root Object

In the CloudFront distribution settings:
- **Default root object:** `index.html`

### Step 8 — Invalidate Cache on Deploy

After each deployment:

```bash
aws cloudfront create-invalidation \
  --distribution-id DISTRIBUTION_ID \
  --paths "/index.html" "/assets/*"
```

### Step 9 — Custom Domain (Optional)

1. Request an ACM certificate in `us-east-1` (required for CloudFront)
2. Add CNAME records to your DNS
3. Add the domain as an Alternate Domain Name (CNAME) in CloudFront
4. Update the ACM certificate ARN in the distribution settings

---

## Deployment Checklist

- [ ] Frames are already on CloudFront at `d21m7w28iod98m.cloudfront.net/frames/v1`
- [ ] `.gitignore` excludes `node_modules/`, `dist/`, `public/frames/`
- [ ] `npm run build` completes without errors
- [ ] No `frame_XXX.jpg` references — using `c1/c2/c3a/c3b` naming
- [ ] No cache-busting query parameters on frame URLs
- [ ] SSL/HTTPS enabled (Amplify does this automatically, CloudFront needs ACM cert)
- [ ] Custom domain configured (if applicable)
- [ ] Test the deployed URL — frames load, scroll works, CTA appears at 95%

---

## Post-Deploy Verification

Open the deployed URL and check:

1. Loading screen shows progress 0% → 100%
2. Scroll scrubs through all 192 frames smoothly
3. Text overlay fades in/out at the correct scroll percentages
4. CTA "Scan Your Fridge" appears near the end
5. Clicking CTA scrolls to the app-entry section
6. Frames load from CloudFront (check Network tab — requests go to `d21m7w28iod98m.cloudfront.net`)
7. No CORS errors in the console
8. Responsive on mobile viewport

---

## Updating the Deployment

### Amplify
Just push to GitHub. Amplify auto-builds and redeploys.

### S3 + CloudFront
```bash
npm run build
aws s3 sync dist/ s3://useitup-landing --delete
aws s3 cp dist/index.html s3://useitup-landing/index.html \
  --cache-control "no-cache, no-store, must-revalidate"
aws cloudfront create-invalidation \
  --distribution-id DISTRIBUTION_ID \
  --paths "/index.html" "/assets/*"
```

---

## Cost Estimate

| Service | Free Tier | Estimate |
|---|---|---|
| **Amplify Hosting** | 5 GB storage, 15 GB/month bandwidth | ~$0 for small sites |
| **S3** | 5 GB storage, 20K GET requests | ~$0.05/month |
| **CloudFront** | 1 TB/month transfer, 10M requests | ~$0 for small sites |
| **ACM Certificate** | Free with CloudFront | $0 |

For a landing page with low traffic, Amplify is essentially free.
