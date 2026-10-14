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


def fragmentation(result: Result) -> dict:
    """Time-weighted fragmentation under three definitions, because "fragmentation" means different things:

    A  stranded_by_size: of the GPUs idle while work waits, the share on nodes with fewer free GPUs than the
       smallest waiting replica needs. These GPUs are idle *because* of fragmentation: the costly kind.
    B  scattered_free: the share of free GPUs that sit on partly used nodes (queue-independent).
    C  partial_nodes: the share of nodes that are partly used (structural, node-level).
    Also: idle_while_waiting_gpu_h, GPU-hours left idle while some job was waiting.
    """
    sizes = [n.gpus for n in result.fleet.nodes]
    idle_wait = unusable = free_total = free_partial = partial_nodes = node_time = 0.0
    for _, dt, free, need in result.samples:
        free_total += sum(free) * dt
        free_partial += sum(f for f, size in zip(free, sizes) if 0 < f < size) * dt
        partial_nodes += sum(1 for f, size in zip(free, sizes) if 0 < f < size) * dt
        node_time += len(free) * dt
        if need:
            idle_wait += sum(free) * dt
            unusable += sum(f for f in free if f < need) * dt
    return {
        "idle_while_waiting_gpu_h": round(idle_wait / 3600, 1),
        "stranded_by_size": round(unusable / idle_wait, 4) if idle_wait else 0.0,
        "scattered_free": round(free_partial / free_total, 4) if free_total else 0.0,
        "partial_nodes": round(partial_nodes / node_time, 4) if node_time else 0.0,
    }
