"""Analysis response contract helpers.

These helpers keep the API payload stable while model providers evolve.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List

SCORE_FIELDS = (
    "aestheticScore",
    "technicalScore",
    "composition",
    "lighting",
    "color",
)

DEFAULT_STYLE = "Natural"
DEFAULT_MOOD = "Serene"
DEFAULT_IMAGE_URL = "/placeholder.svg"
DEFAULT_TAGS = ["photo"]
DEFAULT_HASHTAGS = ["#photography"]
DEFAULT_SUGGESTIONS = [
    "Strong image overall. Minor local contrast adjustments can add extra depth.",
    "Consider a subtle crop to tighten focus on the primary subject.",
]


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


def _coerce_string(value: Any, default: str = "") -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return default


def _coerce_string_list(value: Any, default: Iterable[str]) -> List[str]:
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            stripped = item.strip()
            if not stripped:
                continue
            if stripped not in out:
                out.append(stripped)
        if out:
            return out

    return [item for item in default if isinstance(item, str) and item]


def normalize_analysis_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a contract-safe analysis payload for API responses."""
    source = dict(payload or {})

    image_url = _coerce_string(source.get("imageUrl"), DEFAULT_IMAGE_URL)
    thumbnail_url = _coerce_string(source.get("thumbnailUrl"), image_url)
    filename = _coerce_string(source.get("filename"), "")

    if not filename and image_url:
        filename = image_url.split("/")[-1]

    normalized: Dict[str, Any] = {
        "success": bool(source.get("success", True)),
        "imageUrl": image_url,
        "thumbnailUrl": thumbnail_url,
        "filename": filename,
        "uploadDate": _coerce_string(source.get("uploadDate"), datetime.utcnow().isoformat()),
        "style": _coerce_string(source.get("style"), DEFAULT_STYLE),
        "mood": _coerce_string(source.get("mood"), DEFAULT_MOOD),
    }

    record_id = _coerce_string(source.get("id"), "")
    if record_id:
        normalized["id"] = record_id

    for field in SCORE_FIELDS:
        normalized[field] = _clamp_score(source.get(field))

    tags = _coerce_string_list(source.get("tags"), DEFAULT_TAGS)[:10]
    normalized["tags"] = tags

    hashtags = _coerce_string_list(source.get("hashtags"), [])
    if not hashtags:
        hashtags = []
        for tag in tags:
            token = "".join(ch for ch in tag.lower() if ch.isalnum())
            if token:
                hashtags.append(f"#{token}")
        if not hashtags:
            hashtags = list(DEFAULT_HASHTAGS)
    normalized["hashtags"] = hashtags[:10]

    normalized["suggestions"] = _coerce_string_list(source.get("suggestions"), DEFAULT_SUGGESTIONS)[:5]

    error_text = _coerce_string(source.get("error"), "")
    if error_text:
        normalized["error"] = error_text

    return normalized
