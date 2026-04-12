"""Image scoring module for the Flask application."""
import math
import numpy as np


def _clamp01(value):
    return max(0.0, min(float(value), 1.0))


def _to_1_10(normalized_value):
    return round(1 + (_clamp01(normalized_value) * 9), 1)


def _gaussian_preference(value, target, sigma):
    if sigma <= 0:
        return 0.0
    z = (value - target) / sigma
    return _clamp01(math.exp(-0.5 * z * z))


def _normalized_entropy(values):
    total = float(np.sum(values))
    if total <= 1e-12:
        return 0.0

    p = (values / total).astype(np.float64)
    p = p[p > 0]
    if p.size <= 1:
        return 0.0

    entropy = -float(np.sum(p * np.log(p + 1e-12)))
    max_entropy = math.log(float(p.size))
    if max_entropy <= 1e-12:
        return 0.0
    return _clamp01(entropy / max_entropy)


def analyze_image_quality(image):
    """Return calibrated quality signals and 1-10 scores for an image."""
    if image.mode != "RGB":
        image = image.convert("RGB")

    rgb = np.asarray(image, dtype=np.float32) / 255.0
    r = rgb[:, :, 0]
    g = rgb[:, :, 1]
    b = rgb[:, :, 2]

    luma = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
    mean_luma = float(np.mean(luma))
    std_luma = float(np.std(luma))
    p5, p95 = np.percentile(luma, [5, 95])
    dynamic_range = float(p95 - p5)
    shadow_clip = float(np.mean(luma < 0.03))
    highlight_clip = float(np.mean(luma > 0.97))
    clip_penalty = _clamp01((shadow_clip + highlight_clip) / 0.25)

    max_channel = np.max(rgb, axis=2)
    min_channel = np.min(rgb, axis=2)
    saturation = np.where(max_channel > 1e-6, (max_channel - min_channel) / (max_channel + 1e-6), 0.0)
    saturation_mean = float(np.mean(saturation))

    rg = r - g
    yb = 0.5 * (r + g) - b
    std_rg = float(np.std(rg))
    std_yb = float(np.std(yb))
    mean_rg = float(np.mean(rg))
    mean_yb = float(np.mean(yb))
    colorfulness = math.sqrt(std_rg * std_rg + std_yb * std_yb) + (0.3 * math.sqrt(mean_rg * mean_rg + mean_yb * mean_yb))

    channel_means = np.array([float(np.mean(r)), float(np.mean(g)), float(np.mean(b))], dtype=np.float32)
    color_cast = float(np.max(channel_means) - np.min(channel_means))
    dominant_channel = int(np.argmax(channel_means))

    grad_y, grad_x = np.gradient(luma)
    grad_mag = np.sqrt((grad_x * grad_x) + (grad_y * grad_y))
    edge_mean = float(np.mean(grad_mag))
    edge_var = float(np.var(grad_mag))
    detail_amount = _clamp01(edge_mean / 0.09)
    detail_entropy = _normalized_entropy(grad_mag.ravel()) if edge_mean > 1e-8 else 0.0

    height, width = luma.shape
    aspect_ratio = float(width) / max(float(height), 1.0)

    if edge_mean <= 1e-8:
        thirds_score = 0.2
        balance_score = 0.5
    else:
        weights = grad_mag
        y_idx, x_idx = np.indices((height, width), dtype=np.float32)
        total_weight = float(np.sum(weights))
        center_x = float(np.sum(x_idx * weights) / total_weight) / max(float(width - 1), 1.0)
        center_y = float(np.sum(y_idx * weights) / total_weight) / max(float(height - 1), 1.0)

        thirds_points = (
            (1.0 / 3.0, 1.0 / 3.0),
            (2.0 / 3.0, 1.0 / 3.0),
            (1.0 / 3.0, 2.0 / 3.0),
            (2.0 / 3.0, 2.0 / 3.0),
        )
        thirds_distance = min(
            math.sqrt(((center_x - tx) ** 2) + ((center_y - ty) ** 2))
            for tx, ty in thirds_points
        )
        thirds_score = 1.0 - _clamp01(thirds_distance / 0.75)

        left_energy = float(np.sum(weights[:, : width // 2]))
        right_energy = float(np.sum(weights[:, width // 2 :]))
        top_energy = float(np.sum(weights[: height // 2, :]))
        bottom_energy = float(np.sum(weights[height // 2 :, :]))
        horizontal_balance = 1.0 - _clamp01(abs(left_energy - right_energy) / max(left_energy + right_energy, 1e-6))
        vertical_balance = 1.0 - _clamp01(abs(top_energy - bottom_energy) / max(top_energy + bottom_energy, 1e-6))
        balance_score = (horizontal_balance + vertical_balance) / 2.0

    composition_score = _clamp01(
        (0.45 * thirds_score)
        + (0.25 * balance_score)
        + (0.15 * detail_amount)
        + (0.15 * detail_entropy)
    )

    exposure_score = _gaussian_preference(mean_luma, target=0.50, sigma=0.24)
    contrast_score = _gaussian_preference(std_luma, target=0.19, sigma=0.12)
    dynamic_range_score = _clamp01(dynamic_range / 0.75)
    lighting_score = _clamp01(
        (0.40 * exposure_score)
        + (0.25 * contrast_score)
        + (0.25 * dynamic_range_score)
        + (0.10 * (1.0 - clip_penalty))
    )

    saturation_score = _clamp01((saturation_mean - 0.03) / 0.42)
    colorfulness_score = _clamp01(colorfulness / 0.45)
    color_balance_score = 1.0 - _clamp01(color_cast / 0.30)
    monochrome_penalty = 0.25 if saturation_mean < 0.08 and colorfulness < 0.10 else 0.0
    color_score = _clamp01(
        (0.45 * saturation_score)
        + (0.35 * colorfulness_score)
        + (0.20 * color_balance_score)
        - monochrome_penalty
    )

    edge_mean_score = _clamp01(edge_mean / 0.08)
    edge_var_score = _clamp01(edge_var / 0.015)
    technical_score = _clamp01(
        (0.40 * edge_mean_score)
        + (0.30 * edge_var_score)
        + (0.20 * dynamic_range_score)
        + (0.10 * contrast_score)
    )

    aesthetic_score = _clamp01(
        (0.35 * composition_score)
        + (0.25 * lighting_score)
        + (0.20 * color_score)
        + (0.20 * technical_score)
    )

    return {
        "scores_normalized": {
            "aesthetic": aesthetic_score,
            "technical": technical_score,
            "composition": composition_score,
            "lighting": lighting_score,
            "color": color_score,
        },
        "scores_1_10": {
            "aesthetic": _to_1_10(aesthetic_score),
            "technical": _to_1_10(technical_score),
            "composition": _to_1_10(composition_score),
            "lighting": _to_1_10(lighting_score),
            "color": _to_1_10(color_score),
        },
        "features": {
            "mean_luma": mean_luma,
            "std_luma": std_luma,
            "dynamic_range": dynamic_range,
            "shadow_clip": shadow_clip,
            "highlight_clip": highlight_clip,
            "clip_penalty": clip_penalty,
            "saturation_mean": saturation_mean,
            "colorfulness": colorfulness,
            "color_cast": color_cast,
            "dominant_channel": dominant_channel,
            "edge_mean": edge_mean,
            "edge_var": edge_var,
            "detail_amount": detail_amount,
            "detail_entropy": detail_entropy,
            "aspect_ratio": aspect_ratio,
        },
    }

def score_image(image):
    """
    Score an image for aesthetic and technical quality based on actual image properties
    
    Args:
        image: PIL Image object
        
    Returns:
        Tuple of (aesthetic_score, technical_score, composition, lighting, color)
    """
    quality = analyze_image_quality(image)
    scores = quality["scores_1_10"]

    return (
        scores["aesthetic"],
        scores["technical"],
        scores["composition"],
        scores["lighting"],
        scores["color"],
    )