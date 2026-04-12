"""
Model-backed aesthetic scoring adapter.
"""

from __future__ import annotations

import math
import os
from typing import Optional, Tuple

from app.services import scorer as baseline_scorer

_CLASSIFIER_PIPELINE = None
_PIPELINE_INIT_FAILED = False
_LAST_BACKEND = "deterministic-adapter"


def _clamp_score(value: float) -> float:
    return max(1.0, min(10.0, round(float(value), 1)))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
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


def _get_classifier_pipeline():
    global _CLASSIFIER_PIPELINE, _PIPELINE_INIT_FAILED

    if _CLASSIFIER_PIPELINE is not None:
        return _CLASSIFIER_PIPELINE
    if _PIPELINE_INIT_FAILED:
        return None

    model_id = os.environ.get("PRETRAINED_SCORER_MODEL_ID", "google/vit-base-patch16-224")
    device_name = os.environ.get("PRETRAINED_DEVICE", "cpu")
    top_k = _env_int("PRETRAINED_SCORER_TOP_K", 5)

    try:
        from transformers import pipeline

        _CLASSIFIER_PIPELINE = pipeline(
            "image-classification",
            model=model_id,
            device=_parse_device_index(device_name),
            top_k=max(1, min(top_k, 20)),
        )
    except Exception:
        _PIPELINE_INIT_FAILED = True
        _CLASSIFIER_PIPELINE = None

    return _CLASSIFIER_PIPELINE


def _confidence_signal_from_predictions(predictions) -> Optional[float]:
    scores = []
    for entry in predictions or []:
        if not isinstance(entry, dict):
            continue
        try:
            score = float(entry.get("score", 0.0))
        except (TypeError, ValueError):
            continue
        if score > 0:
            scores.append(score)

    if not scores:
        return None

    total = sum(scores)
    if total <= 0:
        return None

    probs = [s / total for s in scores]
    entropy = -sum(p * math.log(p + 1e-12) for p in probs)
    max_entropy = math.log(float(len(probs))) if len(probs) > 1 else 1.0
    entropy_norm = entropy / max_entropy if max_entropy > 0 else 0.0
    certainty = 1.0 - _clamp01(entropy_norm)
    max_score = max(scores)

    return _clamp01((0.60 * max_score) + (0.40 * certainty))


def _signal_to_score(signal: float) -> float:
    # Keep score in familiar UI range even for different classifier confidence scales.
    return _clamp_score(1.0 + (_clamp01(signal) * 9.0))


def _calibrate_baseline_scores(aesthetic: float, technical: float, composition: float, lighting: float, color: float) -> Tuple[float, float, float, float, float]:
    """Apply a mild non-linear calibration to baseline scores.

    This keeps output dynamic and deterministic without requiring heavy DL
    dependencies during initial rollout.
    """
    mean_score = (aesthetic + technical + composition + lighting + color) / 5.0
    curve = 0.15 * math.tanh((mean_score - 6.0) / 2.0)

    return (
        _clamp_score((aesthetic * 0.92) + 0.55 + curve),
        _clamp_score((technical * 0.90) + 0.65 + curve),
        _clamp_score((composition * 0.93) + 0.50 + curve),
        _clamp_score((lighting * 0.91) + 0.58 + curve),
        _clamp_score((color * 0.92) + 0.52 + curve),
    )


def get_last_backend() -> str:
    return _LAST_BACKEND


def score_image(image):
    """
    Score an image for aesthetic quality using a model adapter path.

    During early rollout this uses calibrated deterministic features as a
    lightweight stand-in. It is intentionally non-random.

    Returns:
        Tuple of (aesthetic, technical, composition, lighting, color)
    """
    global _LAST_BACKEND

    quality = baseline_scorer.analyze_image_quality(image)
    base = quality['scores_1_10']

    fallback_scores = _calibrate_baseline_scores(
        float(base['aesthetic']),
        float(base['technical']),
        float(base['composition']),
        float(base['lighting']),
        float(base['color']),
    )

    classifier = _get_classifier_pipeline()
    if classifier is None:
        _LAST_BACKEND = "deterministic-adapter"
        return fallback_scores

    try:
        confidence_signal = _confidence_signal_from_predictions(classifier(image))
    except Exception:
        _LAST_BACKEND = "deterministic-adapter"
        return fallback_scores

    if confidence_signal is None:
        _LAST_BACKEND = "deterministic-adapter"
        return fallback_scores

    model_aesthetic = _signal_to_score(confidence_signal)
    normalized = quality.get('scores_normalized') if isinstance(quality, dict) else None
    if not isinstance(normalized, dict):
        normalized = {}

    technical_norm = _clamp01(float(normalized.get('technical', float(base['technical']) / 10.0)))
    composition_norm = _clamp01(float(normalized.get('composition', float(base['composition']) / 10.0)))
    lighting_norm = _clamp01(float(normalized.get('lighting', float(base['lighting']) / 10.0)))
    color_norm = _clamp01(float(normalized.get('color', float(base['color']) / 10.0)))

    model_technical = _signal_to_score((0.80 * confidence_signal) + (0.20 * technical_norm))
    model_composition = _signal_to_score((0.50 * confidence_signal) + (0.50 * composition_norm))
    model_lighting = _signal_to_score((0.50 * confidence_signal) + (0.50 * lighting_norm))
    model_color = _signal_to_score((0.50 * confidence_signal) + (0.50 * color_norm))

    _LAST_BACKEND = "pretrained"

    # Blend model-derived global signal with calibrated baseline for stable outputs.
    return (
        _clamp_score((fallback_scores[0] * 0.55) + (model_aesthetic * 0.45)),
        _clamp_score((fallback_scores[1] * 0.65) + (model_technical * 0.35)),
        _clamp_score((fallback_scores[2] * 0.80) + (model_composition * 0.20)),
        _clamp_score((fallback_scores[3] * 0.80) + (model_lighting * 0.20)),
        _clamp_score((fallback_scores[4] * 0.80) + (model_color * 0.20)),
    )
