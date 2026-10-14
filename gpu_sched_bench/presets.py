"""Policy presets that model each scheduling stack's *documented default behaviour*.

These are models, not the schedulers. Each line below names the behaviour and where it comes from, so a
reader can disagree with a specific choice instead of with a black box. Cluster runs of the real
schedulers are the check on these models.

- default: kube-scheduler with the NVIDIA device plugin. Pods are scheduled one at a time (no gang),
  NodeResourcesFit scores with LeastAllocated (spread), unschedulable pods are skipped. No quotas.
- kueue: Kueue admits whole workloads against ClusterQueue quotas (all-or-nothing admission; with
  waitForPodsReady a workload that can't get all its pods is evicted, which this models as gang placement),
  BestEffortFIFO queueing, cohort borrowing, and reclaimWithinCohort preemption. Pods are then placed by
  kube-scheduler, so placement is spread.
- volcano: gang plugin (minAvailable), binpack plugin, proportion plugin for queue shares with borrowing
  of idle capacity. Reclaim is configurable but off in the default action list, so it is off here.
- kai: KAI Scheduler gang scheduling of pod groups, bin-packing by default, hierarchical queues with
  fair-share over quota and reclaim of borrowed resources.
"""
from __future__ import annotations

from .sim import Policy

STACKS = ("default", "kueue", "volcano", "kai")


def preset(name: str, quotas: dict[str, float] | None = None) -> Policy:
    """`quotas` are team shares of the fleet; stacks that support quotas get them, the default stack ignores them."""
    q = dict(quotas or {})
    if name == "default":
        return Policy("default", placement="spread", queue="best-effort", gang=False)
    if name == "kueue":
        return Policy("kueue", placement="spread", queue="best-effort", gang=True, quotas=q, borrowing=bool(q),
                      reclaim=bool(q))
    if name == "volcano":
        return Policy("volcano", placement="binpack", queue="best-effort", gang=True, quotas=q, borrowing=bool(q))
    if name == "kai":
        return Policy("kai", placement="binpack", queue="best-effort", gang=True, quotas=q, borrowing=bool(q),
                      reclaim=bool(q))
    raise ValueError(f"unknown stack '{name}'; choose from {', '.join(STACKS)}")


def equal_quotas(teams: list[str]) -> dict[str, float]:
    """An equal share of the fleet for each team, the usual starting point for a shared platform."""
    teams = sorted(set(teams))
    return {t: 1.0 / len(teams) for t in teams} if teams else {}
