"""Results file: every stack's metrics for one fleet and trace, in one deterministic JSON document.

No timestamps or host details are written, so the same inputs always give byte-identical results and
committed results can be checked in CI.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from . import __version__, metrics
from .fleet import Fleet
from .presets import equal_quotas, preset
from .sim import simulate
from .trace import Job

SCHEMA_VERSION = 1


def run(fleet: Fleet, jobs: list[Job], stacks: list[str], quotas: str = "equal", trace_name: str = "") -> dict:
    shares = equal_quotas([j.team for j in jobs]) if quotas == "equal" else {}
    out = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": __version__,
        "mode": "simulation",   # reference model of documented behaviour; cluster runs will say "cluster"
        "fleet": {"name": fleet.name, "nodes": len(fleet.nodes), "gpus": fleet.total_gpus,
                  "pools": [{"name": p.name, "nodes": p.count, "gpus_per_node": p.gpus_per_node, "gpu_model": p.gpu_model,
                             "price_per_gpu_hour": p.price_per_gpu_hour} for p in fleet.pools]},
        "trace": {"name": trace_name, "jobs": len(jobs), "requested_gpu_h": round(sum(j.gpu_seconds for j in jobs) / 3600, 1)},
        "quotas": shares,
        "stacks": {},
    }
    for stack in stacks:
        policy = preset(stack, shares)
        result = simulate(fleet, jobs, policy)
        p = asdict(policy)
        out["stacks"][stack] = {"policy": p, **metrics.core(result), "fragmentation": metrics.fragmentation(result),
                                "fairness": metrics.fairness(result), "cost": metrics.cost(result)}
    return out


def dumps(results: dict) -> str:
    return json.dumps(results, indent=2, sort_keys=False) + "\n"
