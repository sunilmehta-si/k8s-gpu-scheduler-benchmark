"""Submit a trace's jobs to the cluster at their arrival times, compressed by a speedup factor."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import yaml

from ..trace import Job


@dataclass(frozen=True)
class Submission:
    job_id: str
    due_s: float        # wall-clock seconds after the replay started
    sent_s: float       # when it was actually applied


def plan(jobs: list[Job], speedup: float) -> list[tuple[float, Job]]:
    """(wall-clock offset, job) in submission order; the first arrival is submitted immediately."""
    if speedup <= 0:
        raise ValueError("speedup must be > 0")
    if not jobs:
        return []
    t0 = min(j.arrival_s for j in jobs)
    return [((j.arrival_s - t0) / speedup, j) for j in sorted(jobs, key=lambda j: (j.arrival_s, j.id))]


def replay(kube, manifests_by_job: dict[str, dict], schedule: list[tuple[float, Job]],
           clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
           log: Callable[[str], None] = lambda msg: None) -> list[Submission]:
    start = clock()
    sent = []
    for due, job in schedule:
        wait = start + due - clock()
        if wait > 0:
            sleep(wait)
        kube.apply(yaml.safe_dump(manifests_by_job[job.id], sort_keys=False))
        sent.append(Submission(job.id, round(due, 3), round(clock() - start, 3)))
        log(f"submitted {job.id} at +{sent[-1].sent_s:.1f}s (due +{due:.1f}s)")
    return sent
