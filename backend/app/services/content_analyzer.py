"""Feature-driven content analysis helpers.

This module generates style, mood, tags, hashtags, and improvement suggestions
from image-derived signals. It is deterministic and does not rely on random mocks.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

import numpy as np


def _clamp01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _extract_basic_features(image) -> Dict[str, float]:
    if image.mode != "RGB":
        image = image.convert("RGB")

    rgb = np.asarray(image, dtype=np.float32) / 255.0
    r = rgb[:, :, 0]
    g = rgb[:, :, 1]
    b = rgb[:, :, 2]

    luma = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
    mean_luma = float(np.mean(luma))
    std_luma = float(np.std(luma))

    max_channel = np.max(rgb, axis=2)
    min_channel = np.min(rgb, axis=2)
    saturation = np.where(max_channel > 1e-6, (max_channel - min_channel) / (max_channel + 1e-6), 0.0)
    saturation_mean = float(np.mean(saturation))

    grad_y, grad_x = np.gradient(luma)
    grad_mag = np.sqrt((grad_x * grad_x) + (grad_y * grad_y))
    edge_strength = float(np.mean(grad_mag))

    channel_means = np.array([float(np.mean(r)), float(np.mean(g)), float(np.mean(b))], dtype=np.float32)
    dominant_channel = int(np.argmax(channel_means))

    height, width = luma.shape
    aspect_ratio = float(width) / max(float(height), 1.0)

    return {
        "mean_luma": mean_luma,
        "std_luma": std_luma,
        "saturation_mean": saturation_mean,
        "edge_strength": edge_strength,
        "dominant_channel": dominant_channel,
        "aspect_ratio": aspect_ratio,
    }


def _extract_filename_tokens(filename: str) -> List[str]:
    name = filename.rsplit(".", 1)[0].lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", name) if t]
    return tokens


def _infer_style_and_mood(features: Dict[str, float], scores: Dict[str, float]) -> Tuple[str, str]:
    saturation = features["saturation_mean"]
    brightness = features["mean_luma"]
    contrast = features["std_luma"]
    edge = features["edge_strength"]

    if saturation < 0.12:
        style = "Monochrome"
    elif edge < 0.055 and contrast < 0.16:
        style = "Minimalist"
    elif saturation > 0.35 and scores["color"] >= 7.0:
        style = "Vibrant"
    elif scores["technical"] >= 7.5 and contrast > 0.20:
        style = "HDR"
    else:
        style = "Natural"

    if brightness < 0.28 and contrast > 0.16:
        mood = "Dramatic"
    elif brightness < 0.28:
        mood = "Mysterious"
    elif brightness > 0.72 and saturation > 0.28:
        mood = "Joyful"
    elif contrast < 0.14:
        mood = "Calm"
    else:
        mood = "Serene"

    return style, mood


def _build_tags(features: Dict[str, float], filename_tokens: List[str], style: str, mood: str) -> List[str]:
    tags: List[str] = []

    ratio = features["aspect_ratio"]
    if ratio > 1.2:
        tags.append("landscape")
    elif ratio < 0.85:
        tags.append("portrait")
    else:
        tags.append("square")

    brightness = features["mean_luma"]
    saturation = features["saturation_mean"]
    contrast = features["std_luma"]
    dominant_channel = features["dominant_channel"]

    if brightness < 0.25:
        tags.extend(["dark", "low-light"])
    elif brightness > 0.75:
        tags.extend(["bright", "high-key"])

    if saturation < 0.12:
        tags.append("monochrome")
    elif saturation > 0.35:
        tags.append("colorful")

    if contrast > 0.22:
        tags.append("high-contrast")
    elif contrast < 0.12:
        tags.append("soft-contrast")

    if dominant_channel == 2:
        tags.append("cool-tones")
    elif dominant_channel == 0:
        tags.append("warm-tones")

    keyword_map = {
        "moon": ["moon", "night-sky", "astronomy"],
        "eclipse": ["eclipse", "space", "astronomy"],
        "space": ["space", "cosmic"],
        "cat": ["cat", "animal", "pet"],
        "anime": ["anime", "illustration"],
        "portrait": ["portrait", "character"],
    }

    token_set = set(filename_tokens)
    for token, inferred in keyword_map.items():
        if token in token_set:
            tags.extend(inferred)

    tags.append(style.lower())
    tags.append(mood.lower())

    deduped = []
    seen = set()
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            deduped.append(tag)

    return deduped[:10]


def _build_suggestions(scores: Dict[str, float], features: Dict[str, float]) -> List[str]:
    suggestions: List[str] = []

    if scores["composition"] < 6.0:
        suggestions.append("Try reframing with the subject near a rule-of-thirds intersection for stronger balance.")
    if scores["lighting"] < 6.0:
        if features["mean_luma"] < 0.30:
            suggestions.append("Lift exposure slightly or add a fill light to recover shadow detail.")
        else:
            suggestions.append("Reduce highlights a bit to preserve detail in brighter regions.")
    if scores["color"] < 6.0:
        if features["saturation_mean"] < 0.14:
            suggestions.append("Increase vibrance modestly to improve color separation without oversaturation.")
        else:
            suggestions.append("Tune white balance to reduce color cast and improve color harmony.")
    if scores["technical"] < 6.0:
        suggestions.append("Improve sharpness with a faster shutter speed or steadier camera support.")

    if not suggestions:
        suggestions.append("Strong image overall. Minor local contrast adjustments can add extra depth.")
        suggestions.append("Consider a subtle crop to tighten focus on the primary subject.")

    fallback_pool = [
        "Export at full resolution to retain texture and micro-detail.",
        "Use selective sharpening on the subject while keeping noise reduction gentle.",
        "Refine crop margins slightly to remove visual distractions near the frame edges.",
    ]

    # Keep ordering deterministic while removing duplicates.
    unique_suggestions: List[str] = []
    seen = set()
    for suggestion in suggestions:
        if suggestion not in seen:
            seen.add(suggestion)
            unique_suggestions.append(suggestion)

    for fallback in fallback_pool:
        if len(unique_suggestions) >= 3:
            break
        if fallback not in seen:
            seen.add(fallback)
            unique_suggestions.append(fallback)

    return unique_suggestions[:3]


def _build_hashtags(tags: List[str], style: str, mood: str) -> List[str]:
    base = tags[:8] + [style.lower(), mood.lower(), "photography"]
    normalized = []
    seen = set()
    for tag in base:
        token = re.sub(r"[^a-z0-9]+", "", tag.lower())
        if not token:
            continue
        hashtag = f"#{token}"
        if hashtag not in seen:
            seen.add(hashtag)
            normalized.append(hashtag)
    return normalized[:10]


def build_analysis_metadata(image, filename: str, aesthetic_score: float, technical_score: float, composition: float, lighting: float, color: float):
    scores = {
        "aesthetic": float(aesthetic_score),
        "technical": float(technical_score),
        "composition": float(composition),
        "lighting": float(lighting),
        "color": float(color),
    }

    features = _extract_basic_features(image)
    filename_tokens = _extract_filename_tokens(filename)

    style, mood = _infer_style_and_mood(features, scores)
    tags = _build_tags(features, filename_tokens, style, mood)
    suggestions = _build_suggestions(scores, features)
    hashtags = _build_hashtags(tags, style, mood)

    return {
        "style": style,
        "mood": mood,
        "tags": tags,
        "hashtags": hashtags,
        "suggestions": suggestions,
    }
