"""
Model-backed tag generator adapter.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from app.services.adaptive_learning import expand_candidate_labels, get_adaptive_profile, rerank_tags_with_profile
from app.services.device_policy import build_transformers_pipeline

_ZERO_SHOT_PIPELINE = None
_CAPTION_PIPELINE = None
_OBJECT_PIPELINE = None
_SEGMENT_PIPELINE = None
_PIPELINE_INIT_FAILED = False
_CAPTION_INIT_FAILED = False
_OBJECT_INIT_FAILED = False
_SEGMENT_INIT_FAILED = False
_LAST_BACKEND = "pretrained-uninitialized"
_ZERO_SHOT_DEVICE = "uninitialized"
_CAPTION_DEVICE = "uninitialized"
_OBJECT_DEVICE = "uninitialized"
_SEGMENT_DEVICE = "uninitialized"
_LAST_TAG_CONFIDENCES = {}

_DEFAULT_CANDIDATE_LABELS = [
    "flower",
    "bouquet",
    "petals",
    "hand",
    "fingers",
    "ring",
    "sky",
    "blue sky",
    "clouds",
    "sunlight",
    "outdoor",
    "close up",
    "macro",
    "person",
    "human",
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
    "water lily": "flower",
    "lily": "flower",
    "blue sky": "blue-sky",
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
    "flower": "flower",
    "petal": "petals",
    "bouquet": "bouquet",
    "hand": "hand",
    "finger": "fingers",
    "ring": "ring",
    "sky": "sky",
    "cloud": "clouds",
    "sunlight": "sunlight",
    "outdoor": "outdoor",
    "close up": "close-up",
    "close-up": "close-up",
    "macro": "macro",
    "portrait": "portrait",
    "landscape": "landscape",
    "monochrome": "monochrome",
}


_SENSITIVE_TAGS = {"moon", "astronomy"}
_CAPTION_DIRECT_ALLOWLIST = {
    "flower",
    "petals",
    "bouquet",
    "hand",
    "fingers",
    "ring",
    "sky",
    "blue-sky",
    "clouds",
    "sunlight",
    "outdoor",
    "close-up",
    "macro",
    "portrait",
    "landscape",
}
_OBJECT_LABEL_MAP = {
    "daisy": "flower",
    "sunflower": "flower",
    "water lily": "flower",
    "lily": "flower",
    "yellow lady slipper": "flower",
    "earthstar": "flower",
    "acorn squash": "flower",
}
_OBJECT_ALLOWED_TAGS = {
    "flower",
    "petals",
    "bouquet",
    "hand",
    "fingers",
    "ring",
    "sky",
    "blue-sky",
    "clouds",
    "sunlight",
    "outdoor",
    "portrait",
    "landscape",
    "nature",
    "water",
    "water-reflection",
    "forest",
    "mountain",
    "ocean",
}

_SCENE_TAG_SET = {
    "sky",
    "blue-sky",
    "clouds",
    "sunlight",
    "outdoor",
    "landscape",
    "night-sky",
    "space",
    "space-scene",
    "architecture",
    "street-photography",
    "nature",
    "night-scene",
    "sunset",
    "sunrise",
    "ocean",
    "water",
    "water-reflection",
    "mountain",
    "forest",
    "city-skyline",
    "cloudscape",
    "seascape",
}

_BACKGROUND_SEGMENT_KEYWORDS = {
    "sky",
    "cloud",
    "mountain",
    "water",
    "ocean",
    "sea",
    "lake",
    "river",
    "forest",
    "tree",
    "grass",
    "field",
    "road",
    "street",
    "wall",
    "building",
    "city",
    "architecture",
    "beach",
    "sand",
    "snow",
    "desert",
    "ceiling",
    "floor",
    "terrain",
    "background",
}

_FOREGROUND_SEGMENT_KEYWORDS = {
    "person",
    "people",
    "human",
    "man",
    "woman",
    "boy",
    "girl",
    "face",
    "hand",
    "fingers",
    "flower",
    "petal",
    "bouquet",
    "animal",
    "dog",
    "cat",
    "bird",
    "car",
    "bus",
    "bike",
    "bicycle",
    "motorcycle",
    "food",
}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
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


def _normalize_label(label: str) -> str:
    label = label.strip().lower()
    if not label:
        return ""
    return "-".join(part for part in label.replace("_", " ").split() if part)


def _get_zero_shot_pipeline():
    global _ZERO_SHOT_PIPELINE, _PIPELINE_INIT_FAILED, _ZERO_SHOT_DEVICE

    if _ZERO_SHOT_PIPELINE is not None:
        return _ZERO_SHOT_PIPELINE
    if _PIPELINE_INIT_FAILED:
        return None

    model_id = os.environ.get("PRETRAINED_TAGGER_MODEL_ID", "openai/clip-vit-base-patch32")
    try:
        _ZERO_SHOT_PIPELINE, _ZERO_SHOT_DEVICE = build_transformers_pipeline(
            "zero-shot-image-classification",
            model_id,
        )
    except Exception:
        _PIPELINE_INIT_FAILED = True
        _ZERO_SHOT_PIPELINE = None

    return _ZERO_SHOT_PIPELINE


def _get_caption_pipeline():
    global _CAPTION_PIPELINE, _CAPTION_INIT_FAILED, _CAPTION_DEVICE

    if _CAPTION_PIPELINE is not None:
        return _CAPTION_PIPELINE
    if _CAPTION_INIT_FAILED:
        return None

    model_id = os.environ.get("PRETRAINED_TAGGER_CAPTION_MODEL_ID", "Salesforce/blip-image-captioning-base")
    try:
        _CAPTION_PIPELINE, _CAPTION_DEVICE = build_transformers_pipeline(
            "image-to-text",
            model_id,
        )
    except Exception:
        _CAPTION_INIT_FAILED = True
        _CAPTION_PIPELINE = None

    return _CAPTION_PIPELINE


def _get_object_pipeline():
    global _OBJECT_PIPELINE, _OBJECT_INIT_FAILED, _OBJECT_DEVICE

    if _OBJECT_PIPELINE is not None:
        return _OBJECT_PIPELINE
    if _OBJECT_INIT_FAILED:
        return None

    if str(os.environ.get("PRETRAINED_TAGGER_USE_OBJECT_MODEL", "true")).strip().lower() not in {"1", "true", "yes", "on"}:
        _OBJECT_INIT_FAILED = True
        return None

    model_id = os.environ.get("PRETRAINED_TAGGER_OBJECT_MODEL_ID", "google/vit-base-patch16-224")
    try:
        _OBJECT_PIPELINE, _OBJECT_DEVICE = build_transformers_pipeline(
            "image-classification",
            model_id,
        )
    except Exception:
        _OBJECT_INIT_FAILED = True
        _OBJECT_PIPELINE = None

    return _OBJECT_PIPELINE


def _get_segment_pipeline():
    global _SEGMENT_PIPELINE, _SEGMENT_INIT_FAILED, _SEGMENT_DEVICE

    if _SEGMENT_PIPELINE is not None:
        return _SEGMENT_PIPELINE
    if _SEGMENT_INIT_FAILED:
        return None

    if not _env_bool("PRETRAINED_TAGGER_USE_SEGMENT_SPLIT", True):
        _SEGMENT_INIT_FAILED = True
        return None

    model_id = os.environ.get("PRETRAINED_TAGGER_SEGMENT_MODEL_ID", "nvidia/segformer-b0-finetuned-ade-512-512")
    try:
        _SEGMENT_PIPELINE, _SEGMENT_DEVICE = build_transformers_pipeline(
            "image-segmentation",
            model_id,
        )
    except Exception:
        _SEGMENT_INIT_FAILED = True
        _SEGMENT_PIPELINE = None

    return _SEGMENT_PIPELINE


def _dedupe(values: List[str]) -> List[str]:
    out = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _predict_label_scores(classifier, image, candidate_labels: List[str], top_k: int) -> Dict[str, float]:
    output = classifier(image, candidate_labels=candidate_labels)
    if not isinstance(output, list) or not output:
        return {}

    scores: Dict[str, float] = {}
    for item in output[:top_k]:
        if not isinstance(item, dict):
            continue
        try:
            score = float(item.get("score", 0.0))
        except (TypeError, ValueError):
            continue
        label = _normalize_label(str(item.get("label", "")))
        if not label:
            continue
        scores[label] = max(float(scores.get(label, 0.0)), score)
    return scores


def _is_background_segment_label(label: str) -> bool:
    normalized = _normalize_label(label)
    if not normalized:
        return False

    tokens = {token for token in normalized.replace("-", " ").split() if token}
    if tokens & _FOREGROUND_SEGMENT_KEYWORDS:
        return False
    if normalized in _BACKGROUND_SEGMENT_KEYWORDS:
        return True
    if tokens & _BACKGROUND_SEGMENT_KEYWORDS:
        return True
    return False


def _to_mask_array(mask_value, target_size) -> Optional[np.ndarray]:
    if not isinstance(mask_value, Image.Image):
        return None

    mask_image = mask_value.convert("L")
    if mask_image.size != target_size:
        mask_image = mask_image.resize(target_size, resample=Image.Resampling.NEAREST)

    arr = np.array(mask_image, dtype=np.uint8)
    if arr.ndim != 2:
        return None
    return arr > 0


def _normalized_split_weights() -> Tuple[float, float, float]:
    full_weight = max(0.0, _env_float("PRETRAINED_TAGGER_SPLIT_FULL_WEIGHT", 0.35))
    foreground_weight = max(0.0, _env_float("PRETRAINED_TAGGER_SPLIT_FOREGROUND_WEIGHT", 0.45))
    background_weight = max(0.0, _env_float("PRETRAINED_TAGGER_SPLIT_BACKGROUND_WEIGHT", 0.20))

    total = full_weight + foreground_weight + background_weight
    if total <= 0.0:
        return 0.35, 0.45, 0.20

    return (
        float(full_weight / total),
        float(foreground_weight / total),
        float(background_weight / total),
    )


def _split_foreground_background(segmenter, image):
    min_score = max(0.01, min(_env_float("PRETRAINED_TAGGER_SEGMENT_MIN_SCORE", 0.15), 0.99))
    min_coverage = max(0.01, min(_env_float("PRETRAINED_TAGGER_SPLIT_MIN_FOREGROUND_COVERAGE", 0.08), 0.75))
    max_coverage = max(min_coverage + 0.01, min(_env_float("PRETRAINED_TAGGER_SPLIT_MAX_FOREGROUND_COVERAGE", 0.90), 0.98))

    try:
        segments = segmenter(image)
    except Exception:
        return None

    if not isinstance(segments, list) or not segments:
        return None

    rgb = image.convert("RGB")
    width, height = rgb.size
    foreground_mask = np.zeros((height, width), dtype=bool)
    saw_mask = False

    for segment in segments:
        if not isinstance(segment, dict):
            continue

        score_raw = segment.get("score", 1.0)
        try:
            score = float(score_raw)
        except (TypeError, ValueError):
            score = 1.0
        if score < min_score:
            continue

        label = str(segment.get("label", ""))
        mask_arr = _to_mask_array(segment.get("mask"), rgb.size)
        if mask_arr is None:
            continue
        if int(mask_arr.sum()) < 64:
            continue

        saw_mask = True
        if _is_background_segment_label(label):
            continue

        foreground_mask |= mask_arr

    if not saw_mask:
        return None

    foreground_ratio = float(foreground_mask.mean())
    if foreground_ratio < min_coverage or foreground_ratio > max_coverage:
        return None

    base_arr = np.array(rgb, dtype=np.uint8)
    neutral_rgb = np.median(base_arr.reshape(-1, 3), axis=0).astype(np.uint8)

    foreground_arr = base_arr.copy()
    foreground_arr[~foreground_mask] = neutral_rgb

    background_arr = base_arr.copy()
    background_arr[foreground_mask] = neutral_rgb

    return Image.fromarray(foreground_arr), Image.fromarray(background_arr)


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


def _caption_keyword_tags(caption_text: str) -> List[str]:
    text = re.sub(r"[^a-z0-9\- ]+", " ", str(caption_text).strip().lower())
    tokens = [part for part in text.split() if len(part) >= 3]
    if not tokens:
        return []

    stopwords = {
        "the",
        "with",
        "from",
        "this",
        "that",
        "into",
        "over",
        "under",
        "image",
        "photo",
        "holding",
    }
    allowed_tokens = {
        "flower",
        "lily",
        "petal",
        "bouquet",
        "hand",
        "finger",
        "ring",
        "sky",
        "cloud",
        "sunlight",
        "outdoor",
        "water",
        "pond",
        "macro",
        "portrait",
        "landscape",
    }

    tags: List[str] = []
    for token in tokens:
        if token in stopwords or token not in allowed_tokens:
            continue
        normalized = _normalize_label(token)
        if normalized:
            tags.append(normalized)

    if "blue" in tokens and "sky" in tokens:
        tags.append("blue-sky")
    if "close" in tokens and "up" in tokens:
        tags.append("close-up")

    return _dedupe(tags)


def _normalize_object_label(label: str) -> str:
    text = str(label or "").strip().lower()
    if not text:
        return ""

    if "," in text:
        text = text.split(",", 1)[0].strip()

    mapped = _OBJECT_LABEL_MAP.get(text)
    if mapped:
        text = mapped

    if text.startswith("a "):
        text = text[2:]
    elif text.startswith("an "):
        text = text[3:]

    return _normalize_label(text)


def _extract_object_labels(object_classifier, image) -> Dict[str, float]:
    if object_classifier is None:
        return {}

    top_k = max(3, min(_env_int("PRETRAINED_TAGGER_OBJECT_TOP_K", 8), 20))
    min_score = max(0.05, min(_env_float("PRETRAINED_TAGGER_OBJECT_MIN_SCORE", 0.18), 0.95))

    try:
        predictions = object_classifier(image, top_k=top_k)
    except Exception:
        return {}

    out: Dict[str, float] = {}
    if not isinstance(predictions, list):
        return out

    for item in predictions:
        if not isinstance(item, dict):
            continue
        try:
            score = float(item.get("score", 0.0))
        except (TypeError, ValueError):
            continue
        if score < min_score:
            continue

        label = _normalize_object_label(item.get("label", ""))
        if not label:
            continue
        if label not in _OBJECT_ALLOWED_TAGS:
            continue

        out[label] = max(float(out.get(label, 0.0)), score)

    return out


def _min_score_for_label(label: str, base_threshold: float, caption_semantics: List[str]) -> float:
    minimum = base_threshold
    sensitive_min = max(0.05, min(_env_float("PRETRAINED_TAGGER_SENSITIVE_MIN_SCORE", 0.42), 0.99))
    moon_ungrounded_min = max(sensitive_min, min(_env_float("PRETRAINED_TAGGER_MOON_UNGROUNDED_MIN_SCORE", 0.62), 0.99))

    if label in _SENSITIVE_TAGS:
        minimum = max(minimum, sensitive_min)

    if label == "moon" and "moon" not in caption_semantics:
        minimum = max(minimum, moon_ungrounded_min)

    return minimum


def get_last_backend() -> str:
    return _LAST_BACKEND


def get_active_device() -> str:
    return f"zero-shot={_ZERO_SHOT_DEVICE},caption={_CAPTION_DEVICE},object={_OBJECT_DEVICE},segment={_SEGMENT_DEVICE}"


def get_last_tag_confidences():
    return dict(_LAST_TAG_CONFIDENCES)


def warmup():
    if _get_zero_shot_pipeline() is None:
        raise RuntimeError("Pretrained tagger zero-shot pipeline could not be initialized")
    if _get_caption_pipeline() is None:
        raise RuntimeError("Pretrained tagger caption pipeline could not be initialized")
    _get_object_pipeline()
    _get_segment_pipeline()
    return True


def generate_tags(image):
    """Generate tags from pretrained zero-shot classification outputs only."""
    global _LAST_BACKEND, _LAST_TAG_CONFIDENCES

    classifier = _get_zero_shot_pipeline()
    if classifier is None:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained tagger pipeline could not be initialized")

    captioner = _get_caption_pipeline()
    if captioner is None:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained caption pipeline could not be initialized")

    object_classifier = _get_object_pipeline()

    adaptive_profile = get_adaptive_profile()
    candidate_labels = expand_candidate_labels(_DEFAULT_CANDIDATE_LABELS, adaptive_profile)
    default_label_set = {
        _normalize_label(label)
        for label in _DEFAULT_CANDIDATE_LABELS
        if isinstance(label, str) and _normalize_label(label)
    }

    top_k = max(3, min(_env_int("PRETRAINED_TAGGER_TOP_K", 8), 12))
    threshold = max(0.05, min(_env_float("PRETRAINED_TAGGER_THRESHOLD", 0.18), 0.95))
    caption_agreement_min = max(0.05, min(_env_float("PRETRAINED_TAGGER_CAPTION_AGREEMENT_MIN_SCORE", 0.22), 0.95))
    dynamic_label_min_score = max(0.05, min(_env_float("PRETRAINED_TAGGER_DYNAMIC_LABEL_MIN_SCORE", 0.36), 0.99))

    try:
        full_scores = _predict_label_scores(classifier, image, candidate_labels=candidate_labels, top_k=top_k)
    except Exception as exc:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained tagger inference failed") from exc

    if not full_scores:
        _LAST_BACKEND = "pretrained-error"
        raise RuntimeError("Pretrained tagger returned empty predictions")

    label_scores = dict(full_scores)

    segmenter = _get_segment_pipeline()
    if segmenter is not None:
        split_images = _split_foreground_background(segmenter, image)
        if split_images is not None:
            try:
                foreground_image, background_image = split_images
                foreground_scores = _predict_label_scores(
                    classifier,
                    foreground_image,
                    candidate_labels=candidate_labels,
                    top_k=top_k,
                )
                background_scores = _predict_label_scores(
                    classifier,
                    background_image,
                    candidate_labels=candidate_labels,
                    top_k=top_k,
                )

                full_weight, foreground_weight, background_weight = _normalized_split_weights()
                for label in set(list(full_scores.keys()) + list(foreground_scores.keys()) + list(background_scores.keys())):
                    combined_score = (
                        (full_weight * float(full_scores.get(label, 0.0)))
                        + (foreground_weight * float(foreground_scores.get(label, 0.0)))
                        + (background_weight * float(background_scores.get(label, 0.0)))
                    )
                    label_scores[label] = max(float(label_scores.get(label, 0.0)), combined_score)

                # Preserve at least one strong background/scene descriptor when available.
                background_scene_min = max(0.05, min(_env_float("PRETRAINED_TAGGER_BACKGROUND_SCENE_MIN_SCORE", 0.18), 0.95))
                for label, score in sorted(background_scores.items(), key=lambda row: row[1], reverse=True):
                    if label not in _SCENE_TAG_SET:
                        continue
                    if float(score) < background_scene_min:
                        continue
                    label_scores[label] = max(float(label_scores.get(label, 0.0)), float(score))
                    break
            except Exception:
                pass

    ordered_labels = sorted(label_scores.keys(), key=lambda item: float(label_scores.get(item, 0.0)), reverse=True)
    ordered_labels = ordered_labels[: max(top_k * 3, 18)]

    object_scores = _extract_object_labels(object_classifier, image)
    object_labels = set(object_scores.keys())
    for label, score in object_scores.items():
        label_scores[label] = max(float(label_scores.get(label, 0.0)), float(score))
        if label not in ordered_labels:
            ordered_labels.append(label)

    caption_text = _extract_caption_text(captioner, image)
    raw_caption_semantics = _dedupe(_caption_tags(caption_text) + _caption_keyword_tags(caption_text))
    caption_direct_confidence = max(0.05, min(_env_float("PRETRAINED_TAGGER_CAPTION_DIRECT_CONFIDENCE", 0.30), 0.95))
    caption_semantics: List[str] = []
    caption_confidences: Dict[str, float] = {}
    for label in raw_caption_semantics:
        score = float(label_scores.get(label, 0.0))
        if score >= caption_agreement_min:
            caption_semantics.append(label)
            caption_confidences[label] = max(score, caption_agreement_min)
            continue

        if label in _SENSITIVE_TAGS:
            continue

        if label in _CAPTION_DIRECT_ALLOWLIST:
            caption_semantics.append(label)
            caption_confidences[label] = caption_direct_confidence

    filtered_labels: List[str] = []
    for label in ordered_labels:
        score = float(label_scores.get(label, 0.0))
        is_adaptive_only = label not in default_label_set and label not in caption_semantics and label not in object_labels
        if is_adaptive_only and score < dynamic_label_min_score:
            continue
        min_required = _min_score_for_label(label, threshold, caption_semantics)
        if score >= min_required:
            filtered_labels.append(label)

    selected = list(filtered_labels)
    if not selected:
        fallback_min = max(0.05, min(_env_float("PRETRAINED_TAGGER_FALLBACK_MIN_SCORE", 0.10), 0.95))
        selected = [label for label in ordered_labels if float(label_scores.get(label, 0.0)) >= fallback_min][:4]

    tags: List[str] = []
    tags.extend(caption_semantics)
    tags.extend(selected)

    tags = _dedupe(tags)

    anchor_min_confidence = max(0.05, min(_env_float("PRETRAINED_TAGGER_ANCHOR_MIN_CONFIDENCE", 0.22), 0.95))
    anchor_tags: List[str] = []
    for tag in tags:
        if tag in caption_semantics:
            anchor_tags.append(tag)
            continue
        if float(label_scores.get(tag, 0.0)) >= anchor_min_confidence:
            anchor_tags.append(tag)

    ranking_confidences = dict(label_scores)
    for label, score in caption_confidences.items():
        ranking_confidences[label] = max(float(ranking_confidences.get(label, 0.0)), float(score))

    reranked = rerank_tags_with_profile(tags, adaptive_profile, tag_confidences=ranking_confidences)
    if anchor_tags:
        anchored: List[str] = []
        seen = set()
        for tag in anchor_tags:
            if tag in seen:
                continue
            if tag not in reranked:
                continue
            seen.add(tag)
            anchored.append(tag)
        for tag in reranked:
            if tag in seen:
                continue
            seen.add(tag)
            anchored.append(tag)
        tags = anchored
    else:
        tags = reranked
    if len(tags) < 1:
        if ordered_labels:
            strongest = ordered_labels[0]
            strongest_score = float(label_scores.get(strongest, 0.0))
            hard_fallback_min = max(0.05, min(_env_float("PRETRAINED_TAGGER_HARD_FALLBACK_MIN_SCORE", 0.10), 0.95))
            if strongest_score >= hard_fallback_min:
                tags = [strongest]

    if len(tags) < 1:
        _LAST_TAG_CONFIDENCES = {}
        _LAST_BACKEND = "pretrained"
        return []

    confidences = {}
    for tag in tags[:10]:
        raw_conf = float(label_scores.get(tag, 0.0))
        if tag in caption_confidences:
            raw_conf = max(raw_conf, float(caption_confidences.get(tag, 0.0)))
        confidences[tag] = round(max(0.0, min(raw_conf, 1.0)), 4)

    _LAST_TAG_CONFIDENCES = confidences

    _LAST_BACKEND = "pretrained"
    return tags[:10]
