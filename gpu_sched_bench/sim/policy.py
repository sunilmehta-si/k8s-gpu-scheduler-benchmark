"""Scheduling policies as data: each knob is one documented behaviour a scheduler does or doesn't have."""
from __future__ import annotations

from dataclasses import dataclass

PLACEMENTS = ("spread",)
QUEUES = ("best-effort",)


@dataclass(frozen=True)
class Policy:
    name: str
    placement: str = "spread"       # spread: most free GPUs first (kube-scheduler's LeastAllocated default)
    queue: str = "best-effort"      # best-effort: a job that doesn't fit is skipped and later jobs may start

    def __post_init__(self):
        if self.placement not in PLACEMENTS:
            raise ValueError(f"placement must be one of {', '.join(PLACEMENTS)}")
        if self.queue not in QUEUES:
            raise ValueError(f"queue must be one of {', '.join(QUEUES)}")
