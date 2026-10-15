"""Read back what the scheduler did: for every benchmark pod, its node and when it was scheduled, started and finished."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

JOB_LABEL = "gsb.io/job"


@dataclass(frozen=True)
class PodRun:
    job_id: str
    name: str
    node: str | None
    scheduled_at: float | None   # PodScheduled condition turned True
    started_at: float | None     # status.startTime (kwok sets it when the pod becomes Ready)
    finished_at: float | None    # terminated container's finishedAt
    phase: str


def ts(value: str | None) -> float | None:
    """RFC 3339 timestamp to epoch seconds; Python 3.10's fromisoformat does not accept a trailing Z."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _scheduled(pod: dict) -> float | None:
    for c in (pod.get("status") or {}).get("conditions") or []:
        if c.get("type") == "PodScheduled" and c.get("status") == "True":
            return ts(c.get("lastTransitionTime"))
    return None


def _finished(pod: dict) -> float | None:
    ends = [ts(((s.get("state") or {}).get("terminated") or {}).get("finishedAt"))
            for s in (pod.get("status") or {}).get("containerStatuses") or []]
    ends = [e for e in ends if e is not None]
    return max(ends) if ends else None


def pod_runs(pods: dict) -> list[PodRun]:
    runs = []
    for pod in pods.get("items") or []:
        meta, spec, status = pod.get("metadata") or {}, pod.get("spec") or {}, pod.get("status") or {}
        job_id = (meta.get("labels") or {}).get(JOB_LABEL)
        if not job_id:
            continue
        runs.append(PodRun(job_id=job_id, name=meta.get("name", ""), node=spec.get("nodeName"),
                           scheduled_at=_scheduled(pod), started_at=ts(status.get("startTime")),
                           finished_at=_finished(pod) if status.get("phase") == "Succeeded" else None,
                           phase=status.get("phase", "Unknown")))
    return sorted(runs, key=lambda r: (r.job_id, r.name))


def collect(kube) -> list[PodRun]:
    return pod_runs(kube.get_json("pods", "--all-namespaces", "-l", JOB_LABEL))
