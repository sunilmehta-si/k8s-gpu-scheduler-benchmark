"""Repeat a comparison over many seeded traces, so a conclusion rests on a distribution rather than one sample."""
from __future__ import annotations

import statistics

from . import __version__, metrics
from .fleet import Fleet
from .generate import TraceSpec, generate
from .presets import equal_quotas, preset
from .sim import simulate

# (key in the sweep, extractor from one simulation's metrics, lower_is_better)
METRICS = {
    "makespan_h": (lambda c, f, fa, co: c["makespan_h"], True),
    "useful_utilisation": (lambda c, f, fa, co: c["useful_utilisation"], False),
    "queue_wait_p95_min": (lambda c, f, fa, co: c["queue_wait"]["p95_min"] or 0.0, True),
    "stranded_gpu_h": (lambda c, f, fa, co: c["stranded_gpu_h"], True),
    "preempted_gpu_h": (lambda c, f, fa, co: c["preempted_gpu_h"], True),
    "cost_per_useful_gpu_h": (lambda c, f, fa, co: co["per_useful_gpu_h"] or 0.0, True),
    "fairness": (lambda c, f, fa, co: fa["jain_service"] or 0.0, False),
}


def _summary(values: list[float]) -> dict:
    return {"mean": round(statistics.fmean(values), 4), "stdev": round(statistics.pstdev(values), 4),
            "min": round(min(values), 4), "max": round(max(values), 4)}


def run_sweep(fleet: Fleet, stacks: list[str], seeds: list[int], rate: float, hours: float = 8.0,
              quotas: str = "equal", max_job_share: float = 0.5) -> dict:
    per_seed: list[dict] = []
    for seed in seeds:
        jobs = generate(TraceSpec(hours=hours, jobs_per_hour=rate, seed=seed, max_gpus_per_node=fleet.max_gpus_per_node,
                                  max_job_gpus=max(1, int(fleet.total_gpus * max_job_share))))
        shares = equal_quotas([j.team for j in jobs]) if quotas == "equal" else {}
        row = {"seed": seed, "jobs": len(jobs), "stacks": {}}
        for stack in stacks:
            r = simulate(fleet, jobs, preset(stack, shares))
            core, frag, fair, cost = metrics.core(r), metrics.fragmentation(r), metrics.fairness(r), metrics.cost(r)
            row["stacks"][stack] = {k: fn(core, frag, fair, cost) for k, (fn, _) in METRICS.items()}
        per_seed.append(row)
    summary = {stack: {k: _summary([row["stacks"][stack][k] for row in per_seed]) for k in METRICS} for stack in stacks}
    wins = {stack: 0 for stack in stacks}
    for row in per_seed:
        best = min(row["stacks"][s]["cost_per_useful_gpu_h"] for s in stacks)
        for s in stacks:
            if row["stacks"][s]["cost_per_useful_gpu_h"] == best:
                wins[s] += 1
    return {"schema_version": 1, "tool_version": __version__, "mode": "simulation-sweep",
            "fleet": {"name": fleet.name, "gpus": fleet.total_gpus}, "rate_per_hour": rate, "hours": hours,
            "seeds": seeds, "quotas": quotas, "summary": summary, "cheapest_wins": wins, "per_seed": per_seed}


def load_curve(fleet: Fleet, stacks: list[str], seeds: list[int], rates: list[float], hours: float = 8.0,
               quotas: str = "equal") -> dict:
    """The same multi-seed comparison at several arrival rates: how each stack degrades as the fleet gets busier."""
    points = []
    for rate in rates:
        sweep = run_sweep(fleet, stacks, seeds, rate, hours, quotas)
        points.append({"rate_per_hour": rate,
                       "summary": {s: {k: v["mean"] for k, v in sweep["summary"][s].items()} for s in stacks},
                       "cheapest_wins": sweep["cheapest_wins"]})
    return {"schema_version": 1, "tool_version": __version__, "mode": "simulation-load-curve",
            "fleet": {"name": fleet.name, "gpus": fleet.total_gpus}, "hours": hours, "seeds": seeds, "quotas": quotas,
            "points": points}
