"""Sanity-check a cluster run: did each fake pod run for its trace duration divided by the speedup?

If kwok's delayed-completion stage is missing or misconfigured, pods finish almost immediately and every number
downstream is meaningless while still looking plausible. This check makes that failure loud.
"""
from __future__ import annotations

import statistics

from ..trace import Job
from .collect import PodRun

TOLERANCE = (0.75, 1.33)   # observed / expected runtime, median over finished pods


def runtime_check(jobs: list[Job], runs: list[PodRun], speedup: float) -> dict:
    expected = {j.id: max(1.0, round(j.duration_s / speedup)) for j in jobs}
    ratios = [(r.finished_at - r.started_at) / expected[r.job_id] for r in runs
              if r.job_id in expected and r.started_at is not None and r.finished_at is not None]
    if not ratios:
        return {"pods_checked": 0, "ok": False, "reason": "no finished pods to check"}
    ratios.sort()
    median = statistics.median(ratios)
    ok = TOLERANCE[0] <= median <= TOLERANCE[1]
    return {"pods_checked": len(ratios), "median_ratio": round(median, 3), "min_ratio": round(ratios[0], 3),
            "max_ratio": round(ratios[-1], 3), "ok": ok,
            "reason": "" if ok else (f"pods ran {median:.2f}x their expected time; check that kwok's pod/general stages "
                                     "(pod-complete with the delay annotation) are installed")}
