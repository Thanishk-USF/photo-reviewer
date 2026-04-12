"""Runtime adapter for model-backed analysis.

This module keeps model selection and fallback logic in one place.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from app.models import scorer as model_scorer
from app.models import style as model_style
from app.models import suggester as model_suggester
from app.models import tagger as model_tagger


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


def _require_pretrained_enabled(app_config: Dict[str, Any], flag_name: str) -> None:
    if bool(app_config.get(flag_name, False)):
        return
    raise RuntimeError(f"{flag_name} must be enabled for pretrained-only analysis")


def analyze_image_runtime(image, filename: str, app_config: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze image with pretrained model outputs only (no deterministic fallback)."""
    _require_pretrained_enabled(app_config, "USE_PRETRAINED_SCORER")
    _require_pretrained_enabled(app_config, "USE_PRETRAINED_TAGGER")
    _require_pretrained_enabled(app_config, "USE_PRETRAINED_STYLE")
    _require_pretrained_enabled(app_config, "USE_PRETRAINED_SUGGESTER")

    aesthetic, technical, composition, lighting, color = _ensure_score_tuple(model_scorer.score_image(image))
    scorer_source = getattr(model_scorer, "get_last_backend", lambda: "pretrained")()

    final_tags = _coerce_tags(model_tagger.generate_tags(image))
    if not final_tags:
        raise RuntimeError("Pretrained tagger returned no usable tags")
    final_hashtags = _tags_to_hashtags(final_tags)
    tagger_source = getattr(model_tagger, "get_last_backend", lambda: "pretrained")()

    final_style, final_mood = model_style.classify_style(image)
    if not isinstance(final_style, str) or not final_style.strip() or not isinstance(final_mood, str) or not final_mood.strip():
        raise RuntimeError("Pretrained style classifier returned empty labels")
    final_style = final_style.strip()
    final_mood = final_mood.strip()
    style_source = getattr(model_style, "get_last_backend", lambda: "pretrained")()

    model_suggestions = model_suggester.generate_suggestions(
        image,
        {
            "aesthetic": aesthetic,
            "technical": technical,
            "composition": composition,
            "lighting": lighting,
            "color": color,
        },
    )
    final_suggestions = [str(item).strip() for item in model_suggestions if isinstance(item, str) and str(item).strip()]
    if not final_suggestions:
        raise RuntimeError("Pretrained suggester returned no usable suggestions")
    suggestion_source = getattr(model_suggester, "get_last_backend", lambda: "pretrained")()

    if not all(source == "pretrained" for source in (scorer_source, tagger_source, style_source, suggestion_source)):
        raise RuntimeError("Non-pretrained backend detected in pretrained-only mode")

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
            "model_version": "pretrained-v2",
            "scorer_source": scorer_source,
            "tagger_source": tagger_source,
            "style_source": style_source,
            "suggestion_source": suggestion_source,
            "fallback_used": False,
        },
    }
