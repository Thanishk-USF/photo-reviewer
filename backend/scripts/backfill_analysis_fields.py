"""Backfill analysis fields for existing photo records.

Recomputes score/style/mood/tags/hashtags/suggestions using the current
scoring and content-analysis logic.

Usage:
  python scripts/backfill_analysis_fields.py            # dry run
  python scripts/backfill_analysis_fields.py --apply    # apply updates
  python scripts/backfill_analysis_fields.py --limit 20
    python scripts/backfill_analysis_fields.py --use-pretrained-scorer --use-pretrained-tagger --use-pretrained-style --use-pretrained-suggester --model-version pretrained-v1
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import sys
from datetime import datetime
from typing import Dict, Optional, Tuple

from PIL import Image
from pymongo import MongoClient

BACKEND_ROOT = os.path.dirname(os.path.dirname(__file__))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.models.runtime import analyze_image_runtime
from app.services.analysis_contract import normalize_analysis_result


def extract_filename_from_api_image_url(url_value: Optional[str]) -> Optional[str]:
    if not isinstance(url_value, str):
        return None
    if not url_value.startswith("/api/images/"):
        return None
    return url_value.split("/")[-1]


def resolve_existing_file(upload_root: str, filename: Optional[str]) -> Optional[str]:
    if not filename:
        return None

    candidates = [
        os.path.join(upload_root, "originals", filename),
        os.path.join(upload_root, "thumbnails", filename),
        os.path.join(upload_root, filename),
    ]

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    return None


def load_image_bytes(doc: dict, upload_root: str) -> Tuple[Optional[bytes], str]:
    if isinstance(doc.get("image_binary"), (bytes, bytearray)):
        return bytes(doc["image_binary"]), "mongo:image_binary"

    image_filename = extract_filename_from_api_image_url(doc.get("imageUrl"))
    file_path = resolve_existing_file(upload_root, image_filename)
    if file_path:
        with open(file_path, "rb") as image_file:
            return image_file.read(), f"disk:{file_path}"

    thumb_filename = extract_filename_from_api_image_url(doc.get("thumbnailUrl"))
    file_path = resolve_existing_file(upload_root, thumb_filename)
    if file_path:
        with open(file_path, "rb") as image_file:
            return image_file.read(), f"disk:{file_path}"

    return None, "missing"


def _legacy_analysis_snapshot(doc: dict) -> Dict[str, object]:
    return {
        "aestheticScore": doc.get("aestheticScore"),
        "technicalScore": doc.get("technicalScore"),
        "composition": doc.get("composition"),
        "lighting": doc.get("lighting"),
        "color": doc.get("color"),
        "style": doc.get("style"),
        "mood": doc.get("mood"),
        "tags": doc.get("tags"),
        "hashtags": doc.get("hashtags"),
        "suggestions": doc.get("suggestions"),
    }


def backfill_document(doc: dict, image_bytes: bytes, model_version: Optional[str], runtime_config: Dict[str, object]) -> dict:
    with Image.open(io.BytesIO(image_bytes)) as image:
        filename = doc.get("filename") or extract_filename_from_api_image_url(doc.get("imageUrl")) or "image.jpg"
        image_url = doc.get("imageUrl") if isinstance(doc.get("imageUrl"), str) else f"/api/images/{filename}"
        thumbnail_url = doc.get("thumbnailUrl") if isinstance(doc.get("thumbnailUrl"), str) else image_url

        runtime_output = analyze_image_runtime(
            image,
            filename,
            runtime_config,
        )
        runtime_meta = runtime_output.pop("_runtime", {})

        normalized = normalize_analysis_result(
            {
                "success": True,
                "id": str(doc.get("_id", "")),
                "imageUrl": image_url,
                "thumbnailUrl": thumbnail_url,
                "filename": filename,
                "uploadDate": doc.get("uploadDate") or datetime.utcnow().isoformat(),
                **runtime_output,
            }
        )

    return {
        "filename": filename,
        "aestheticScore": normalized["aestheticScore"],
        "technicalScore": normalized["technicalScore"],
        "composition": normalized["composition"],
        "lighting": normalized["lighting"],
        "color": normalized["color"],
        "style": normalized["style"],
        "mood": normalized["mood"],
        "tags": normalized["tags"],
        "hashtags": normalized["hashtags"],
        "suggestions": normalized["suggestions"],
        "image_hash": hashlib.sha256(image_bytes).hexdigest(),
        "model_version": (str(model_version).strip() if model_version is not None else "") or str(runtime_meta.get("model_version", "deterministic-v1")),
        "score_source": str(runtime_meta.get("scorer_source", "deterministic")),
        "tagger_source": str(runtime_meta.get("tagger_source", "deterministic")),
        "style_source": str(runtime_meta.get("style_source", "deterministic")),
        "suggestion_source": str(runtime_meta.get("suggestion_source", "deterministic")),
        "fallback_used": bool(runtime_meta.get("fallback_used", False)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill analysis fields in MongoDB photo documents.")
    parser.add_argument("--apply", action="store_true", help="Write updates to MongoDB.")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N documents (0 = all).")
    parser.add_argument("--model-version", type=str, default="", help="Optional model version override. If omitted, runtime-derived model_version is used.")
    parser.add_argument("--use-pretrained-scorer", action="store_true", help="Enable pretrained scorer path for backfill runs.")
    parser.add_argument("--use-pretrained-tagger", action="store_true", help="Enable pretrained tagger/style path for backfill runs.")
    parser.add_argument("--use-pretrained-style", action="store_true", help="Enable pretrained style path for backfill runs.")
    parser.add_argument("--use-pretrained-suggester", action="store_true", help="Enable pretrained suggestion path for backfill runs.")
    args = parser.parse_args()

    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
    mongo_db_name = os.environ.get("MONGO_DB_NAME", "photo_reviewer")
    upload_root = os.environ.get("UPLOAD_FOLDER", os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads"))

    client = MongoClient(mongo_uri)
    photos = client[mongo_db_name]["photos"]

    cursor = photos.find().sort("_id", -1)
    processed = 0
    updated = 0
    skipped = 0
    failed = 0
    fallback_used_count = 0
    pretrained_count = 0

    runtime_config: Dict[str, object] = {
        "USE_PRETRAINED_SCORER": bool(args.use_pretrained_scorer),
        "USE_PRETRAINED_TAGGER": bool(args.use_pretrained_tagger),
        "USE_PRETRAINED_STYLE": bool(args.use_pretrained_style or args.use_pretrained_tagger),
        "USE_PRETRAINED_SUGGESTER": bool(args.use_pretrained_suggester),
        "FALLBACK_ON_MODEL_ERROR": True,
        "MODEL_CANARY_PERCENT": 100.0,
        "PRETRAINED_SCORE_BLEND_ALPHA": float(os.environ.get("PRETRAINED_SCORE_BLEND_ALPHA", "0.7")),
    }

    print(f"mongo_uri={mongo_uri}")
    print(f"db_name={mongo_db_name}")
    print(f"upload_root={upload_root}")
    print(f"mode={'apply' if args.apply else 'dry-run'}")
    print(f"model_version={args.model_version or '<runtime>'}")
    print(
        "runtime_flags="
        f"scorer:{runtime_config['USE_PRETRAINED_SCORER']} "
        f"tagger:{runtime_config['USE_PRETRAINED_TAGGER']} "
        f"style:{runtime_config['USE_PRETRAINED_STYLE']} "
        f"suggester:{runtime_config['USE_PRETRAINED_SUGGESTER']}"
    )

    for doc in cursor:
        if args.limit and processed >= args.limit:
            break

        processed += 1
        image_bytes, source = load_image_bytes(doc, upload_root)
        doc_id = str(doc.get("_id"))

        if not image_bytes:
            skipped += 1
            print(f"skip _id={doc_id} reason=no-image-source")
            continue

        try:
            payload = backfill_document(doc, image_bytes, args.model_version, runtime_config)
        except Exception as exc:
            failed += 1
            print(f"fail _id={doc_id} source={source} error={exc}")
            continue

        if payload.get("fallback_used"):
            fallback_used_count += 1
        if (
            str(payload.get("score_source")) == "pretrained"
            or str(payload.get("tagger_source")) == "pretrained"
            or str(payload.get("style_source")) == "pretrained"
            or str(payload.get("suggestion_source")) == "pretrained"
        ):
            pretrained_count += 1

        if args.apply:
            update_payload = dict(payload)
            if "legacy_analysis" not in doc:
                update_payload["legacy_analysis"] = _legacy_analysis_snapshot(doc)
            photos.update_one({"_id": doc["_id"]}, {"$set": update_payload})
            updated += 1
            print(
                f"updated _id={doc_id} source={source} "
                f"score_source={payload.get('score_source')} "
                f"tagger_source={payload.get('tagger_source')} "
                f"style_source={payload.get('style_source')} "
                f"suggestion_source={payload.get('suggestion_source')} "
                f"fallback={payload.get('fallback_used')}"
            )
        else:
            updated += 1
            print(
                f"would-update _id={doc_id} source={source} "
                f"score_source={payload.get('score_source')} "
                f"tagger_source={payload.get('tagger_source')} "
                f"style_source={payload.get('style_source')} "
                f"suggestion_source={payload.get('suggestion_source')} "
                f"fallback={payload.get('fallback_used')}"
            )

    print("\nsummary")
    print(f"processed={processed}")
    print(f"updated={updated}")
    print(f"skipped={skipped}")
    print(f"failed={failed}")
    print(f"pretrained_results={pretrained_count}")
    print(f"fallback_used={fallback_used_count}")


if __name__ == "__main__":
    main()
