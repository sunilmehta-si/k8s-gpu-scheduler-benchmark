"""Turn a simulation result into the numbers platform teams compare schedulers on."""
from __future__ import annotations

import math

from .sim import Result


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile; None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def _wait_summary(waits: list[float]) -> dict:
    return {"jobs": len(waits),
            "p50_min": _min(percentile(waits, 50)), "p95_min": _min(percentile(waits, 95)), "max_min": _min(max(waits, default=None))}


def _min(seconds: float | None) -> float | None:
    return None if seconds is None else round(seconds / 60, 1)


def core(result: Result) -> dict:
    capacity = result.fleet.total_gpus * result.makespan
    finished = [r for r in result.records.values() if r.end is not None]
    waits = [r.wait for r in result.records.values() if r.wait is not None]
    by_kind: dict[str, list[float]] = {}
    for r in result.records.values():
        if r.wait is not None:
            by_kind.setdefault(r.job.kind, []).append(r.wait)
    return {
        "makespan_h": round(result.makespan / 3600, 2),
        "jobs": len(result.records),
        "jobs_finished": len(finished),
        "deadlocked": result.deadlocked,
        "utilisation": round(result.allocated_gpu_s / capacity, 4) if capacity else 0.0,
        # GPUs doing work: excludes GPUs held by half-placed gangs, which are allocated but idle
        "useful_utilisation": round((result.allocated_gpu_s - result.stranded_gpu_s) / capacity, 4) if capacity else 0.0,
        "stranded_gpu_h": round(result.stranded_gpu_s / 3600, 1),
        "preempted_gpu_h": round(result.preempted_gpu_s / 3600, 1),
        "queue_wait": _wait_summary(waits),
        "queue_wait_by_kind": {k: _wait_summary(v) for k, v in sorted(by_kind.items())},
    }
