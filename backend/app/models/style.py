"""
Style/mood classifier adapter.
"""

from __future__ import annotations

import numpy as np


def _extract_features(image):
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

    grad_y, grad_x = np.gradient(luma)
    edge_strength = float(np.mean(np.sqrt((grad_x * grad_x) + (grad_y * grad_y))))

    return brightness, contrast, saturation_mean, edge_strength


def classify_style(image):
    """
    Classify style and mood with deterministic feature rules.

    This keeps output stable while the pretrained style model path is added.
    """
    brightness, contrast, saturation, edge_strength = _extract_features(image)

    if saturation < 0.12:
        style = "Monochrome"
    elif edge_strength < 0.045 and contrast < 0.15:
        style = "Minimalist"
    elif saturation > 0.30 and contrast > 0.18:
        style = "Vibrant"
    elif contrast > 0.24:
        style = "HDR"
    else:
        style = "Natural"

    if brightness < 0.28 and contrast > 0.16:
        mood = "Dramatic"
    elif brightness < 0.30:
        mood = "Mysterious"
    elif brightness > 0.72 and saturation > 0.24:
        mood = "Joyful"
    elif contrast < 0.12:
        mood = "Calm"
    else:
        mood = "Serene"

    return style, mood
