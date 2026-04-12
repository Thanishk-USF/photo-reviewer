"""
Model-backed aesthetic scoring adapter.
"""

from __future__ import annotations

import math
import os
from typing import Dict, List, Sequence, Tuple

_CLASSIFIER_PIPELINE = None
_PIPELINE_INIT_FAILED = False
_LAST_BACKEND = "pretrained-uninitialized"

_PROMPT_ENSEMBLE: Dict[str, Dict[str, Sequence[str]]] = {
    "aesthetic": {
        "positive": (
            "stunning professional photo",
            "visually pleasing high quality image",
            "beautifully composed image",
        ),
        "negative": (
            "low quality unattractive image",
            "poorly composed unattractive image",
            "visually unappealing photo",
        ),
    },
    "technical": {
        "positive": (
            "sharp image with clean details",
            "technically excellent photo",
            "well focused image",
        ),
        "negative": (
            "blurry noisy image",
            "technically flawed photo",
            "out of focus image",
        ),
    },
    "composition": {
        "positive": (
            "strong composition with clear subject",
            "well balanced framing",
            "cinematic composition",
        ),
        "negative": (
            "poor composition and weak framing",
            "cluttered composition",
            "unbalanced framing",
        ),
    },
    "lighting": {
        "positive": (
            "well lit scene with good exposure",
            "pleasant lighting and tonal detail",
            "balanced highlights and shadows",
        ),
        "negative": (
            "poor lighting and weak exposure",
            "harsh lighting with clipped tones",
            "underexposed or overexposed image",
        ),
    },
    "color": {
        "positive": (
            "rich natural color rendering",
            "harmonious color palette",
            "excellent color balance",
        ),
        "negative": (
            "dull or unpleasant colors",
            "poor color balance",
            "oversaturated or washed out colors",
        ),
    },
}


def _clamp_score(value: float) -> float:
    return max(1.0, min(10.0, round(float(value), 1)))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


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


def _get_classifier_pipeline():
    global _CLASSIFIER_PIPELINE, _PIPELINE_INIT_FAILED

    if _CLASSIFIER_PIPELINE is not None:
        return _CLASSIFIER_PIPELINE
    if _PIPELINE_INIT_FAILED:
        return None

    model_id = os.environ.get("PRETRAINED_SCORER_MODEL_ID", "openai/clip-vit-base-patch32")
    device_name = os.environ.get("PRETRAINED_DEVICE", "cpu")

    try:
        from transformers import pipeline

        _CLASSIFIER_PIPELINE = pipeline(
            "zero-shot-image-classification",
            model=model_id,
            device=_parse_device_index(device_name),
        )
    except Exception:
        _PIPELINE_INIT_FAILED = True
        _CLASSIFIER_PIPELINE = None

    return _CLASSIFIER_PIPELINE


def _normalize_predictions(predictions) -> List[Dict[str, float]]:
    normalized: List[Dict[str, float]] = []
    for entry in predictions or []:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label", "")).strip().lower()
        if not label:
            continue
        try:
            score = float(entry.get("score", 0.0))
        except (TypeError, ValueError):
            continue
        if score > 0:
            normalized.append({"label": label, "score": score})

    return normalized


def _signal_from_prompt_ensemble(classifier, image, positive: Sequence[str], negative: Sequence[str]) -> float:
    labels = [str(label).strip() for label in list(positive) + list(negative) if str(label).strip()]
    if not labels:
        raise RuntimeError("Pretrained scorer prompt ensemble is empty")

    predictions = classifier(image, candidate_labels=labels)
    rows = _normalize_predictions(predictions)
    if not rows:
        raise RuntimeError("Pretrained scorer returned no prediction scores")

    total = sum(item["score"] for item in rows)
    if total <= 0:
        raise RuntimeError("Pretrained scorer returned zero total score")

    score_map = {item["label"]: (item["score"] / total) for item in rows}
    pos_set = {str(value).strip().lower() for value in positive}
    neg_set = {str(value).strip().lower() for value in negative}

    pos_sum = sum(score_map.get(label, 0.0) for label in pos_set)
    neg_sum = sum(score_map.get(label, 0.0) for label in neg_set)
    pn_total = pos_sum + neg_sum
    if pn_total <= 1e-12:
        raise RuntimeError("Pretrained scorer produced no usable positive/negative signal")

    # Keep the signal model-driven but avoid collapsing scores around the bottom range.
    signal = pos_sum / pn_total
    return _clamp01((signal * 0.88) + 0.06)


def _signal_to_score(signal: float) -> float:
    return _clamp_score(1.0 + (_clamp01(signal) * 9.0))


def get_last_backend() -> str:
    return _LAST_BACKEND


def score_image(image):
    """
    Score an image using pretrained zero-shot classification outputs only.

    Returns:
        Tuple of (aesthetic, technical, composition, lighting, color)
    """
    global _LAST_BACKEND

    classifier = _get_classifier_pipeline()
    if classifier is None:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained scorer pipeline could not be initialized")

    try:
        outputs: Dict[str, float] = {}
        for dimension, groups in _PROMPT_ENSEMBLE.items():
            signal = _signal_from_prompt_ensemble(
                classifier,
                image,
                groups.get("positive", ()),
                groups.get("negative", ()),
            )
            outputs[dimension] = _signal_to_score(signal)

        # Keep overall score coherent with model-derived subdimensions.
        sub_mean = (outputs["technical"] + outputs["composition"] + outputs["lighting"] + outputs["color"]) / 4.0
        outputs["aesthetic"] = _clamp_score((outputs["aesthetic"] * 0.65) + (sub_mean * 0.35))

        _LAST_BACKEND = "pretrained"
        return (
            outputs["aesthetic"],
            outputs["technical"],
            outputs["composition"],
            outputs["lighting"],
            outputs["color"],
        )
    except Exception as exc:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained scorer inference failed") from exc
