"""
Model-backed tag generator adapter.
"""

from __future__ import annotations

from typing import List

import numpy as np


def _image_features(image):
    if image.mode != "RGB":
        image = image.convert("RGB")

    rgb = np.asarray(image, dtype=np.float32) / 255.0
    r = rgb[:, :, 0]
    g = rgb[:, :, 1]
    b = rgb[:, :, 2]

    luma = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
    brightness = float(np.mean(luma))
    contrast = float(np.std(luma))

    max_channel = np.max(rgb, axis=2)
    min_channel = np.min(rgb, axis=2)
    saturation = np.where(max_channel > 1e-6, (max_channel - min_channel) / (max_channel + 1e-6), 0.0)
    saturation_mean = float(np.mean(saturation))

    height, width = luma.shape
    aspect_ratio = float(width) / max(float(height), 1.0)

    channel_means = np.array([float(np.mean(r)), float(np.mean(g)), float(np.mean(b))], dtype=np.float32)
    dominant_channel = int(np.argmax(channel_means))

    return brightness, contrast, saturation_mean, aspect_ratio, dominant_channel


def _dedupe(values: List[str]) -> List[str]:
    out = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def generate_tags(image):
    """
    Generate stable tags from image features.

    This adapter intentionally avoids random output so runtime behavior is
    deterministic before heavy pretrained dependencies are introduced.
    """
    brightness, contrast, saturation, aspect_ratio, dominant_channel = _image_features(image)

    tags: List[str] = ["photo"]

    if aspect_ratio > 1.25:
        tags.append("landscape")
    elif aspect_ratio < 0.80:
        tags.append("portrait")

    if brightness < 0.30:
        tags.extend(["dark", "low-light"])
    elif brightness > 0.72:
        tags.extend(["bright", "high-key"])

    if saturation < 0.12:
        tags.append("monochrome")
    elif saturation > 0.33:
        tags.extend(["colorful", "vivid"])

    if contrast > 0.22:
        tags.append("high-contrast")
    elif contrast < 0.11:
        tags.append("soft-contrast")

    if dominant_channel == 0:
        tags.append("warm-tones")
    elif dominant_channel == 2:
        tags.append("cool-tones")
    else:
        tags.append("balanced-tones")

    return _dedupe(tags)[:10]
