"""Kubernetes manifests for running a trace on a real scheduler, against kwok fake GPU nodes.

`setup` objects are applied once (namespaces, priority classes, and each stack's queues); `workloads` are
one object per trace job, to be submitted at the job's arrival time (annotated as gsb.io/arrival-s).
Pods carry kwok's pod-complete delay annotation, so each fake pod "finishes" after its trace duration
(divided by --speedup). That stage only applies to pods owned by a Job, which all workloads here are.
"""
from __future__ import annotations

from .fleet import Fleet
from .kwok import KWOK_TAINT
from .trace import Job

PLACEHOLDER_IMAGE = "registry.k8s.io/pause:3.10"   # never runs: kwok nodes have no kubelet


def namespace(team: str) -> str:
    return f"gsb-{team}"


def priority_class(priority: int) -> str:
    return f"gsb-priority-{priority}"


def pod_template(job: Job, speedup: float, scheduler: str | None = None, labels: dict | None = None) -> dict:
    delay = max(1, round(job.duration_s / speedup))
    spec = {
        "restartPolicy": "Never",
        "priorityClassName": priority_class(job.priority),
        "nodeSelector": {"type": "kwok", **({"nvidia.com/gpu.product": job.gpu_model} if job.gpu_model else {})},
        "tolerations": [{"key": KWOK_TAINT["key"], "operator": "Exists", "effect": KWOK_TAINT["effect"]}],
        "automountServiceAccountToken": False,
        "containers": [{"name": "main", "image": PLACEHOLDER_IMAGE,
                        "resources": {"limits": {"nvidia.com/gpu": str(job.gpus_per_replica)}}}],
    }
    if scheduler:
        spec = {"schedulerName": scheduler, **spec}
    return {
        "metadata": {
            "labels": {"gsb.io/job": job.id, "gsb.io/team": job.team, "gsb.io/kind": job.kind, **(labels or {})},
            # kwok picks a random delay between delay and jitter-delay, and uses jitter-delay outright when it is
            # not larger (lifecycle.go, Stage.Delay). Equal values give an exact delay; "0s" would mean no delay at
            # all, and leaving it out would cap every delay at kwok's 5 s default.
            "annotations": {"pod-complete.stage.kwok.x-k8s.io/delay": f"{delay}s",
                            "pod-complete.stage.kwok.x-k8s.io/jitter-delay": f"{delay}s"},
        },
        "spec": spec,
    }


def common_setup(jobs: list[Job]) -> list[dict]:
    teams = sorted({j.team for j in jobs})
    priorities = sorted({j.priority for j in jobs})
    docs = [{"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": namespace(t), "labels": {"gsb.io/team": t}}}
            for t in teams]
    docs += [{"apiVersion": "scheduling.k8s.io/v1", "kind": "PriorityClass", "metadata": {"name": priority_class(p)},
              "value": p, "preemptionPolicy": "PreemptLowerPriority", "globalDefault": False,
              "description": f"gsb trace priority {p}"} for p in priorities]
    return docs


def batch_job(job: Job, speedup: float, scheduler: str | None = None, labels: dict | None = None,
              annotations: dict | None = None, pod_labels: dict | None = None) -> dict:
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": job.id, "namespace": namespace(job.team),
                     "labels": {"gsb.io/team": job.team, "gsb.io/kind": job.kind, **(labels or {})},
                     "annotations": {"gsb.io/arrival-s": str(job.arrival_s), **(annotations or {})}},
        "spec": {"parallelism": job.replicas, "completions": job.replicas, "backoffLimit": 0,
                 "template": pod_template(job, speedup, scheduler, pod_labels)},
    }


# -- stacks ------------------------------------------------------------------------------------------
def default_setup(fleet: Fleet, jobs: list[Job], quotas: dict[str, float]) -> list[dict]:
    return []     # kube-scheduler has no queues or quotas to configure


def default_workload(job: Job, speedup: float) -> dict:
    return batch_job(job, speedup)


# Kueue (kueue.x-k8s.io/v1beta2, as documented for Kueue v0.20): one ClusterQueue per team in a shared cohort,
# BestEffortFIFO, reclaimWithinCohort: Any so a team can take back its nominal quota from borrowers.
KUEUE_API = "kueue.x-k8s.io/v1beta2"
KUEUE_FLAVOR = "gsb-gpu"
KUEUE_LOCAL_QUEUE = "gsb-queue"


def _gpu_quotas(fleet: Fleet, jobs: list[Job], quotas: dict[str, float]) -> dict[str, int]:
    """Whole GPUs per team; without quotas, every team shares one queue sized to the fleet."""
    if not quotas:
        return {}
    return {team: int(share * fleet.total_gpus) for team, share in sorted(quotas.items())}


def kueue_setup(fleet: Fleet, jobs: list[Job], quotas: dict[str, float]) -> list[dict]:
    teams = sorted({j.team for j in jobs})
    gpus = _gpu_quotas(fleet, jobs, quotas)
    docs = [{"apiVersion": KUEUE_API, "kind": "ResourceFlavor", "metadata": {"name": KUEUE_FLAVOR},
             "spec": {"nodeLabels": {"type": "kwok"},
                      "tolerations": [{"key": KWOK_TAINT["key"], "operator": "Exists", "effect": KWOK_TAINT["effect"]}]}}]
    queues = {t: (f"gsb-{t}", gpus.get(t, 0)) for t in teams} if gpus else {t: ("gsb-shared", fleet.total_gpus) for t in teams}
    for name, nominal in sorted(set(queues.values())):
        team_selector = [t for t, (q, _) in queues.items() if q == name]
        docs.append({"apiVersion": KUEUE_API, "kind": "ClusterQueue", "metadata": {"name": name},
                     "spec": {"cohortName": "gsb",
                              "namespaceSelector": {"matchExpressions": [{"key": "gsb.io/team", "operator": "In",
                                                                          "values": team_selector}]},
                              "queueingStrategy": "BestEffortFIFO",
                              "resourceGroups": [{"coveredResources": ["nvidia.com/gpu"],
                                                  "flavors": [{"name": KUEUE_FLAVOR,
                                                               "resources": [{"name": "nvidia.com/gpu", "nominalQuota": nominal}]}]}],
                              "preemption": {"reclaimWithinCohort": "Any", "withinClusterQueue": "LowerPriority"}}})
    for t in teams:
        docs.append({"apiVersion": KUEUE_API, "kind": "LocalQueue",
                     "metadata": {"name": KUEUE_LOCAL_QUEUE, "namespace": namespace(t)},
                     "spec": {"clusterQueue": queues[t][0]}})
    return docs


