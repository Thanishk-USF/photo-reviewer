"""Model-backed suggestion generator adapter."""

from __future__ import annotations

import os
from typing import Dict, List

_ZERO_SHOT_PIPELINE = None
_PIPELINE_INIT_FAILED = False
_LAST_BACKEND = "pretrained-uninitialized"

_ISSUE_LABELS = [
    "out of focus subject",
    "motion blur",
    "digital noise",
    "underexposed scene",
    "overexposed highlights",
    "low contrast scene",
    "flat lighting",
    "color cast issue",
    "oversaturated colors",
    "desaturated colors",
    "cluttered background",
    "weak subject separation",
    "crooked horizon",
    "strong composition",
    "balanced exposure",
    "natural colors",
    "good sharpness",
]

_ISSUE_SUGGESTIONS = {
    "out of focus subject": "Refocus on the primary subject and use a faster shutter speed to improve clarity.",
    "motion blur": "Increase shutter speed or stabilize the camera to reduce motion blur.",
    "digital noise": "Lower ISO where possible and apply targeted noise reduction in darker regions.",
    "underexposed scene": "Raise exposure slightly or add controlled fill light to recover shadow detail.",
    "overexposed highlights": "Reduce highlights and exposure compensation to preserve bright-area detail.",
    "low contrast scene": "Increase local contrast to improve depth and subject separation.",
    "flat lighting": "Introduce directional lighting or local dodge/burn to add dimensionality.",
    "color cast issue": "Adjust white balance and tint to neutralize the color cast.",
    "oversaturated colors": "Reduce vibrance and saturation slightly to restore natural color balance.",
    "desaturated colors": "Increase vibrance modestly to improve color separation without clipping.",
    "cluttered background": "Simplify the frame by cropping distractions around the subject.",
    "weak subject separation": "Create clearer subject isolation with contrast and depth separation.",
    "crooked horizon": "Straighten the horizon to stabilize visual balance.",
    "strong composition": "Composition is strong; refine micro-contrast and local detail for a final polish.",
    "balanced exposure": "Exposure is well balanced; fine-tune highlights and shadows for texture depth.",
    "natural colors": "Colors are natural; subtle selective grading can enhance mood while staying realistic.",
    "good sharpness": "Sharpness is good; avoid over-sharpening and preserve fine texture detail.",
}

_NEGATIVE_ISSUES = {
    "out of focus subject",
    "motion blur",
    "digital noise",
    "underexposed scene",
    "overexposed highlights",
    "low contrast scene",
    "flat lighting",
    "color cast issue",
    "oversaturated colors",
    "desaturated colors",
    "cluttered background",
    "weak subject separation",
    "crooked horizon",
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


def get_last_backend() -> str:
    return _LAST_BACKEND


def generate_suggestions(image, scores: Dict[str, float]) -> List[str]:
    """Return ranked improvement suggestions using pretrained vision model when available."""
    global _LAST_BACKEND

    classifier = _get_zero_shot_pipeline()
    if classifier is None:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained suggester pipeline could not be initialized")

    threshold = max(0.05, min(_env_float("PRETRAINED_SUGGESTER_THRESHOLD", 0.20), 0.95))
    top_k = max(2, min(_env_int("PRETRAINED_SUGGESTER_TOP_K", 3), 5))

    try:
        predictions = classifier(image, candidate_labels=_ISSUE_LABELS)
    except Exception as exc:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained suggester inference failed") from exc

    suggestions: List[str] = []
    seen = set()
    fallback_labels: List[str] = []
    top_label = ""
    top_score = 0.0

    if isinstance(predictions, list):
        for entry in predictions[:top_k]:
            if not isinstance(entry, dict):
                continue
            label = str(entry.get("label", "")).strip().lower()
            try:
                score = float(entry.get("score", 0.0))
            except (TypeError, ValueError):
                continue

            if label:
                fallback_labels.append(label)
                if score > top_score:
                    top_score = score
                    top_label = label

            if score < threshold:
                continue

            if label not in _NEGATIVE_ISSUES:
                continue

            suggestion = _ISSUE_SUGGESTIONS.get(label)
            if not suggestion or suggestion in seen:
                continue

            seen.add(suggestion)
            suggestions.append(suggestion)

    if not suggestions:
        ordered_labels = [top_label] + fallback_labels if top_label else list(fallback_labels)
        for label in ordered_labels:
            suggestion = _ISSUE_SUGGESTIONS.get(label)
            if not suggestion or suggestion in seen:
                continue
            seen.add(suggestion)
            suggestions.append(suggestion)
            if len(suggestions) >= 3:
                break

    if not suggestions:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained suggester produced no usable suggestions")

    _LAST_BACKEND = "pretrained"
    return suggestions[:3]
