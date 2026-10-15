"""Turn collected pod runs into the simulator's Result, so a cluster run is measured by exactly the same metrics code.

Wall-clock times are mapped back to trace time: (t - replay_start) * speedup + first arrival. A gang job's start
is when its last pod started, and its earlier pods count as stranded until then, as in the model. Preemptions are
not visible from final pod state, so preempted work is reported as 0 for cluster runs.
"""
from __future__ import annotations

from ..fleet import Fleet
from ..sim import JobRecord, Policy, Result
from ..trace import Job
from .collect import PodRun


def to_result(fleet: Fleet, jobs: list[Job], runs: list[PodRun], stack: str, replay_start: float, speedup: float,
              collected_at: float | None = None) -> Result:
    t_first = min((j.arrival_s for j in jobs), default=0.0)

    def trace_time(t: float | None) -> float | None:
        return None if t is None else (t - replay_start) * speedup + t_first

    by_job: dict[str, list[PodRun]] = {}
    for r in runs:
        by_job.setdefault(r.job_id, []).append(r)
    records: dict[str, JobRecord] = {}
    for job in jobs:
        n = job.replicas
        rec = JobRecord(job, [None] * n, [None] * n, [None] * n, [None] * n, [None] * n, [job.duration_s] * n)
        pods = sorted(by_job.get(job.id, []), key=lambda r: (r.scheduled_at or float("inf"), r.name))[:n]
        for i, pod in enumerate(pods):
            if pod.node is None:
                continue
            rec.nodes[i] = pod.node
            rec.placed_at[i] = trace_time(pod.scheduled_at)
            rec.replica_start[i] = trace_time(pod.started_at)
            rec.replica_end[i] = trace_time(pod.finished_at)
        if job.gang and None not in rec.replica_start:
            whole = max(rec.replica_start)          # the gang works once its last pod runs
            rec.replica_start = [whole] * n
        records[job.id] = rec

    ends = [e for r in records.values() for e in r.replica_end if e is not None]
    makespan = max(ends + ([trace_time(collected_at)] if collected_at else []) + [t_first])
    allocated = stranded = 0.0
    events: list[tuple[float, str, int]] = []      # (time, node, +gpus allocated / -gpus freed)
    for rec in records.values():
        g = rec.job.gpus_per_replica
        gang_start = rec.start
        for node, placed, end in zip(rec.nodes, rec.placed_at, rec.replica_end):
            if node is None or placed is None:
                continue
            until = end if end is not None else makespan
            allocated += (until - placed) * g
            if rec.job.gang:
                stranded += ((gang_start if gang_start is not None else until) - placed) * g
            events += [(placed, node, g), (until, node, -g)]
    sizes = {n.name: n.gpus for n in fleet.nodes}
    order = [n.name for n in fleet.nodes]
    used = {name: 0 for name in order}
    samples = []
    cuts = sorted({t for t, _, _ in events} | {j.arrival_s for j in jobs} | {makespan})
    events.sort()
    k = 0
    for a, b in zip(cuts, cuts[1:]):
        while k < len(events) and events[k][0] <= a:
            _, node, delta = events[k]
            if node in used:
                used[node] += delta
            k += 1
        waiting = [r.job.gpus_per_replica for r in records.values() if r.job.arrival_s <= a and
                   any(p is None or p > a for p in r.placed_at)]
        samples.append((a, b - a, [sizes[name] - used[name] for name in order], min(waiting, default=0)))
    return Result(policy=Policy(stack), fleet=fleet, records=records, makespan=makespan,
                  allocated_gpu_s=allocated, stranded_gpu_s=stranded, preempted_gpu_s=0.0, deadlocked=False,
                  samples=samples)
