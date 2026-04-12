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
- `PRETRAINED_SCORER_MODEL_ID`
- `PRETRAINED_TAGGER_MODEL_ID`
- `PRETRAINED_TAGGER_CAPTION_MODEL_ID`
- `PRETRAINED_STYLE_MODEL_ID`
- `PRETRAINED_SUGGESTER_MODEL_ID`

Optional tag precision guardrails (reduce false-positive tags):

- `PRETRAINED_TAGGER_CAPTION_AGREEMENT_MIN_SCORE=0.22`
- `PRETRAINED_TAGGER_SENSITIVE_MIN_SCORE=0.42`
- `PRETRAINED_TAGGER_MOON_UNGROUNDED_MIN_SCORE=0.62`

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

Tags are now model-derived. The API/frontend no longer force-inject a generic `photo` tag when model output is empty.

## Admin Debug Access

The adaptive debug panel is available at `/admin` and requires admin login.

Configure these environment variables:

- `ADMIN_DEBUG_PASSWORD` (required; used for admin login session)
- `ADMIN_DEBUG_KEY` (optional; if unset, backend falls back to `ADMIN_DEBUG_PASSWORD`)

Protected surfaces:

- Next.js admin session routes: `/api/admin/login`, `/api/admin/logout`, `/api/admin/profile`
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
