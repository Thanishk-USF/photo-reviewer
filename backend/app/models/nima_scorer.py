"""Optional NIMA-based aesthetic scorer.

This adapter expects an image-classification model that outputs rating buckets
(e.g. 1-10 labels). It is intentionally optional: if disabled or unavailable,
callers should fall back to CLIP-only aesthetic scoring.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List

from app.services.device_policy import build_transformers_pipeline

_PIPELINE = None
_PIPELINE_INIT_FAILED = False
_LAST_BACKEND = "nima-uninitialized"
_ACTIVE_DEVICE = "uninitialized"


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_score(value: float) -> float:
    numeric = float(value)
    if numeric < 1.0:
        numeric = 1.0
    elif numeric > 10.0:
        numeric = 10.0
    return round(numeric, 1)


def _label_to_bucket(label: str):
    text = str(label or "").strip().lower()
    if not text:
        return None

    # Accept common label formats: "7", "7/10", "rating_7", "score-7".
    match = re.search(r"(?<!\d)(10|[1-9])(?!\d)", text)
    if not match:
        return None

    try:
        value = int(match.group(1))
    except (TypeError, ValueError):
        return None

    if 1 <= value <= 10:
        return value
    return None


def _normalize_predictions(raw_predictions) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []

    if not isinstance(raw_predictions, list):
        return rows

    for item in raw_predictions:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        if not label:
            continue
        try:
            score = float(item.get("score", 0.0))
        except (TypeError, ValueError):
            continue
        if score <= 0.0:
            continue
        bucket = _label_to_bucket(label)
        if bucket is None:
            continue
        rows.append({"bucket": float(bucket), "score": float(score)})

    return rows


def _prediction_weighted_score(raw_predictions) -> float:
    rows = _normalize_predictions(raw_predictions)
    if not rows:
        raise RuntimeError("NIMA model did not return usable 1-10 rating labels")

    total = sum(row["score"] for row in rows)
    if total <= 0:
        raise RuntimeError("NIMA model returned zero confidence mass")

    normalized = []
    for row in rows:
        normalized.append({"bucket": row["bucket"], "weight": row["score"] / total})

    confidence = max(row["weight"] for row in normalized)
    min_conf = max(0.0, min(_env_float("NIMA_MIN_CONFIDENCE", 0.15), 1.0))
    if confidence < min_conf:
        raise RuntimeError("NIMA confidence below configured minimum")

    expected = sum(row["bucket"] * row["weight"] for row in normalized)
    return _clamp_score(expected)


def _get_pipeline():
    global _PIPELINE, _PIPELINE_INIT_FAILED, _ACTIVE_DEVICE

    if _PIPELINE is not None:
        return _PIPELINE
    if _PIPELINE_INIT_FAILED:
        return None

    if not _env_bool("USE_NIMA_AESTHETIC", False):
        _PIPELINE_INIT_FAILED = True
        return None

    model_id = str(os.environ.get("NIMA_MODEL_ID", "")).strip()
    if not model_id:
        _PIPELINE_INIT_FAILED = True
        return None

    try:
        _PIPELINE, _ACTIVE_DEVICE = build_transformers_pipeline(
            "image-classification",
            model_id,
        )
    except Exception:
        _PIPELINE_INIT_FAILED = True
        _PIPELINE = None

    return _PIPELINE


def get_last_backend() -> str:
    return _LAST_BACKEND


def get_active_device() -> str:
    return _ACTIVE_DEVICE


def warmup():
    if not _env_bool("USE_NIMA_AESTHETIC", False):
        return False
    if _get_pipeline() is None:
        raise RuntimeError("NIMA scorer pipeline could not be initialized")
    return True


def score_aesthetic(image) -> float:
    """Return a NIMA-style aesthetic score on a 1-10 scale."""
    global _LAST_BACKEND

    pipeline_instance = _get_pipeline()
    if pipeline_instance is None:
        _LAST_BACKEND = "nima-unavailable"
        raise RuntimeError("NIMA scorer is unavailable")

    top_k = max(5, min(_env_int("NIMA_TOP_K", 10), 20))

    try:
        predictions = pipeline_instance(image, top_k=top_k)
        score = _prediction_weighted_score(predictions)
    except Exception as exc:
        _LAST_BACKEND = "nima-error"
        raise RuntimeError("NIMA inference failed") from exc

    _LAST_BACKEND = "nima"
    return score
