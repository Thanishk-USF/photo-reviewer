"""Adaptive profiling utilities to improve analysis quality using historical user data.

This module builds a lightweight cached profile from prior Mongo analysis records
and exposes helpers for score calibration, dynamic tag vocabulary expansion, and
retrieval-backed suggestion enrichment.
"""

from __future__ import annotations

import math
import os
import re
import threading
import time
from collections import Counter
from typing import Dict, Iterable, List, Tuple

from app.services.mongo_service import photos_collection

_PROFILE_CACHE_LOCK = threading.Lock()
_PROFILE_CACHE: Dict[str, object] = {
    "expires_at": 0.0,
    "value": None,
}

_SCORE_DIMENSIONS = ("aesthetic", "technical", "composition", "lighting", "color")
_SENSITIVE_TAGS = {"moon", "astronomy"}


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


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


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _normalize_tag(tag: str) -> str:
    text = _normalize_text(tag).replace("_", " ").replace("-", " ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokenize(text: str) -> List[str]:
    normalized = _normalize_tag(text)
    return [token for token in normalized.split() if token]


def _quantile(sorted_values: List[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if q <= 0:
        return float(sorted_values[0])
    if q >= 1:
        return float(sorted_values[-1])

    pos = (len(sorted_values) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_values[lo])

    weight = pos - lo
    return float(sorted_values[lo] * (1.0 - weight) + sorted_values[hi] * weight)


def _default_profile() -> Dict[str, object]:
    return {
        "sample_count": 0,
        "score_means": {},
        "score_quantiles": {},
        "tag_priors": {},
        "dynamic_labels": [],
        "suggestion_pool": [],
        "adaptive_epoch": 0,
    }


def invalidate_adaptive_profile_cache() -> None:
    """Invalidate cached adaptive profile so next read reflects latest records."""
    with _PROFILE_CACHE_LOCK:
        _PROFILE_CACHE["value"] = None
        _PROFILE_CACHE["expires_at"] = 0.0


def _build_profile_from_docs(docs: Iterable[dict], adaptive_epoch: int) -> Dict[str, object]:
    score_values: Dict[str, List[float]] = {dim: [] for dim in _SCORE_DIMENSIONS}
    tag_counter: Counter[str] = Counter()
    tag_weight_counter: Dict[str, float] = {}
    suggestion_counter: Counter[str] = Counter()
    suggestion_display: Dict[str, str] = {}
    base_tag_min_confidence = max(0.0, min(_env_float("ADAPTIVE_TAG_MIN_CONFIDENCE", 0.35), 1.0))
    sensitive_tag_min_confidence = max(
        base_tag_min_confidence,
        min(_env_float("ADAPTIVE_TAG_SENSITIVE_MIN_CONFIDENCE", 0.55), 1.0),
    )
    require_confidence = _env_bool("ADAPTIVE_REQUIRE_TAG_CONFIDENCE", False)
    min_prior_occurrences = max(1, min(_env_int("ADAPTIVE_TAG_MIN_OCCURRENCES", 2), 20))
    min_dynamic_occurrences = max(
        min_prior_occurrences,
        min(_env_int("ADAPTIVE_DYNAMIC_TAG_MIN_OCCURRENCES", 3), 25),
    )

    sample_count = 0
    for doc in docs:
        sample_count += 1

        tag_confidences = doc.get("tag_confidences", {}) or {}
        if not isinstance(tag_confidences, dict):
            tag_confidences = {}

        for dim in _SCORE_DIMENSIONS:
            key = f"{dim}Score" if dim in {"aesthetic", "technical"} else dim
            value = doc.get(key)
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if 1.0 <= numeric <= 10.0:
                score_values[dim].append(numeric)

        for tag in doc.get("tags", []) or []:
            if not isinstance(tag, str):
                continue
            normalized_tag = _normalize_tag(tag)
            if not normalized_tag or normalized_tag == "photo":
                continue

            confidence_value = None
            if normalized_tag in tag_confidences:
                confidence_value = tag_confidences.get(normalized_tag)
            elif tag in tag_confidences:
                confidence_value = tag_confidences.get(tag)

            confidence = None
            if confidence_value is not None:
                try:
                    confidence = float(confidence_value)
                except (TypeError, ValueError):
                    confidence = None

            min_required = sensitive_tag_min_confidence if normalized_tag in _SENSITIVE_TAGS else base_tag_min_confidence

            if confidence is not None and confidence < min_required:
                continue

            if confidence is None and require_confidence:
                continue

            tag_counter[normalized_tag] += 1
            confidence_weight = confidence if confidence is not None else base_tag_min_confidence
            confidence_weight = max(0.05, min(1.0, float(confidence_weight)))
            tag_weight_counter[normalized_tag] = float(tag_weight_counter.get(normalized_tag, 0.0)) + confidence_weight

        for suggestion in doc.get("suggestions", []) or []:
            if not isinstance(suggestion, str):
                continue
            raw_text = str(suggestion).strip()
            if not raw_text:
                continue
            normalized = _normalize_text(raw_text)
            if normalized:
                suggestion_counter[normalized] += 1
                if normalized not in suggestion_display:
                    suggestion_display[normalized] = raw_text

    score_means: Dict[str, float] = {}
    score_quantiles: Dict[str, Dict[str, float]] = {}
    for dim, values in score_values.items():
        if not values:
            continue
        ordered = sorted(values)
        score_means[dim] = round(sum(ordered) / float(len(ordered)), 4)
        score_quantiles[dim] = {
            "q10": round(_quantile(ordered, 0.10), 4),
            "q50": round(_quantile(ordered, 0.50), 4),
            "q90": round(_quantile(ordered, 0.90), 4),
        }

    filtered_weights: Dict[str, float] = {}
    for tag, count in tag_counter.items():
        if int(count) < min_prior_occurrences:
            continue
        filtered_weights[tag] = float(tag_weight_counter.get(tag, float(count)))

    total_weight = sum(filtered_weights.values())
    tag_priors: Dict[str, float] = {}
    if total_weight > 0.0:
        for tag, weighted_count in filtered_weights.items():
            tag_priors[tag] = float(weighted_count) / float(total_weight)

    max_dynamic = max(10, min(_env_int("ADAPTIVE_MAX_DYNAMIC_TAG_LABELS", 80), 400))
    dynamic_labels = [tag for tag, count in tag_counter.most_common(max_dynamic) if int(count) >= min_dynamic_occurrences]

    max_suggestions = max(20, min(_env_int("ADAPTIVE_MAX_SUGGESTION_POOL", 240), 1000))
    suggestion_pool = []
    for normalized, freq in suggestion_counter.most_common(max_suggestions):
        text = suggestion_display.get(normalized, normalized)
        suggestion_pool.append(
            {
                "text": text,
                "freq": int(freq),
                "tokens": _tokenize(normalized),
            }
        )

    return {
        "sample_count": sample_count,
        "score_means": score_means,
        "score_quantiles": score_quantiles,
        "tag_priors": tag_priors,
        "dynamic_labels": dynamic_labels,
        "suggestion_pool": suggestion_pool,
        "adaptive_epoch": int(adaptive_epoch),
    }


def get_adaptive_profile(force_refresh: bool = False) -> Dict[str, object]:
    """Return cached adaptive profile built from previous analysis records."""
    if not _env_bool("ADAPTIVE_PROFILE_ENABLED", True):
        return _default_profile()

    now = time.time()
    ttl_seconds = max(30, min(_env_int("ADAPTIVE_PROFILE_CACHE_TTL_SECONDS", 300), 3600))

    with _PROFILE_CACHE_LOCK:
        cached = _PROFILE_CACHE.get("value")
        expires_at = float(_PROFILE_CACHE.get("expires_at", 0.0) or 0.0)
        if not force_refresh and isinstance(cached, dict) and now < expires_at:
            return cached

    max_docs = max(50, min(_env_int("ADAPTIVE_PROFILE_MAX_DOCS", 500), 5000))
    adaptive_epoch = max(1, _env_int("ADAPTIVE_PROFILE_EPOCH", 2))
    include_legacy_docs = _env_bool("ADAPTIVE_INCLUDE_LEGACY_DOCS", False)
    projection = {
        "aestheticScore": 1,
        "technicalScore": 1,
        "composition": 1,
        "lighting": 1,
        "color": 1,
        "tags": 1,
        "tag_confidences": 1,
        "suggestions": 1,
        "adaptive_epoch": 1,
    }
    query = {} if include_legacy_docs else {"adaptive_epoch": {"$gte": adaptive_epoch}}

    try:
        docs = list(photos_collection.find(query, projection).sort("_id", -1).limit(max_docs))
        profile = _build_profile_from_docs(docs, adaptive_epoch=adaptive_epoch)
    except Exception:
        profile = _default_profile()

    with _PROFILE_CACHE_LOCK:
        _PROFILE_CACHE["value"] = profile
        _PROFILE_CACHE["expires_at"] = now + float(ttl_seconds)

    return profile


def expand_candidate_labels(base_labels: Iterable[str], profile: Dict[str, object]) -> List[str]:
    """Expand candidate labels with user-history tags while avoiding uncontrolled growth."""
    max_total = max(20, min(_env_int("ADAPTIVE_MAX_CANDIDATE_LABELS", 160), 800))

    merged: List[str] = []
    seen = set()

    for item in base_labels:
        label = _normalize_tag(item)
        if not label or label in seen:
            continue
        seen.add(label)
        merged.append(label)

    for item in profile.get("dynamic_labels", []) or []:
        label = _normalize_tag(str(item))
        if not label or label in seen:
            continue
        seen.add(label)
        merged.append(label)
        if len(merged) >= max_total:
            break

    return merged[:max_total]


def rerank_tags_with_profile(
    tags: List[str],
    profile: Dict[str, object],
    tag_confidences: Dict[str, float] | None = None,
) -> List[str]:
    """Rerank tags by user-history priors while preserving stability and uniqueness."""
    if not tags:
        return []

    priors = profile.get("tag_priors", {}) or {}
    if not isinstance(priors, dict) or not priors:
        return tags

    prior_weight = max(0.0, min(_env_float("ADAPTIVE_TAG_PRIOR_WEIGHT", 0.35), 1.0))
    confidence_weight = max(0.0, min(_env_float("ADAPTIVE_TAG_CONFIDENCE_WEIGHT", 0.70), 1.0))
    order_weight = max(0.0, min(1.0 - (prior_weight + confidence_weight), 0.60))

    normalized_conf: Dict[str, float] = {}
    if isinstance(tag_confidences, dict):
        for raw_tag, raw_score in tag_confidences.items():
            normalized = _normalize_tag(str(raw_tag))
            if not normalized:
                continue
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                continue
            normalized_conf[normalized] = max(0.0, min(1.0, score))

    head = []
    body = tags
    if tags and tags[0] == "photo":
        head = ["photo"]
        body = tags[1:]

    scored: List[Tuple[float, int, str]] = []
    for idx, tag in enumerate(body):
        normalized = _normalize_tag(tag)
        prior = float(priors.get(normalized, 0.0))
        confidence = float(normalized_conf.get(normalized, max(0.05, 1.0 - (0.08 * idx))))
        order_hint = max(0.0, 1.0 - (0.10 * idx))
        score = (confidence_weight * confidence) + (prior_weight * prior) + (order_weight * order_hint)
        scored.append((score, -idx, tag))

    scored.sort(reverse=True)
    ranked = [item[2] for item in scored]

    out = head + ranked
    deduped = []
    seen = set()
    for tag in out:
        if tag in seen:
            continue
        seen.add(tag)
        deduped.append(tag)

    return deduped[:10]


def calibrate_score_from_profile(dimension: str, raw_score: float, profile: Dict[str, object]) -> float:
    """Calibrate score with user-history statistics to reduce persistent outliers."""
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return float(raw_score)

    sample_count = int(profile.get("sample_count", 0) or 0)
    min_samples = max(20, min(_env_int("ADAPTIVE_SCORE_MIN_SAMPLES", 40), 500))
    if sample_count < min_samples:
        return round(max(1.0, min(10.0, score)), 1)

    means = profile.get("score_means", {}) or {}
    quantiles = profile.get("score_quantiles", {}) or {}
    if dimension not in means:
        return round(max(1.0, min(10.0, score)), 1)

    mean_value = float(means.get(dimension, score))
    q = quantiles.get(dimension, {}) or {}
    q10 = float(q.get("q10", 1.0))
    q90 = float(q.get("q90", 10.0))

    # Soft clipping around historical spread before applying mean re-centering.
    lower = max(1.0, q10 - 1.0)
    upper = min(10.0, q90 + 1.0)
    clipped = min(max(score, lower), upper)

    weight = max(0.0, min(_env_float("ADAPTIVE_SCORE_CALIBRATION_WEIGHT", 0.15), 0.50))
    adjusted = ((1.0 - weight) * clipped) + (weight * mean_value)

    return round(max(1.0, min(10.0, adjusted)), 1)


def retrieve_suggestions_from_profile(query_terms: Iterable[str], profile: Dict[str, object], limit: int = 3) -> List[str]:
    """Retrieve context-matching suggestions from user history suggestion pool."""
    pool = profile.get("suggestion_pool", []) or []
    if not isinstance(pool, list) or not pool:
        return []

    query_tokens = set()
    for term in query_terms:
        for token in _tokenize(str(term)):
            query_tokens.add(token)

    ranked: List[Tuple[float, str]] = []
    for item in pool:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue

        tokens = item.get("tokens", []) or []
        token_set = set(token for token in tokens if isinstance(token, str) and token)
        freq = int(item.get("freq", 1) or 1)

        overlap = 0.0
        if query_tokens and token_set:
            overlap = float(len(query_tokens & token_set)) / math.sqrt(float(len(query_tokens) * len(token_set)))

        freq_bonus = min(freq / 100.0, 1.0) * 0.20
        score = overlap + freq_bonus
        ranked.append((score, text))

    if not ranked:
        return []

    ranked.sort(key=lambda row: row[0], reverse=True)

    out: List[str] = []
    seen = set()
    for _, text in ranked:
        normalized = _normalize_text(text)
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(text)
        if len(out) >= max(1, int(limit)):
            break

    return out
