"""Device selection helpers for model inference pipelines.

Policy:
- Prefer GPU when configured and available.
- Fall back to CPU automatically when initialization fails.
- Keep backward compatibility with legacy PRETRAINED_DEVICE.
"""

from __future__ import annotations

import os
from typing import Dict, List, Tuple


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized in {"cpu", "cuda", "auto"}:
        return normalized
    return "auto"


def _parse_legacy_device(device_value: str) -> int:
    value = str(device_value or "cpu").strip().lower()
    if value in {"cpu", "-1"}:
        return -1
    if value.isdigit():
        return int(value)
    if value.startswith("cuda"):
        if ":" in value:
            _, _, suffix = value.partition(":")
            if suffix.isdigit():
                return int(suffix)
        return 0
    return -1


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _dedupe_candidates(candidates: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    seen = set()
    for index, label in candidates:
        key = (int(index), str(label))
        if key in seen:
            continue
        seen.add(key)
        out.append((int(index), str(label)))
    return out


def get_transformers_device_candidates() -> List[Tuple[int, str]]:
    """Return ordered device candidates for transformers pipeline initialization."""
    mode = _normalize_mode(os.environ.get("PRETRAINED_DEVICE_MODE", "auto"))
    legacy_device = os.environ.get("PRETRAINED_DEVICE")
    cuda_index = max(0, _env_int("PRETRAINED_CUDA_INDEX", 0))

    candidates: List[Tuple[int, str]] = []

    if mode == "cpu":
        candidates.append((-1, "cpu"))
        return candidates

    if legacy_device and mode == "auto":
        legacy_index = _parse_legacy_device(legacy_device)
        if legacy_index >= 0:
            candidates.append((legacy_index, f"cuda:{legacy_index}"))
            candidates.append((-1, "cpu"))
            return _dedupe_candidates(candidates)
        candidates.append((-1, "cpu"))
        return candidates

    if _cuda_available():
        candidates.append((cuda_index, f"cuda:{cuda_index}"))

    # Even in cuda mode, keep a CPU fallback to preserve service availability.
    candidates.append((-1, "cpu"))

    return _dedupe_candidates(candidates)


def get_device_policy_snapshot() -> Dict[str, object]:
    candidates = get_transformers_device_candidates()
    primary_index, primary_label = candidates[0]
    return {
        "mode": _normalize_mode(os.environ.get("PRETRAINED_DEVICE_MODE", "auto")),
        "legacyDevice": str(os.environ.get("PRETRAINED_DEVICE", "")).strip() or None,
        "cudaIndex": max(0, _env_int("PRETRAINED_CUDA_INDEX", 0)),
        "primaryDevice": primary_label,
        "primaryDeviceIndex": int(primary_index),
        "fallbackDevices": [label for _, label in candidates[1:]],
    }


def build_transformers_pipeline(task: str, model_id: str, **kwargs):
    """Build a transformers pipeline by trying preferred device candidates in order."""
    from transformers import pipeline

    last_error = None
    attempts = get_transformers_device_candidates()

    for device_index, device_label in attempts:
        try:
            instance = pipeline(task, model=model_id, device=device_index, **kwargs)
            return instance, device_label
        except Exception as exc:
            last_error = exc
            continue

    attempted_labels = ", ".join(label for _, label in attempts)
    raise RuntimeError(
        f"Failed to initialize '{task}' model '{model_id}' on devices: {attempted_labels}"
    ) from last_error
