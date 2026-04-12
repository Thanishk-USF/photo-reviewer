"""
Model-backed aesthetic scoring adapter.
"""

from __future__ import annotations

import math
from typing import Tuple

from app.services import scorer as baseline_scorer


def _clamp_score(value: float) -> float:
    return max(1.0, min(10.0, round(float(value), 1)))


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


def score_image(image):
    """
    Score an image for aesthetic quality using a model adapter path.

    During early rollout this uses calibrated deterministic features as a
    lightweight stand-in. It is intentionally non-random.

    Returns:
        Tuple of (aesthetic, technical, composition, lighting, color)
    """
    quality = baseline_scorer.analyze_image_quality(image)
    base = quality['scores_1_10']

    return _calibrate_baseline_scores(
        float(base['aesthetic']),
        float(base['technical']),
        float(base['composition']),
        float(base['lighting']),
        float(base['color']),
    )
