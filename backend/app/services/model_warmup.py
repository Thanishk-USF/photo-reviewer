"""Model warmup orchestration for startup and admin diagnostics."""

from __future__ import annotations

import time
from typing import Any, Dict

from PIL import Image

from app.models import nima_scorer
from app.models import scorer
from app.models import style
from app.models import suggester
from app.models import tagger


def _is_enabled(config: Dict[str, Any], name: str, default: bool = True) -> bool:
    value = config.get(name, default)
    return bool(value)


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


def _model_result(ok: bool, elapsed_ms: float, **extra):
    payload = {
        "ok": bool(ok),
        "elapsedMs": round(float(elapsed_ms), 2),
    }
    payload.update(extra)
    return payload


def warmup_models(config: Dict[str, Any], run_inference: bool = False) -> Dict[str, Any]:
    """Warm up enabled model adapters and optionally run one sample inference pass."""
    started = _now_ms()
    results: Dict[str, Any] = {}

    sample_image = None
    if run_inference:
        sample_image = Image.new("RGB", (224, 224), (127, 127, 127))

    def invoke(name: str, fn):
        t0 = _now_ms()
        try:
            fn()
            results[name] = _model_result(True, _now_ms() - t0)
        except Exception as exc:
            results[name] = _model_result(False, _now_ms() - t0, error=str(exc))

    if _is_enabled(config, "USE_PRETRAINED_SCORER", True):
        def _warm_scorer():
            scorer.warmup()
            if sample_image is not None:
                scorer.score_image(sample_image.copy())

        invoke("scorer", _warm_scorer)

    if _is_enabled(config, "USE_PRETRAINED_TAGGER", True):
        def _warm_tagger():
            tagger.warmup()
            if sample_image is not None:
                tagger.generate_tags(sample_image.copy())

        invoke("tagger", _warm_tagger)

    if _is_enabled(config, "USE_PRETRAINED_STYLE", True):
        def _warm_style():
            style.warmup()
            if sample_image is not None:
                style.classify_style(sample_image.copy())

        invoke("style", _warm_style)

    if _is_enabled(config, "USE_PRETRAINED_SUGGESTER", True):
        def _warm_suggester():
            suggester.warmup()
            if sample_image is not None:
                suggester.generate_suggestions(
                    sample_image.copy(),
                    {
                        "aesthetic": 5.5,
                        "technical": 5.5,
                        "composition": 5.5,
                        "lighting": 5.5,
                        "color": 5.5,
                    },
                )

        invoke("suggester", _warm_suggester)

    if _is_enabled(config, "USE_NIMA_AESTHETIC", False):
        def _warm_nima():
            nima_scorer.warmup()
            if sample_image is not None:
                nima_scorer.score_aesthetic(sample_image.copy())

        invoke("nima", _warm_nima)

    any_failed = any(not bool(item.get("ok")) for item in results.values())
    return {
        "ok": not any_failed,
        "runInference": bool(run_inference),
        "models": results,
        "elapsedMs": round(_now_ms() - started, 2),
        "timestamp": int(time.time()),
    }
