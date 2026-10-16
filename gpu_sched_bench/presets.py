"""Policy presets that model each scheduling stack's *documented default behaviour*.

These are models, not the schedulers. Each line below names the behaviour and where it comes from, so a
reader can disagree with a specific choice instead of with a black box. Where a behaviour is
configuration rather than a default, the preset matches what `gsb manifests` generates for that stack,
so the model and a cluster run describe the same setup. Cluster runs of the real schedulers are the
check on these models.

- default: kube-scheduler with the NVIDIA device plugin. Pods are scheduled one at a time (no gang),
  unschedulable pods are skipped. No quotas. Pods preempt lower-priority pods anywhere in the cluster (gsb's
  PriorityClasses use PreemptLowerPriority). Placement is random among the nodes that fit: NodeResourcesFit's
  default LeastAllocated strategy scores only cpu and memory (weight 1 each), so GPUs are not scored at all.
  A pod that requests only GPUs counts as kube-scheduler's non-zero default (100m cpu, 200Mi memory), which
  moves a 96-core node's integer score by about one point per ten pods; every feasible node ties, and
  kube-scheduler picks among tied nodes at random. See docs/gpu-scoring.md.
- kueue: Kueue admits whole workloads against ClusterQueue quotas (all-or-nothing admission; with
  waitForPodsReady a workload that can't get all its pods is evicted, which this models as gang placement),
  BestEffortFIFO queueing and cohort borrowing. Reclaim is not a Kueue default (reclaimWithinCohort
  defaults to Never); gsb's ClusterQueues set it to Any, so the preset reclaims, and withinClusterQueue:
  LowerPriority lets a team's higher-priority workloads preempt its own lower-priority ones. Pods are then
  placed by kube-scheduler, so placement is random among feasible nodes, as for default.
- volcano: Volcano v1.16's default scheduler config (installer/volcano-development.yaml): actions enqueue,
  allocate, backfill; plugins priority, gang, conformance, then overcommit, drf, predicates, proportion,
  nodeorder and binpack. Gang via minAvailable; proportion queue shares with borrowing of idle capacity;
  reclaim is not in the default action list, so it is off. The overcommit plugin admits a job only while
  queued demand fits in 1.2x the cluster minus what is in use. Placement is most-pods: binpack's default
  weights cover only cpu and memory (nvidia.com/gpu needs binpack.resources), but Volcano charges a pod with no
  requests 100m cpu, and binpack packs that, so each pod goes to the node already running the most pods,
  whatever its GPU size. nodeorder's least-requested score is an integer that ties across these nodes. The
  real scheduler's placements show it: every notebook and inference pod of the smoke trace went to the same
  H100 node until it was full, which held the 16-GPU training gang back for seven hours. The first cluster
  runs, made when this preset bin-packed GPUs, were 84% slower than it predicted.
Tuned variants: the same stacks configured to bin-pack GPUs, the one setting the defaults leave out.
- default-binpack, kueue-binpack: kube-scheduler with NodeResourcesFit's MostAllocated strategy scoring
  nvidia.com/gpu (a second scheduler profile; gsb manifests ships it). Otherwise as default and kueue.
- volcano-binpack: Volcano with binpack.resources: nvidia.com/gpu and binpack.weight: 10, so GPU packing
  outweighs nodeorder's cpu/memory scores. Otherwise as volcano.

- kai: KAI Scheduler gang scheduling of pod groups, bin-packing by default, hierarchical queues with
  fair-share over quota, reclaim of borrowed resources, and priority preemption within a queue.
"""
from __future__ import annotations

from dataclasses import replace

from .sim import Policy

STACKS = ("default", "kueue", "volcano", "kai")       # as installed, with their documented defaults
TUNED = ("default-binpack", "kueue-binpack", "volcano-binpack")   # configured to bin-pack GPUs
ALL_STACKS = STACKS + TUNED


def preset(name: str, quotas: dict[str, float] | None = None) -> Policy:
    """`quotas` are team shares of the fleet; stacks that support quotas get them, the default stack ignores them."""
    q = dict(quotas or {})
    if name in TUNED:
        return replace(preset(name.removesuffix("-binpack"), q), name=name, placement="binpack")
    if name == "default":
        return Policy("default", placement="random", queue="best-effort", gang=False, priority_preemption="global")
    if name == "kueue":
        return Policy("kueue", placement="random", queue="best-effort", gang=True, quotas=q, borrowing=bool(q),
                      reclaim=bool(q), priority_preemption="team")
    if name == "volcano":
        return Policy("volcano", placement="most-pods", queue="best-effort", gang=True, quotas=q, borrowing=bool(q),
                      enqueue_overcommit=1.2)
    if name == "kai":
        return Policy("kai", placement="binpack", queue="best-effort", gang=True, quotas=q, borrowing=bool(q),
                      reclaim=bool(q), priority_preemption="team")
    raise ValueError(f"unknown stack '{name}'; choose from {', '.join(ALL_STACKS)}")


def equal_quotas(teams: list[str]) -> dict[str, float]:
    """An equal share of the fleet for each team, the usual starting point for a shared platform."""
    teams = sorted(set(teams))
    return {t: 1.0 / len(teams) for t in teams} if teams else {}
