"""Runtime adapter for model-backed analysis.

This module keeps model selection and fallback logic in one place.
"""

from __future__ import annotations

import random
from typing import Any, Dict, Iterable, List, Tuple

from app.models import scorer as model_scorer
from app.models import style as model_style
from app.models import tagger as model_tagger
from app.services import content_analyzer
from app.services import scorer as deterministic_scorer


def _clamp_score(value: Any, default: float = 5.5) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default

    if numeric < 1.0:
        numeric = 1.0
    elif numeric > 10.0:
        numeric = 10.0

    return round(numeric, 1)


def _ensure_score_tuple(values: Any) -> Tuple[float, float, float, float, float]:
    if isinstance(values, (list, tuple)) and len(values) >= 5:
        return (
            _clamp_score(values[0]),
            _clamp_score(values[1]),
            _clamp_score(values[2]),
            _clamp_score(values[3]),
            _clamp_score(values[4]),
        )

    raise ValueError("Expected 5 score values from scorer")


def _coerce_tags(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []

    seen = set()
    tags: List[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        item = value.strip().lower()
        if not item or item in seen:
            continue
        seen.add(item)
        tags.append(item)

    return tags[:10]


def _tags_to_hashtags(tags: Iterable[str]) -> List[str]:
    hashtags: List[str] = []
    seen = set()

    for tag in tags:
        token = "".join(ch for ch in str(tag).lower() if ch.isalnum())
        if not token:
            continue
        hashtag = f"#{token}"
        if hashtag in seen:
            continue
        seen.add(hashtag)
        hashtags.append(hashtag)

    return hashtags[:10]


def _should_use_pretrained(app_config: Dict[str, Any], flag_name: str) -> bool:
    if not bool(app_config.get(flag_name, False)):
        return False

    canary_percent = float(app_config.get("MODEL_CANARY_PERCENT", 100.0) or 100.0)
    if canary_percent <= 0:
        return False
    if canary_percent >= 100:
        return True

    return (random.random() * 100.0) < canary_percent


def _blend_scores(pretrained_scores: Tuple[float, float, float, float, float], baseline_scores: Dict[str, float], blend_alpha: float) -> Tuple[float, float, float, float, float]:
    alpha = max(0.0, min(float(blend_alpha), 1.0))
    base_tuple = (
        float(baseline_scores["aesthetic"]),
        float(baseline_scores["technical"]),
        float(baseline_scores["composition"]),
        float(baseline_scores["lighting"]),
        float(baseline_scores["color"]),
    )

    blended = []
    for pretrained, baseline in zip(pretrained_scores, base_tuple):
        value = (alpha * float(pretrained)) + ((1.0 - alpha) * baseline)
        blended.append(_clamp_score(value))

    return tuple(blended)  # type: ignore[return-value]


def analyze_image_runtime(image, filename: str, app_config: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze image with pretrained models when enabled, else deterministic fallback."""
    quality = deterministic_scorer.analyze_image_quality(image)
    base_scores = quality["scores_1_10"]

    fallback_on_error = bool(app_config.get("FALLBACK_ON_MODEL_ERROR", True))
    blend_alpha = float(app_config.get("PRETRAINED_SCORE_BLEND_ALPHA", 0.70) or 0.70)

    # Start from deterministic values for safety.
    active_scores = (
        _clamp_score(base_scores["aesthetic"]),
        _clamp_score(base_scores["technical"]),
        _clamp_score(base_scores["composition"]),
        _clamp_score(base_scores["lighting"]),
        _clamp_score(base_scores["color"]),
    )
    scorer_source = "deterministic"
    fallback_used = False

    use_pretrained_scorer = _should_use_pretrained(app_config, "USE_PRETRAINED_SCORER")
    if use_pretrained_scorer:
        try:
            pretrained_scores = _ensure_score_tuple(model_scorer.score_image(image))
            active_scores = _blend_scores(pretrained_scores, base_scores, blend_alpha)
            scorer_source = "pretrained"
        except Exception:
            if not fallback_on_error:
                raise
            fallback_used = True
            scorer_source = "deterministic-fallback"

    aesthetic, technical, composition, lighting, color = active_scores

    metadata = content_analyzer.build_analysis_metadata(
        image,
        filename,
        aesthetic,
        technical,
        composition,
        lighting,
        color,
        quality=quality,
    )

    final_style = metadata["style"]
    final_mood = metadata["mood"]
    final_tags = list(metadata["tags"])
    final_hashtags = list(metadata["hashtags"])
    final_suggestions = list(metadata["suggestions"])
    tagger_source = "deterministic"

    use_pretrained_tagger = _should_use_pretrained(app_config, "USE_PRETRAINED_TAGGER")
    if use_pretrained_tagger:
        try:
            pretrained_tags = _coerce_tags(model_tagger.generate_tags(image))
            if pretrained_tags:
                final_tags = pretrained_tags
                final_hashtags = _tags_to_hashtags(pretrained_tags)

            style_label, mood_label = model_style.classify_style(image)
            if isinstance(style_label, str) and style_label.strip():
                final_style = style_label.strip()
            if isinstance(mood_label, str) and mood_label.strip():
                final_mood = mood_label.strip()

            tagger_source = "pretrained"
        except Exception:
            if not fallback_on_error:
                raise
            fallback_used = True
            tagger_source = "deterministic-fallback"

    return {
        "aestheticScore": aesthetic,
        "technicalScore": technical,
        "composition": composition,
        "lighting": lighting,
        "color": color,
        "style": final_style,
        "mood": final_mood,
        "tags": final_tags,
        "hashtags": final_hashtags,
        "suggestions": final_suggestions,
        "_runtime": {
            "model_version": "pretrained-v1" if scorer_source == "pretrained" or tagger_source == "pretrained" else "deterministic-v1",
            "scorer_source": scorer_source,
            "tagger_source": tagger_source,
            "fallback_used": fallback_used,
        },
    }
