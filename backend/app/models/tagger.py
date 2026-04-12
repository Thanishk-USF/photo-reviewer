"""
Model-backed tag generator adapter.
"""

from __future__ import annotations

import os
from typing import List

import numpy as np

_ZERO_SHOT_PIPELINE = None
_PIPELINE_INIT_FAILED = False
_LAST_BACKEND = "deterministic-adapter"

_DEFAULT_CANDIDATE_LABELS = [
    "landscape",
    "portrait",
    "architecture",
    "street photography",
    "nature",
    "wildlife",
    "night scene",
    "sunset",
    "sunrise",
    "city skyline",
    "minimalist composition",
    "high contrast",
    "low light",
    "macro photography",
    "food photography",
    "travel photography",
    "monochrome",
    "vibrant colors",
    "warm tones",
    "cool tones",
]


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


def _normalize_label(label: str) -> str:
    label = label.strip().lower()
    if not label:
        return ""
    return "-".join(part for part in label.replace("_", " ").split() if part)


def _get_zero_shot_pipeline():
    global _ZERO_SHOT_PIPELINE, _PIPELINE_INIT_FAILED

    if _ZERO_SHOT_PIPELINE is not None:
        return _ZERO_SHOT_PIPELINE
    if _PIPELINE_INIT_FAILED:
        return None

    model_id = os.environ.get("PRETRAINED_TAGGER_MODEL_ID", "openai/clip-vit-base-patch32")
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


def _image_features(image):
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

    height, width = luma.shape
    aspect_ratio = float(width) / max(float(height), 1.0)

    channel_means = np.array([float(np.mean(r)), float(np.mean(g)), float(np.mean(b))], dtype=np.float32)
    dominant_channel = int(np.argmax(channel_means))

    return brightness, contrast, saturation_mean, aspect_ratio, dominant_channel


def _dedupe(values: List[str]) -> List[str]:
    out = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _fallback_tags(image) -> List[str]:
    brightness, contrast, saturation, aspect_ratio, dominant_channel = _image_features(image)

    tags: List[str] = ["photo"]

    if aspect_ratio > 1.25:
        tags.append("landscape")
    elif aspect_ratio < 0.80:
        tags.append("portrait")

    if brightness < 0.30:
        tags.extend(["dark", "low-light"])
    elif brightness > 0.72:
        tags.extend(["bright", "high-key"])

    if saturation < 0.12:
        tags.append("monochrome")
    elif saturation > 0.33:
        tags.extend(["colorful", "vivid"])

    if contrast > 0.22:
        tags.append("high-contrast")
    elif contrast < 0.11:
        tags.append("soft-contrast")

    if dominant_channel == 0:
        tags.append("warm-tones")
    elif dominant_channel == 2:
        tags.append("cool-tones")
    else:
        tags.append("balanced-tones")

    return _dedupe(tags)[:10]


def get_last_backend() -> str:
    return _LAST_BACKEND


def generate_tags(image):
    """
    Generate stable tags from image features.

    This adapter intentionally avoids random output so runtime behavior is
    deterministic before heavy pretrained dependencies are introduced.
    """
    global _LAST_BACKEND

    classifier = _get_zero_shot_pipeline()
    if classifier is None:
        _LAST_BACKEND = "deterministic-adapter"
        return _fallback_tags(image)

    top_k = max(3, min(_env_int("PRETRAINED_TAGGER_TOP_K", 8), 12))
    threshold = max(0.05, min(_env_float("PRETRAINED_TAGGER_THRESHOLD", 0.18), 0.95))

    try:
        results = classifier(image, candidate_labels=_DEFAULT_CANDIDATE_LABELS)
    except Exception:
        _LAST_BACKEND = "deterministic-adapter"
        return _fallback_tags(image)

    if not isinstance(results, list) or not results:
        _LAST_BACKEND = "deterministic-adapter"
        return _fallback_tags(image)

    tags: List[str] = ["photo"]
    for item in results[:top_k]:
        if not isinstance(item, dict):
            continue
        try:
            score = float(item.get("score", 0.0))
        except (TypeError, ValueError):
            continue
        if score < threshold:
            continue
        label = _normalize_label(str(item.get("label", "")))
        if label:
            tags.append(label)

    tags = _dedupe(tags)
    if len(tags) > 1:
        _LAST_BACKEND = "pretrained"
        return tags[:10]

    _LAST_BACKEND = "deterministic-adapter"
    return _fallback_tags(image)
