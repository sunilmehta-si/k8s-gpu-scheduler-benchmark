"""Sanity-check a cluster run: did each fake pod run for its trace duration divided by the speedup, and did it
start as soon as it was bound to a node?

If kwok's delayed-completion stage is missing or misconfigured, pods finish almost immediately; if its pod-ready
stage keeps its default delay, every bound pod holds its GPUs idle for seconds, which the speedup turns into
trace minutes. Either way every number downstream is meaningless while still looking plausible. This check
makes both failures loud.
"""
from __future__ import annotations

import statistics

from ..trace import Job
from .collect import PodRun

TOLERANCE = (0.75, 1.33)   # observed / expected runtime, median over finished pods
MAX_START_LAG_S = 2.0      # wall seconds from bound (PodScheduled) to started, median over started pods


def runtime_check(jobs: list[Job], runs: list[PodRun], speedup: float) -> dict:
    expected = {j.id: max(1.0, round(j.duration_s / speedup)) for j in jobs}
    ratios = [(r.finished_at - r.started_at) / expected[r.job_id] for r in runs
              if r.job_id in expected and r.started_at is not None and r.finished_at is not None]
    if not ratios:
        return {"pods_checked": 0, "ok": False, "reason": "no finished pods to check"}
    ratios.sort()
    median = statistics.median(ratios)
    lags = sorted(r.started_at - r.scheduled_at for r in runs if r.started_at is not None and r.scheduled_at is not None)
    lag = statistics.median(lags) if lags else 0.0
    runtime_ok, lag_ok = TOLERANCE[0] <= median <= TOLERANCE[1], lag <= MAX_START_LAG_S
    reasons = []
    if not runtime_ok:
        reasons.append(f"pods ran {median:.2f}x their expected time; check that kwok's pod/general stages "
                       "(pod-complete with the delay annotation) are installed")
    if not lag_ok:
        reasons.append(f"pods started a median {lag:.1f} s after being bound (x{speedup:g} = {lag * speedup / 60:.0f} trace "
                       "minutes of idle GPUs); check the pod-ready delay annotations")
    return {"pods_checked": len(ratios), "median_ratio": round(median, 3), "min_ratio": round(ratios[0], 3),
            "max_ratio": round(ratios[-1], 3), "median_start_lag_s": round(lag, 2),
            "max_start_lag_s": round(lags[-1], 2) if lags else 0.0, "ok": runtime_ok and lag_ok, "reason": "; ".join(reasons)}
