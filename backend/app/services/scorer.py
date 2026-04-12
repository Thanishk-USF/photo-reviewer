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

def score_image(image):
    """
    Score an image for aesthetic and technical quality based on actual image properties
    
    Args:
        image: PIL Image object
        
    Returns:
        Tuple of (aesthetic_score, technical_score, composition, lighting, color)
    """
    # Convert to RGB if not already.
    if image.mode != 'RGB':
        image = image.convert('RGB')

    rgb = np.asarray(image, dtype=np.float32) / 255.0
    r = rgb[:, :, 0]
    g = rgb[:, :, 1]
    b = rgb[:, :, 2]

    # Relative luminance approximation and tonal spread.
    luma = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
    mean_luma = float(np.mean(luma))
    std_luma = float(np.std(luma))
    p5, p95 = np.percentile(luma, [5, 95])
    dynamic_range = float(p95 - p5)

    # Gradient-based detail/sharpness proxies.
    grad_y, grad_x = np.gradient(luma)
    grad_mag = np.sqrt((grad_x * grad_x) + (grad_y * grad_y))
    sharpness_score = _clamp01(float(np.var(grad_mag)) / 0.02)

    # Exposure and contrast are best around moderate targets.
    exposure_score = _gaussian_preference(mean_luma, target=0.48, sigma=0.22)
    contrast_score = _gaussian_preference(std_luma, target=0.22, sigma=0.12)
    dynamic_range_score = _clamp01(dynamic_range / 0.8)

    # Saturation and color-balance proxies.
    max_channel = np.max(rgb, axis=2)
    min_channel = np.min(rgb, axis=2)
    saturation = np.where(max_channel > 1e-6, (max_channel - min_channel) / (max_channel + 1e-6), 0.0)
    saturation_mean = float(np.mean(saturation))
    saturation_score = _gaussian_preference(saturation_mean, target=0.30, sigma=0.20)

    channel_means = np.array([float(np.mean(r)), float(np.mean(g)), float(np.mean(b))], dtype=np.float32)
    color_cast = float(np.max(channel_means) - np.min(channel_means))
    color_balance_score = 1.0 - _clamp01(color_cast / 0.35)

    # Composition proxy based on weighted detail centroid near rule-of-thirds points.
    height, width = luma.shape
    y_idx, x_idx = np.indices((height, width), dtype=np.float32)
    weights = grad_mag + 1e-6
    center_x = float(np.sum(x_idx * weights) / np.sum(weights)) / max(float(width - 1), 1.0)
    center_y = float(np.sum(y_idx * weights) / np.sum(weights)) / max(float(height - 1), 1.0)

    thirds_points = ((1.0 / 3.0, 1.0 / 3.0), (2.0 / 3.0, 1.0 / 3.0), (1.0 / 3.0, 2.0 / 3.0), (2.0 / 3.0, 2.0 / 3.0))
    thirds_distance = min(
        math.sqrt(((center_x - tx) ** 2) + ((center_y - ty) ** 2))
        for tx, ty in thirds_points
    )
    thirds_score = 1.0 - _clamp01(thirds_distance / 0.75)

    # Symmetry-like balance using detail energy distribution across halves.
    left_energy = float(np.sum(weights[:, : width // 2]))
    right_energy = float(np.sum(weights[:, width // 2 :]))
    top_energy = float(np.sum(weights[: height // 2, :]))
    bottom_energy = float(np.sum(weights[height // 2 :, :]))
    horizontal_balance = 1.0 - _clamp01(abs(left_energy - right_energy) / max(left_energy + right_energy, 1e-6))
    vertical_balance = 1.0 - _clamp01(abs(top_energy - bottom_energy) / max(top_energy + bottom_energy, 1e-6))
    balance_score = (horizontal_balance + vertical_balance) / 2.0
    composition_score = _clamp01((0.6 * thirds_score) + (0.4 * balance_score))

    lighting_score = _clamp01((0.45 * exposure_score) + (0.35 * contrast_score) + (0.20 * dynamic_range_score))
    color_score = _clamp01((0.55 * saturation_score) + (0.45 * color_balance_score))
    technical_score_norm = _clamp01((0.50 * sharpness_score) + (0.30 * dynamic_range_score) + (0.20 * contrast_score))
    aesthetic_score_norm = _clamp01((0.35 * composition_score) + (0.30 * color_score) + (0.20 * lighting_score) + (0.15 * technical_score_norm))

    return (
        _to_1_10(aesthetic_score_norm),
        _to_1_10(technical_score_norm),
        _to_1_10(composition_score),
        _to_1_10(lighting_score),
        _to_1_10(color_score),
    )