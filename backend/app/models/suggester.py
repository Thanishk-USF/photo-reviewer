"""Model-backed suggestion generator adapter."""

from __future__ import annotations

import os
from typing import Dict, List

_ZERO_SHOT_PIPELINE = None
_PIPELINE_INIT_FAILED = False
_LAST_BACKEND = "deterministic-adapter"

_ISSUE_LABELS = [
    "blurry image",
    "underexposed photo",
    "overexposed photo",
    "low contrast scene",
    "oversaturated colors",
    "dull colors",
    "noisy image",
    "cluttered composition",
    "subject not well framed",
]

_ISSUE_SUGGESTIONS = {
    "blurry image": "Use a faster shutter speed or stabilize the camera to improve sharpness.",
    "underexposed photo": "Raise exposure slightly or add controlled fill light to recover shadow detail.",
    "overexposed photo": "Reduce highlights and lower exposure compensation to preserve bright-area detail.",
    "low contrast scene": "Increase local contrast modestly to improve depth and subject separation.",
    "oversaturated colors": "Reduce vibrance slightly to restore natural color balance.",
    "dull colors": "Boost vibrance selectively to improve color separation without clipping.",
    "noisy image": "Lower ISO where possible and apply targeted noise reduction in darker regions.",
    "cluttered composition": "Simplify the frame by cropping distractions around the subject.",
    "subject not well framed": "Recompose using rule-of-thirds placement to strengthen focus.",
}


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


def _parse_device_index(device_value: str) -> int:
    value = (device_value or "cpu").strip().lower()
    if value in {"cpu", "-1"}:
        return -1
    if value.isdigit():
        return int(value)
    if value.startswith("cuda"):
        if ":" in value:
            _, _, suffix = value.partition(":")
            if suffix.isdigit():
                return int(suffix)
        return 0
    return -1


def _get_zero_shot_pipeline():
    global _ZERO_SHOT_PIPELINE, _PIPELINE_INIT_FAILED

    if _ZERO_SHOT_PIPELINE is not None:
        return _ZERO_SHOT_PIPELINE
    if _PIPELINE_INIT_FAILED:
        return None

    model_id = os.environ.get("PRETRAINED_SUGGESTER_MODEL_ID", os.environ.get("PRETRAINED_TAGGER_MODEL_ID", "openai/clip-vit-base-patch32"))
    device_name = os.environ.get("PRETRAINED_DEVICE", "cpu")

    try:
        from transformers import pipeline

        _ZERO_SHOT_PIPELINE = pipeline(
            "zero-shot-image-classification",
            model=model_id,
            device=_parse_device_index(device_name),
        )
    except Exception:
        _PIPELINE_INIT_FAILED = True
        _ZERO_SHOT_PIPELINE = None

    return _ZERO_SHOT_PIPELINE


def _fallback_suggestions(scores: Dict[str, float]) -> List[str]:
    suggestions: List[str] = []

    if float(scores.get("composition", 0.0)) < 6.0:
        suggestions.append("Try reframing with the subject near a rule-of-thirds intersection for stronger balance.")
    if float(scores.get("lighting", 0.0)) < 6.0:
        suggestions.append("Adjust exposure and highlight control to recover more tonal detail.")
    if float(scores.get("color", 0.0)) < 6.0:
        suggestions.append("Tune white balance and vibrance to improve color harmony.")
    if float(scores.get("technical", 0.0)) < 6.0:
        suggestions.append("Improve sharpness with steadier support and a faster capture speed.")

    if not suggestions:
        suggestions.append("Strong image overall. Minor local contrast adjustments can add extra depth.")
        suggestions.append("Consider a subtle crop to tighten focus on the primary subject.")

    return suggestions[:3]


def get_last_backend() -> str:
    return _LAST_BACKEND


def generate_suggestions(image, scores: Dict[str, float]) -> List[str]:
    """Return ranked improvement suggestions using pretrained vision model when available."""
    global _LAST_BACKEND

    classifier = _get_zero_shot_pipeline()
    if classifier is None:
        _LAST_BACKEND = "deterministic-adapter"
        return _fallback_suggestions(scores)

    threshold = max(0.05, min(_env_float("PRETRAINED_SUGGESTER_THRESHOLD", 0.20), 0.95))
    top_k = max(2, min(_env_int("PRETRAINED_SUGGESTER_TOP_K", 3), 5))

    try:
        predictions = classifier(image, candidate_labels=_ISSUE_LABELS)
    except Exception:
        _LAST_BACKEND = "deterministic-adapter"
        return _fallback_suggestions(scores)

    suggestions: List[str] = []
    seen = set()

    if isinstance(predictions, list):
        for entry in predictions[:top_k]:
            if not isinstance(entry, dict):
                continue
            label = str(entry.get("label", "")).strip().lower()
            try:
                score = float(entry.get("score", 0.0))
            except (TypeError, ValueError):
                continue

            if score < threshold:
                continue

            suggestion = _ISSUE_SUGGESTIONS.get(label)
            if not suggestion or suggestion in seen:
                continue

            seen.add(suggestion)
            suggestions.append(suggestion)

    if suggestions:
        _LAST_BACKEND = "pretrained"
        return suggestions[:3]

    _LAST_BACKEND = "deterministic-adapter"
    return _fallback_suggestions(scores)
