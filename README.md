# PhotoReviewer

A photo analysis application that provides aesthetic scoring, content tagging, style analysis, and hashtag generation for your photos.

## Features

- Upload and analyze photos
- Get aesthetic scores and technical analysis
- Identify content tags and style
- Generate optimized hashtags for social media
- View analysis history in the dashboard

## Tech Stack

- **Frontend**: Next.js, React, TypeScript, Tailwind CSS
- **Backend**: Flask, Python
- **Database**: MongoDB

## Project Structure

\`\`\`
photo-reviewer/
├── app/ # Next.js app directory
│ ├── api/ # API routes
│ ├── dashboard/ # Dashboard page
│ ├── results/ # Results page
│ ├── globals.css # Global styles
│ ├── layout.tsx # Root layout
│ └── page.tsx # Home page
├── components/ # React components
├── lib/ # Utility functions and API client
├── backend/ # Flask backend
│ ├── app/ # Flask application
│ │ ├── models/ # Deterministic + pretrained-capable model adapters
│ │ ├── utils/ # Utility functions
│ │ ├── **init**.py # App factory
│ │ └── routes.py # API routes
│ ├── uploads/ # Uploaded images
│ └── run.py # Entry point
├── public/ # Static assets
├── .env.local # Environment variables
└── package.json # Dependencies

## Pretrained Rollout Flags (Backend)

Backend now runs in pretrained-only mode by default. If you override flags in your environment, keep all of these enabled:

- `USE_PRETRAINED_SCORER=true`
- `USE_PRETRAINED_TAGGER=true`
- `USE_PRETRAINED_STYLE=true` (defaults to the tagger flag if unset)
- `USE_PRETRAINED_SUGGESTER=true`
- `MODEL_CANARY_PERCENT=100`
- `FALLBACK_ON_MODEL_ERROR=false`

Model IDs/devices are configurable via:

- `PRETRAINED_DEVICE` (`cpu`, `cuda`, or `cuda:0`)
- `PRETRAINED_DEVICE_MODE` (`auto`, `cuda`, `cpu`) — preferred modern switch
- `PRETRAINED_CUDA_INDEX` (default `0`)
- `PRETRAINED_SCORER_MODEL_ID`
- `PRETRAINED_TAGGER_MODEL_ID`
- `PRETRAINED_TAGGER_CAPTION_MODEL_ID`
- `PRETRAINED_STYLE_MODEL_ID`
- `PRETRAINED_SUGGESTER_MODEL_ID`

`PRETRAINED_DEVICE_MODE=auto` will try GPU first and automatically fall back to CPU if model initialization fails.

## Optional NIMA Aesthetic Blend

You can blend CLIP-based aesthetic scoring with a NIMA-style classifier:

- `USE_NIMA_AESTHETIC=false`
- `NIMA_MODEL_ID=` (required when enabling NIMA)
- `NIMA_AESTHETIC_BLEND_WEIGHT=0.65`
- `NIMA_MIN_CONFIDENCE=0.15`
- `NIMA_TOP_K=10`

When NIMA is unavailable or below confidence threshold, scoring automatically falls back to CLIP-only aesthetic.

Startup warmup controls:

- `PRETRAINED_WARMUP_ON_STARTUP=true`
- `PRETRAINED_WARMUP_RUN_INFERENCE=false`
- `PRETRAINED_WARMUP_FAIL_FAST=false`

Admin warmup trigger:

- `POST /api/admin/warmup` with admin auth header and optional JSON body `{ "runInference": true }`

Optional tag precision guardrails (reduce false-positive tags):

- `PRETRAINED_TAGGER_CAPTION_AGREEMENT_MIN_SCORE=0.22`
- `PRETRAINED_TAGGER_CAPTION_DIRECT_CONFIDENCE=0.30`
- `PRETRAINED_TAGGER_SENSITIVE_MIN_SCORE=0.42`
- `PRETRAINED_TAGGER_MOON_UNGROUNDED_MIN_SCORE=0.62`
- `PRETRAINED_TAGGER_FALLBACK_MIN_SCORE=0.10`
- `PRETRAINED_TAGGER_HARD_FALLBACK_MIN_SCORE=0.10`
- `PRETRAINED_TAGGER_ANCHOR_MIN_CONFIDENCE=0.22`

Optional object-model booster for tags:

- `PRETRAINED_TAGGER_USE_OBJECT_MODEL=true`
- `PRETRAINED_TAGGER_OBJECT_MODEL_ID=google/vit-base-patch16-224`
- `PRETRAINED_TAGGER_OBJECT_TOP_K=8`
- `PRETRAINED_TAGGER_OBJECT_MIN_SCORE=0.18`

Optional foreground/background split tagging (scene-aware):

- `PRETRAINED_TAGGER_USE_SEGMENT_SPLIT=true`
- `PRETRAINED_TAGGER_SEGMENT_MODEL_ID=nvidia/segformer-b0-finetuned-ade-512-512`
- `PRETRAINED_TAGGER_SEGMENT_MIN_SCORE=0.15`
- `PRETRAINED_TAGGER_SPLIT_FULL_WEIGHT=0.35`
- `PRETRAINED_TAGGER_SPLIT_FOREGROUND_WEIGHT=0.45`
- `PRETRAINED_TAGGER_SPLIT_BACKGROUND_WEIGHT=0.20`
- `PRETRAINED_TAGGER_SPLIT_MIN_FOREGROUND_COVERAGE=0.08`
- `PRETRAINED_TAGGER_SPLIT_MAX_FOREGROUND_COVERAGE=0.90`
- `PRETRAINED_TAGGER_BACKGROUND_SCENE_MIN_SCORE=0.18`

How it works:

1. A pretrained segmentation model estimates scene masks.
2. The image is split into foreground-focused and background-focused views.
3. Tag scores are computed separately for foreground/background and blended with full-image scores.
4. The final tags preserve both subject and scene context.

## Adaptive Learning From Your Data

The backend now learns from prior analysis records in MongoDB to improve relevance over time:

- Score calibration to reduce persistent outliers with your own score distribution
- Dynamic tag vocabulary expansion from your historical tags
- Retrieval-backed suggestion enrichment from your historical suggestions

Optional tuning knobs:

- `ADAPTIVE_PROFILE_ENABLED=true`
- `ADAPTIVE_PROFILE_MAX_DOCS=500`
- `ADAPTIVE_PROFILE_CACHE_TTL_SECONDS=300`
- `ADAPTIVE_MAX_DYNAMIC_TAG_LABELS=80`
- `ADAPTIVE_MAX_CANDIDATE_LABELS=160`
- `ADAPTIVE_MAX_SUGGESTION_POOL=240`
- `ADAPTIVE_SCORE_MIN_SAMPLES=40`
- `ADAPTIVE_SCORE_CALIBRATION_WEIGHT=0.15`
- `ADAPTIVE_TAG_PRIOR_WEIGHT=0.35`
- `ADAPTIVE_TAG_MIN_CONFIDENCE=0.35`
- `ADAPTIVE_TAG_SENSITIVE_MIN_CONFIDENCE=0.55`
- `ADAPTIVE_REQUIRE_TAG_CONFIDENCE=false`

The adaptive profile now filters low-confidence tags before building priors, with stricter handling for sensitive tags.

Tags are now model-derived. The API/frontend no longer force-inject a generic `photo` tag when model output is empty.

## Admin Debug Access

The adaptive debug panel is available at `/admin` and requires admin login.

Configure these environment variables:

- `ADMIN_DEBUG_PASSWORD` (required; used for admin login session)
- `ADMIN_DEBUG_KEY` (optional; if unset, backend falls back to `ADMIN_DEBUG_PASSWORD`)

Protected surfaces:

- Next.js admin session routes: `/api/admin/login`, `/api/admin/logout`, `/api/admin/profile`, `/api/admin/warmup`
- Flask debug endpoint: `/api/admin/adaptive-profile` (requires `X-Admin-Debug-Key`)

## Backfill Existing Mongo Records

Dry run:

```bash
python backend/scripts/backfill_analysis_fields.py --limit 20
```

Apply pretrained recompute with version label:

```bash
python backend/scripts/backfill_analysis_fields.py --apply --model-version pretrained-v2
```

If `--model-version` is omitted, the script stores the runtime-derived value (`pretrained-v2`).

## CPU/GPU Benchmark Script

Run single-mode benchmark:

```bash
python backend/scripts/benchmark_device_modes.py --single-mode --mode cpu --images backend/uploads/originals --limit 20 --iterations 1 --warmup
```

Compare CPU vs GPU-preferred auto mode with quality gates:

```bash
python backend/scripts/benchmark_device_modes.py --images backend/uploads/originals --modes cpu,auto --limit 20 --iterations 1 --warmup --max-p95-ms 5000 --max-empty-tag-rate 0.40 --max-failure-rate 0.05 --min-avg-suggestions 2.0
```
