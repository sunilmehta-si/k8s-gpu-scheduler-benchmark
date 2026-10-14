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


def jain(values: list[float]) -> float | None:
    """Jain's fairness index: 1.0 when all values are equal, 1/n when one gets everything."""
    if not values or not any(values):
        return None
    return round(sum(values) ** 2 / (len(values) * sum(v * v for v in values)), 4)


def fairness(result: Result) -> dict:
    """How evenly teams were served: per team, the share of requested GPU-hours that finished, and waits."""
    teams: dict[str, list] = {}
    for r in result.records.values():
        teams.setdefault(r.job.team, []).append(r)
    per_team = {}
    for team, recs in sorted(teams.items()):
        requested = sum(r.job.gpu_seconds for r in recs)
        served = sum(r.job.gpu_seconds for r in recs if r.end is not None)
        waits = [r.wait for r in recs if r.wait is not None]
        per_team[team] = {"jobs": len(recs), "requested_gpu_h": round(requested / 3600, 1),
                          "served_share": round(served / requested, 4) if requested else 1.0,
                          "never_started": sum(1 for r in recs if r.start is None),
                          "preemptions": sum(r.preemptions for r in recs), **_wait_summary(waits)}
    return {"jain_served_share": jain([t["served_share"] for t in per_team.values()]), "teams": per_team}


def cost(result: Result) -> dict:
    """GPU cost from each pool's price per GPU-hour. A replica is billed from placement to its end (or to the
    end of the run if it never finished), so stranded and deadlocked GPUs cost money like working ones."""
    price = {n.name: n.price_per_gpu_hour / 3600 for n in result.fleet.nodes}
    by_team: dict[str, float] = {}
    by_model: dict[str, float] = {}
    allocated = stranded = wasted = 0.0
    for r in result.records.values():
        job_cost = r.billed_before
        wasted += r.wasted_cost
        for node, placed, start, end in zip(r.nodes, r.placed_at, r.replica_start, r.replica_end):
            if node is None:
                continue
            until = end if end is not None else result.makespan
            job_cost += (until - placed) * r.job.gpus_per_replica * price[node]
            stranded += ((start if start is not None else until) - placed) * r.job.gpus_per_replica * price[node]
        allocated += job_cost
        by_team[r.job.team] = by_team.get(r.job.team, 0.0) + job_cost
        model = r.job.model or r.job.kind
        by_model[model] = by_model.get(model, 0.0) + job_cost
    sizes = [n.price_per_gpu_hour / 3600 for n in result.fleet.nodes]
    idle = sum(sum(f * p for f, p in zip(free, sizes)) * dt for _, dt, free, _ in result.samples)
    useful_gpu_h = (result.allocated_gpu_s - result.stranded_gpu_s) / 3600 - result.preempted_gpu_s / 3600
    total = allocated + idle
    return {
        "total": round(total, 2),
        "idle": round(idle, 2),
        "stranded": round(stranded, 2),
        "preempted_work": round(wasted, 2),
        "per_useful_gpu_h": round(total / useful_gpu_h, 3) if useful_gpu_h > 0 else None,
        "by_team": {k: round(v, 2) for k, v in sorted(by_team.items())},
        "by_model": {k: round(v, 2) for k, v in sorted(by_model.items(), key=lambda kv: -kv[1])},
    }
