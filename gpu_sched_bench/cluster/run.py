"""Run one stack on a cluster: create kwok GPU nodes, apply the stack's queues, replay the trace, wait, collect."""
from __future__ import annotations

import time
from typing import Callable

import yaml

from .. import kwok, manifests, results
from ..fleet import Fleet
from ..trace import Job
from .check import runtime_check
from .collect import collect
from .replay import plan, replay
from .result import to_result


def run_cluster(kube, fleet: Fleet, jobs: list[Job], stack: str, shares: dict[str, float], speedup: float,
                timeout_s: float = 1800.0, poll_s: float = 5.0, trace_name: str = "",
                clock: Callable[[], float] = time.time, sleep: Callable[[float], None] = time.sleep,
                log: Callable[[str], None] = lambda msg: None) -> dict:
    kube.apply(kwok.render(fleet))
    log(f"created {len(fleet.nodes)} kwok nodes ({fleet.total_gpus} GPUs)")
    setup = manifests.render(stack, fleet, jobs, shares, speedup, part="setup")
    kube.apply(yaml.safe_dump_all(setup, sort_keys=False))
    log(f"applied {len(setup)} setup objects for {stack}")
    docs = {d["metadata"]["name"]: d for d in manifests.render(stack, fleet, jobs, shares, speedup, part="jobs")}
    replay_start = clock()
    replay(kube, docs, plan(jobs, speedup), clock=clock, sleep=sleep, log=log)
    expected = sum(j.replicas for j in jobs)
    deadline = replay_start + timeout_s
    runs = collect(kube)
    while sum(1 for r in runs if r.finished_at is not None) < expected and clock() < deadline:
        sleep(poll_s)
        runs = collect(kube)
    done = sum(1 for r in runs if r.finished_at is not None)
    log(f"{done}/{expected} pods finished" + ("" if done == expected else " before the timeout"))
    check = runtime_check(jobs, runs, speedup)
    log(f"runtime check: {'ok' if check['ok'] else 'FAILED'} ({check.get('median_ratio', '-')}x expected over "
        f"{check['pods_checked']} pods) {check['reason']}".rstrip())
    result = to_result(fleet, jobs, runs, stack, replay_start, speedup, collected_at=clock())
    doc = results.document(fleet, jobs, shares, trace_name, "cluster")
    doc["speedup"] = speedup
    doc["runtime_check"] = check
    doc["stacks"][stack] = results.summarize(result, {"name": stack, "source": "cluster"})
    return doc