def kueue_workload(job: Job, speedup: float) -> dict:
    return batch_job(job, speedup, labels={"kueue.x-k8s.io/queue-name": KUEUE_LOCAL_QUEUE})


# Volcano: one Queue per team weighted by its share (proportion plugin), gangs via minAvailable.
def _volcano_queue(team: str, quotas: dict[str, float]) -> str:
    return f"gsb-{team}" if quotas else "gsb-shared"


def volcano_setup(fleet: Fleet, jobs: list[Job], quotas: dict[str, float]) -> list[dict]:
    if not quotas:
        return [{"apiVersion": "scheduling.volcano.sh/v1beta1", "kind": "Queue", "metadata": {"name": "gsb-shared"},
                 "spec": {"weight": 1}}]
    return [{"apiVersion": "scheduling.volcano.sh/v1beta1", "kind": "Queue", "metadata": {"name": _volcano_queue(t, quotas)},
             "spec": {"weight": max(1, round(share * 100))}} for t, share in sorted(quotas.items())]


def volcano_workload(job: Job, speedup: float, quotas: dict[str, float] | None = None) -> dict:
    return {
        "apiVersion": "batch.volcano.sh/v1alpha1",
        "kind": "Job",
        "metadata": {"name": job.id, "namespace": namespace(job.team),
                     "labels": {"gsb.io/team": job.team, "gsb.io/kind": job.kind},
                     "annotations": {"gsb.io/arrival-s": str(job.arrival_s)}},
        "spec": {"schedulerName": "volcano", "queue": _volcano_queue(job.team, quotas or {}),
                 "minAvailable": job.replicas if job.gang else 1,       # gang: every replica or none
                 "priorityClassName": priority_class(job.priority), "maxRetry": 0,
                 "tasks": [{"name": "worker", "replicas": job.replicas,
                            "template": pod_template(job, speedup, "volcano")}]},
    }


# KAI Scheduler: hierarchical scheduling.run.ai/v2 Queues (a parent and one leaf per team), as in the KAI
# repository's docs/quickstart and docs/batch examples. Gangs use the kai.scheduler/batch-min-member annotation.
KAI_API = "scheduling.run.ai/v2"
KAI_PARENT = "gsb-parent"


def _kai_resources(gpu_quota: int) -> dict:
    unlimited = {"quota": 0, "limit": -1, "overQuotaWeight": 1}
    return {"cpu": dict(unlimited), "memory": dict(unlimited), "gpu": {"quota": gpu_quota, "limit": -1, "overQuotaWeight": 1}}


def _kai_queue(team: str, quotas: dict[str, float]) -> str:
    return f"gsb-{team}" if quotas else "gsb-shared"


def kai_setup(fleet: Fleet, jobs: list[Job], quotas: dict[str, float]) -> list[dict]:
    docs = [{"apiVersion": KAI_API, "kind": "Queue", "metadata": {"name": KAI_PARENT}, "spec": {"resources": _kai_resources(0)}}]
    gpus = _gpu_quotas(fleet, jobs, quotas)
    leaves = sorted(gpus.items()) if gpus else [(None, 0)]
    for team, quota in leaves:
        name = _kai_queue(team, quotas) if team else "gsb-shared"
        docs.append({"apiVersion": KAI_API, "kind": "Queue", "metadata": {"name": name},
                     "spec": {"parentQueue": KAI_PARENT, "resources": _kai_resources(quota)}})
    return docs


def kai_workload(job: Job, speedup: float, quotas: dict[str, float] | None = None) -> dict:
    annotations = {"kai.scheduler/batch-min-member": str(job.replicas)} if job.gang else {}
    return batch_job(job, speedup, scheduler="kai-scheduler", annotations=annotations,
                     pod_labels={"kai.scheduler/queue": _kai_queue(job.team, quotas or {})})


STACKS = {"default": (default_setup, default_workload), "kueue": (kueue_setup, kueue_workload),
          "volcano": (volcano_setup, volcano_workload), "kai": (kai_setup, kai_workload)}
QUOTA_AWARE_WORKLOADS = {"volcano", "kai"}   # workload renderers that need the quotas to pick a queue


def render(stack: str, fleet: Fleet, jobs: list[Job], quotas: dict[str, float], speedup: float = 1.0,
           part: str = "all") -> list[dict]:
    if stack not in STACKS:
        raise ValueError(f"no manifests for stack '{stack}'; available: {', '.join(STACKS)}")
    if speedup <= 0:
        raise ValueError("speedup must be > 0")
    setup_fn, workload_fn = STACKS[stack]
    docs = []
    if part in ("all", "setup"):
        docs += common_setup(jobs) + setup_fn(fleet, jobs, quotas)
    if part in ("all", "jobs"):
        docs += [workload_fn(j, speedup, quotas) if stack in QUOTA_AWARE_WORKLOADS else workload_fn(j, speedup)
                 for j in jobs]
    return docs
