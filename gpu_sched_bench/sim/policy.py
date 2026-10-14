"""Scheduling policies as data: each knob is one documented behaviour a scheduler does or doesn't have."""
from __future__ import annotations

from dataclasses import dataclass, field

PLACEMENTS = ("spread", "binpack")
QUEUES = ("best-effort", "strict")


@dataclass(frozen=True)
class Policy:
    name: str
    placement: str = "spread"       # spread: most free GPUs first (kube-scheduler's LeastAllocated default);
                                    # binpack: fewest free GPUs that still fit, keeping whole nodes free for big jobs
    queue: str = "best-effort"      # best-effort: a job that doesn't fit is skipped and later jobs may start;
                                    # strict: nothing behind the head of the queue starts until it does
    gang: bool = False              # all-or-nothing: a gang job's replicas are placed together or not at all
    quotas: dict[str, float] = field(default_factory=dict)  # team -> guaranteed share of the fleet's GPUs
    borrowing: bool = False         # a team may use other teams' unused quota (Kueue cohorts, KAI/Volcano queues)
    reclaim: bool = False           # a team within its quota evicts borrowers to get its GPUs back

    def __post_init__(self):
        if self.placement not in PLACEMENTS:
            raise ValueError(f"placement must be one of {', '.join(PLACEMENTS)}")
        if self.queue not in QUEUES:
            raise ValueError(f"queue must be one of {', '.join(QUEUES)}")
        if any(v < 0 for v in self.quotas.values()) or sum(self.quotas.values()) > 1.0 + 1e-9:
            raise ValueError("quota shares must be >= 0 and add up to at most 1.0")
        if self.borrowing and not self.quotas:
            raise ValueError("borrowing needs quotas")
        if self.reclaim and not self.borrowing:
            raise ValueError("reclaim needs borrowing (there is nothing to reclaim otherwise)")
