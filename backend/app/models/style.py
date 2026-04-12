"""
Style/mood classifier adapter.
"""

from __future__ import annotations

import os
import numpy as np

_ZERO_SHOT_PIPELINE = None
_PIPELINE_INIT_FAILED = False
_LAST_BACKEND = "deterministic-adapter"

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


def _fallback_classify(image):
    brightness, contrast, saturation, edge_strength = _extract_features(image)

    if saturation < 0.12:
        style = "Monochrome"
    elif edge_strength < 0.045 and contrast < 0.15:
        style = "Minimalist"
    elif saturation > 0.30 and contrast > 0.18:
        style = "Vibrant"
    elif contrast > 0.24:
        style = "HDR"
    else:
        style = "Natural"

    if brightness < 0.28 and contrast > 0.16:
        mood = "Dramatic"
    elif brightness < 0.30:
        mood = "Mysterious"
    elif brightness > 0.72 and saturation > 0.24:
        mood = "Joyful"
    elif contrast < 0.12:
        mood = "Calm"
    else:
        mood = "Serene"

    return style, mood


def _title_label(label):
    text = str(label).replace("_", " ").replace("-", " ").strip()
    return " ".join(part.capitalize() for part in text.split()) if text else ""


def get_last_backend() -> str:
    return _LAST_BACKEND


def _extract_features(image):
    if image.mode != "RGB":
        image = image.convert("RGB")

    rgb = np.asarray(image, dtype=np.float32) / 255.0
    r = rgb[:, :, 0]
    g = rgb[:, :, 1]
    b = rgb[:, :, 2]

    luma = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
    brightness = float(np.mean(luma))
    contrast = float(np.std(luma))

    max_channel = np.max(rgb, axis=2)
    min_channel = np.min(rgb, axis=2)
    saturation = np.where(max_channel > 1e-6, (max_channel - min_channel) / (max_channel + 1e-6), 0.0)
    saturation_mean = float(np.mean(saturation))

    grad_y, grad_x = np.gradient(luma)
    edge_strength = float(np.mean(np.sqrt((grad_x * grad_x) + (grad_y * grad_y))))

    return brightness, contrast, saturation_mean, edge_strength


def classify_style(image):
    """
    Classify style and mood with deterministic feature rules.

    This keeps output stable while the pretrained style model path is added.
    """
    global _LAST_BACKEND

    classifier = _get_zero_shot_pipeline()
    if classifier is None:
        _LAST_BACKEND = "deterministic-adapter"
        return _fallback_classify(image)

    try:
        style_preds = classifier(image, candidate_labels=_STYLE_LABELS)
        mood_preds = classifier(image, candidate_labels=_MOOD_LABELS)
    except Exception:
        _LAST_BACKEND = "deterministic-adapter"
        return _fallback_classify(image)

    if not isinstance(style_preds, list) or not style_preds or not isinstance(mood_preds, list) or not mood_preds:
        _LAST_BACKEND = "deterministic-adapter"
        return _fallback_classify(image)

    style_label = _title_label(style_preds[0].get("label", "")) if isinstance(style_preds[0], dict) else ""
    mood_label = _title_label(mood_preds[0].get("label", "")) if isinstance(mood_preds[0], dict) else ""

    if style_label and mood_label:
        _LAST_BACKEND = "pretrained"
        return style_label, mood_label

    _LAST_BACKEND = "deterministic-adapter"
    return _fallback_classify(image)
