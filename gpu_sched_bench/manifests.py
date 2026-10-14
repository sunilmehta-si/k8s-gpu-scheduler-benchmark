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
        "nodeSelector": {"type": "kwok"},
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
            "annotations": {"pod-complete.stage.kwok.x-k8s.io/delay": f"{delay}s",
                            "pod-complete.stage.kwok.x-k8s.io/jitter-delay": "0s"},
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


STACKS = {"default": (default_setup, default_workload)}


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
        docs += [workload_fn(j, speedup) for j in jobs]
    return docs
