"""Backfill analysis fields for existing photo records.

Recomputes score/style/mood/tags/hashtags/suggestions using the current
scoring and content-analysis logic.

Usage:
  python scripts/backfill_analysis_fields.py            # dry run
  python scripts/backfill_analysis_fields.py --apply    # apply updates
  python scripts/backfill_analysis_fields.py --limit 20
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import sys
from typing import Optional, Tuple

from PIL import Image
from pymongo import MongoClient

BACKEND_ROOT = os.path.dirname(os.path.dirname(__file__))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.services import scorer
from app.services.content_analyzer import build_analysis_metadata


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


def backfill_document(doc: dict, image_bytes: bytes) -> dict:
    with Image.open(io.BytesIO(image_bytes)) as image:
        quality = scorer.analyze_image_quality(image)
        score_map = quality["scores_1_10"]

        filename = doc.get("filename") or extract_filename_from_api_image_url(doc.get("imageUrl")) or "image.jpg"

        metadata = build_analysis_metadata(
            image,
            filename,
            score_map["aesthetic"],
            score_map["technical"],
            score_map["composition"],
            score_map["lighting"],
            score_map["color"],
            quality=quality,
        )

    return {
        "filename": filename,
        "aestheticScore": round(score_map["aesthetic"], 1),
        "technicalScore": round(score_map["technical"], 1),
        "composition": round(score_map["composition"], 1),
        "lighting": round(score_map["lighting"], 1),
        "color": round(score_map["color"], 1),
        "style": metadata["style"],
        "mood": metadata["mood"],
        "tags": metadata["tags"],
        "hashtags": metadata["hashtags"],
        "suggestions": metadata["suggestions"],
        "image_hash": hashlib.sha256(image_bytes).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill analysis fields in MongoDB photo documents.")
    parser.add_argument("--apply", action="store_true", help="Write updates to MongoDB.")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N documents (0 = all).")
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

    print(f"mongo_uri={mongo_uri}")
    print(f"db_name={mongo_db_name}")
    print(f"upload_root={upload_root}")
    print(f"mode={'apply' if args.apply else 'dry-run'}")

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
            payload = backfill_document(doc, image_bytes)
        except Exception as exc:
            failed += 1
            print(f"fail _id={doc_id} source={source} error={exc}")
            continue

        if args.apply:
            photos.update_one({"_id": doc["_id"]}, {"$set": payload})
            updated += 1
            print(f"updated _id={doc_id} source={source}")
        else:
            updated += 1
            print(f"would-update _id={doc_id} source={source}")

    print("\nsummary")
    print(f"processed={processed}")
    print(f"updated={updated}")
    print(f"skipped={skipped}")
    print(f"failed={failed}")


if __name__ == "__main__":
    main()
