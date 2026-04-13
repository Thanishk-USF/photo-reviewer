"""Benchmark inference quality/latency across CPU/GPU device modes.

Examples:
  python backend/scripts/benchmark_device_modes.py --images backend/uploads/originals --modes cpu,auto
  python backend/scripts/benchmark_device_modes.py --single-mode --mode cpu --images backend/uploads/originals
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List

from PIL import Image

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"

_VALID_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def _percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    if q <= 0:
        return float(values[0])
    if q >= 1:
        return float(values[-1])

    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    weight = pos - lo
    return float(ordered[lo] * (1.0 - weight) + ordered[hi] * weight)


def _collect_images(path: Path, limit: int) -> List[Path]:
    if not path.exists():
        return []

    files = [
        candidate
        for candidate in sorted(path.rglob("*"))
        if candidate.is_file() and candidate.suffix.lower() in _VALID_EXTS
    ]

    bounded_limit = max(1, int(limit))
    return files[:bounded_limit]


def _evaluate_gates(metrics: Dict[str, float], args) -> Dict[str, Dict[str, object]]:
    gates = {
        "p95Ms": {
            "ok": float(metrics.get("p95Ms", 0.0)) <= float(args.max_p95_ms),
            "value": float(metrics.get("p95Ms", 0.0)),
            "limit": float(args.max_p95_ms),
            "operator": "<=",
        },
        "failureRate": {
            "ok": float(metrics.get("failureRate", 1.0)) <= float(args.max_failure_rate),
            "value": float(metrics.get("failureRate", 1.0)),
            "limit": float(args.max_failure_rate),
            "operator": "<=",
        },
        "emptyTagRate": {
            "ok": float(metrics.get("emptyTagRate", 1.0)) <= float(args.max_empty_tag_rate),
            "value": float(metrics.get("emptyTagRate", 1.0)),
            "limit": float(args.max_empty_tag_rate),
            "operator": "<=",
        },
        "avgSuggestionCount": {
            "ok": float(metrics.get("avgSuggestionCount", 0.0)) >= float(args.min_avg_suggestions),
            "value": float(metrics.get("avgSuggestionCount", 0.0)),
            "limit": float(args.min_avg_suggestions),
            "operator": ">=",
        },
    }
    return gates


def _run_single_mode(args) -> Dict[str, object]:
    os.environ["PRETRAINED_DEVICE_MODE"] = str(args.mode).strip().lower()

    # Late imports so mode env is applied before model initialization.
    sys.path.insert(0, str(BACKEND_DIR))
    from app import create_app
    from app.models.runtime import analyze_image_runtime
    from app.services.model_warmup import warmup_models

    images_root = Path(args.images)
    if not images_root.is_absolute():
        images_root = (ROOT_DIR / images_root).resolve()

    images = _collect_images(images_root, args.limit)
    if not images:
        raise RuntimeError(f"No images found for benchmark at: {images_root}")

    app = create_app()

    if args.warmup:
        warmup_models(app.config, run_inference=False)

    latencies_ms: List[float] = []
    success_count = 0
    failure_count = 0
    empty_tag_count = 0
    suggestion_counts: List[int] = []
    tag_counts: List[int] = []
    aesthetic_sources: Dict[str, int] = {}

    for _ in range(max(1, int(args.iterations))):
        for image_path in images:
            start = time.perf_counter()
            try:
                with Image.open(image_path) as opened:
                    image = opened.convert("RGB")
                    runtime_result = analyze_image_runtime(image, image_path.name, app.config)
            except Exception:
                failure_count += 1
                continue
            finally:
                elapsed = (time.perf_counter() - start) * 1000.0
                latencies_ms.append(float(elapsed))

            success_count += 1
            tags = runtime_result.get("tags", []) or []
            suggestions = runtime_result.get("suggestions", []) or []
            if len(tags) == 0:
                empty_tag_count += 1
            tag_counts.append(len(tags))
            suggestion_counts.append(len(suggestions))

            runtime_meta = runtime_result.get("_runtime", {}) or {}
            aesthetic_source = str(runtime_meta.get("aesthetic_source", "unknown"))
            aesthetic_sources[aesthetic_source] = int(aesthetic_sources.get(aesthetic_source, 0)) + 1

    total = max(1, len(latencies_ms))
    mean_ms = float(statistics.fmean(latencies_ms)) if latencies_ms else 0.0
    p50_ms = _percentile(latencies_ms, 0.50)
    p95_ms = _percentile(latencies_ms, 0.95)
    p99_ms = _percentile(latencies_ms, 0.99)

    metrics = {
        "mode": str(args.mode).strip().lower(),
        "imageCount": len(images),
        "iterationCount": max(1, int(args.iterations)),
        "sampleCount": int(total),
        "successCount": int(success_count),
        "failureCount": int(failure_count),
        "failureRate": round(float(failure_count) / float(total), 4),
        "meanMs": round(mean_ms, 2),
        "p50Ms": round(p50_ms, 2),
        "p95Ms": round(p95_ms, 2),
        "p99Ms": round(p99_ms, 2),
        "emptyTagRate": round(float(empty_tag_count) / float(max(1, success_count)), 4),
        "avgTagCount": round(float(statistics.fmean(tag_counts)) if tag_counts else 0.0, 3),
        "avgSuggestionCount": round(float(statistics.fmean(suggestion_counts)) if suggestion_counts else 0.0, 3),
        "aestheticSourceCounts": aesthetic_sources,
    }

    gates = _evaluate_gates(metrics, args)
    passed = all(bool(item.get("ok")) for item in gates.values())

    return {
        "passed": bool(passed),
        "metrics": metrics,
        "gates": gates,
    }


def _run_compare_modes(args) -> Dict[str, object]:
    modes = [item.strip().lower() for item in str(args.modes).split(",") if item.strip()]
    if not modes:
        raise RuntimeError("No benchmark modes provided")

    results = {}
    failures = []

    for mode in modes:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{mode}.json") as tmp:
            tmp_path = Path(tmp.name)

        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--single-mode",
            "--mode",
            mode,
            "--images",
            str(args.images),
            "--limit",
            str(args.limit),
            "--iterations",
            str(args.iterations),
            "--max-p95-ms",
            str(args.max_p95_ms),
            "--max-failure-rate",
            str(args.max_failure_rate),
            "--max-empty-tag-rate",
            str(args.max_empty_tag_rate),
            "--min-avg-suggestions",
            str(args.min_avg_suggestions),
            "--json-output",
            str(tmp_path),
        ]
        if args.warmup:
            cmd.append("--warmup")

        proc = subprocess.run(
            cmd,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
        )

        try:
            payload = json.loads(tmp_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {
                "passed": False,
                "error": "Failed to parse benchmark output",
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }

        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

        payload["exitCode"] = int(proc.returncode)
        results[mode] = payload

        if int(proc.returncode) not in {0, 2}:
            failures.append({"mode": mode, "error": "benchmark process failed", "stderr": proc.stderr})

    compare = {
        "cpuVsOthers": {},
    }

    cpu_metrics = (results.get("cpu") or {}).get("metrics") or {}
    cpu_p95 = float(cpu_metrics.get("p95Ms", 0.0) or 0.0)

    if cpu_p95 > 0.0:
        for mode, payload in results.items():
            if mode == "cpu":
                continue
            target_metrics = payload.get("metrics") or {}
            target_p95 = float(target_metrics.get("p95Ms", 0.0) or 0.0)
            if target_p95 > 0.0:
                compare["cpuVsOthers"][mode] = {
                    "p95SpeedupX": round(cpu_p95 / target_p95, 3),
                    "cpuP95Ms": round(cpu_p95, 2),
                    "targetP95Ms": round(target_p95, 2),
                }

    all_passed = all(bool((payload or {}).get("passed")) for payload in results.values()) and not failures

    summary = {
        "passed": bool(all_passed),
        "modes": results,
        "comparison": compare,
        "processFailures": failures,
    }

    return summary


def _create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark model inference across device modes")
    parser.add_argument("--images", required=True, help="Image directory (absolute or repo-relative)")
    parser.add_argument("--limit", type=int, default=20, help="Max images per run")
    parser.add_argument("--iterations", type=int, default=1, help="How many full passes over image set")
    parser.add_argument("--warmup", action="store_true", help="Run model warmup before measuring")

    parser.add_argument("--single-mode", action="store_true", help="Run only one mode in this process")
    parser.add_argument("--mode", default="auto", help="Single mode: cpu, auto, or cuda")
    parser.add_argument("--modes", default="cpu,auto", help="Compare modes list for orchestrated run")

    parser.add_argument("--max-p95-ms", type=float, default=5000.0)
    parser.add_argument("--max-failure-rate", type=float, default=0.05)
    parser.add_argument("--max-empty-tag-rate", type=float, default=0.40)
    parser.add_argument("--min-avg-suggestions", type=float, default=2.0)

    parser.add_argument("--json-output", default="", help="Optional output file path for JSON results")
    return parser


def main() -> int:
    args = _create_arg_parser().parse_args()

    if args.single_mode:
        result = _run_single_mode(args)
    else:
        result = _run_compare_modes(args)

    rendered = json.dumps(result, indent=2)
    if args.json_output:
        output_path = Path(args.json_output)
        output_path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)

    return 0 if bool(result.get("passed")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
