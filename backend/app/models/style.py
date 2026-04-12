"""
Style/mood classifier adapter.
"""

from __future__ import annotations

import os

_ZERO_SHOT_PIPELINE = None
_PIPELINE_INIT_FAILED = False
_LAST_BACKEND = "pretrained-uninitialized"

_STYLE_LABELS = [
    "minimalist",
    "vibrant",
    "monochrome",
    "natural",
    "cinematic",
    "documentary",
    "portrait",
    "landscape",
]

_MOOD_LABELS = [
    "calm",
    "serene",
    "joyful",
    "dramatic",
    "mysterious",
    "moody",
    "energetic",
]


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

    model_id = os.environ.get("PRETRAINED_STYLE_MODEL_ID", os.environ.get("PRETRAINED_TAGGER_MODEL_ID", "openai/clip-vit-base-patch32"))
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


def _title_label(label):
    text = str(label).replace("_", " ").replace("-", " ").strip()
    return " ".join(part.capitalize() for part in text.split()) if text else ""


def get_last_backend() -> str:
    return _LAST_BACKEND


def classify_style(image):
    """Classify style/mood from pretrained zero-shot outputs only."""
    global _LAST_BACKEND

    classifier = _get_zero_shot_pipeline()
    if classifier is None:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained style pipeline could not be initialized")

    try:
        style_preds = classifier(image, candidate_labels=_STYLE_LABELS)
        mood_preds = classifier(image, candidate_labels=_MOOD_LABELS)
    except Exception as exc:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained style inference failed") from exc

    if not isinstance(style_preds, list) or not style_preds or not isinstance(mood_preds, list) or not mood_preds:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained style returned empty predictions")

    style_label = _title_label(style_preds[0].get("label", "")) if isinstance(style_preds[0], dict) else ""
    mood_label = _title_label(mood_preds[0].get("label", "")) if isinstance(mood_preds[0], dict) else ""

    if not style_label or not mood_label:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained style produced invalid label outputs")

    _LAST_BACKEND = "pretrained"
    return style_label, mood_label
