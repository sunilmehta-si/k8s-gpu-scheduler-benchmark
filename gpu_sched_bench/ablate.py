"""Ablation: switch scheduling behaviours on one at a time, so a gain can be attributed to the behaviour behind it."""
from __future__ import annotations

from dataclasses import asdict

from . import results
from .fleet import Fleet
from .presets import equal_quotas
from .sim import Policy, simulate
from .trace import Job


def variants(shares: dict[str, float]) -> list[Policy]:
    """Cumulative steps from the default scheduler towards a quota-aware gang scheduler."""
    steps = [
        Policy("1 default"),
        Policy("2 + gang", gang=True),
        Policy("3 + gang, binpack", gang=True, placement="binpack"),
    ]
    if shares:
        steps += [
            Policy("4 + quotas", gang=True, placement="binpack", quotas=shares),
            Policy("5 + borrowing", gang=True, placement="binpack", quotas=shares, borrowing=True),
            Policy("6 + reclaim", gang=True, placement="binpack", quotas=shares, borrowing=True, reclaim=True),
        ]
    steps.append(Policy("binpack only", placement="binpack"))   # isolates bin-packing without gangs
    return steps


def run_ablation(fleet: Fleet, jobs: list[Job], quotas: str = "equal", trace_name: str = "") -> dict:
    shares = equal_quotas([j.team for j in jobs]) if quotas == "equal" else {}
    doc = results.document(fleet, jobs, shares, trace_name, "simulation")
    doc["ablation"] = True
    for policy in variants(shares):
        doc["stacks"][policy.name] = results.summarize(simulate(fleet, jobs, policy), asdict(policy))
    return doc
