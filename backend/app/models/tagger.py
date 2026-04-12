"""
Model-backed tag generator adapter.
"""

from __future__ import annotations

import os
import re
from typing import List

_ZERO_SHOT_PIPELINE = None
_CAPTION_PIPELINE = None
_PIPELINE_INIT_FAILED = False
_CAPTION_INIT_FAILED = False
_LAST_BACKEND = "pretrained-uninitialized"

_DEFAULT_CANDIDATE_LABELS = [
    "photo",
    "landscape",
    "portrait",
    "night sky",
    "moon",
    "astronomy",
    "space scene",
    "architecture",
    "street photography",
    "nature",
    "wildlife",
    "night scene",
    "sunset",
    "sunrise",
    "ocean",
    "water reflection",
    "mountain",
    "forest",
    "city skyline",
    "minimalist composition",
    "high contrast",
    "low light",
    "dramatic lighting",
    "soft lighting",
    "macro photography",
    "food photography",
    "travel photography",
    "monochrome",
    "vibrant colors",
    "warm tones",
    "cool tones",
    "digital art",
    "anime illustration",
    "fantasy illustration",
    "character art",
    "cinematic scene",
    "cloudscape",
    "seascape",
]

_CAPTION_PHRASE_TAGS = {
    "night sky": "night-sky",
    "city skyline": "city-skyline",
    "digital art": "digital-art",
    "anime": "anime",
    "illustration": "illustration",
    "fantasy": "fantasy",
    "character": "character",
    "moon": "moon",
    "astronomy": "astronomy",
    "space": "space",
    "sunrise": "sunrise",
    "sunset": "sunset",
    "ocean": "ocean",
    "water": "water",
    "mountain": "mountain",
    "forest": "forest",
    "portrait": "portrait",
    "landscape": "landscape",
    "monochrome": "monochrome",
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


def _get_caption_pipeline():
    global _CAPTION_PIPELINE, _CAPTION_INIT_FAILED

    if _CAPTION_PIPELINE is not None:
        return _CAPTION_PIPELINE
    if _CAPTION_INIT_FAILED:
        return None

    model_id = os.environ.get("PRETRAINED_TAGGER_CAPTION_MODEL_ID", "Salesforce/blip-image-captioning-base")
    device_name = os.environ.get("PRETRAINED_DEVICE", "cpu")

    try:
        from transformers import pipeline

        _CAPTION_PIPELINE = pipeline(
            "image-to-text",
            model=model_id,
            device=_parse_device_index(device_name),
        )
    except Exception:
        _CAPTION_INIT_FAILED = True
        _CAPTION_PIPELINE = None

    return _CAPTION_PIPELINE


def _dedupe(values: List[str]) -> List[str]:
    out = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _extract_caption_text(captioner, image) -> str:
    max_tokens = max(12, min(_env_int("PRETRAINED_TAGGER_CAPTION_MAX_TOKENS", 40), 80))
    output = captioner(image, max_new_tokens=max_tokens)

    if isinstance(output, list) and output and isinstance(output[0], dict):
        text = str(output[0].get("generated_text", "")).strip().lower()
        if text:
            return text

    raise RuntimeError("Pretrained caption model returned no caption text")


def _caption_tags(caption_text: str) -> List[str]:
    text = re.sub(r"\s+", " ", caption_text.strip().lower())
    tags: List[str] = []

    for phrase, tag in _CAPTION_PHRASE_TAGS.items():
        if phrase in text:
            tags.append(tag)

    return _dedupe([_normalize_label(tag) for tag in tags if _normalize_label(tag)])


def get_last_backend() -> str:
    return _LAST_BACKEND


def generate_tags(image):
    """Generate tags from pretrained zero-shot classification outputs only."""
    global _LAST_BACKEND

    classifier = _get_zero_shot_pipeline()
    if classifier is None:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained tagger pipeline could not be initialized")

    captioner = _get_caption_pipeline()
    if captioner is None:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained caption pipeline could not be initialized")

    top_k = max(3, min(_env_int("PRETRAINED_TAGGER_TOP_K", 8), 12))
    threshold = max(0.05, min(_env_float("PRETRAINED_TAGGER_THRESHOLD", 0.18), 0.95))

    try:
        results = classifier(image, candidate_labels=_DEFAULT_CANDIDATE_LABELS)
    except Exception as exc:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained tagger inference failed") from exc

    if not isinstance(results, list) or not results:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained tagger returned empty predictions")

    caption_text = _extract_caption_text(captioner, image)
    caption_semantics = _caption_tags(caption_text)

    tags: List[str] = ["photo"]
    filtered_labels: List[str] = []
    fallback_labels: List[str] = []
    for item in results[:top_k]:
        if not isinstance(item, dict):
            continue
        try:
            score = float(item.get("score", 0.0))
        except (TypeError, ValueError):
            continue
        label = _normalize_label(str(item.get("label", "")))
        if not label:
            continue
        fallback_labels.append(label)
        if score >= threshold:
            filtered_labels.append(label)

    selected = filtered_labels or fallback_labels
    tags.extend(caption_semantics)
    tags.extend(selected)

    tags = _dedupe(tags)
    if len(tags) <= 1:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained tagger produced no usable tags")

    _LAST_BACKEND = "pretrained"
    return tags[:10]
