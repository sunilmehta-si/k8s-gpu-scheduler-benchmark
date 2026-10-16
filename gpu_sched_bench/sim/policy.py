"""Scheduling policies as data: each knob is one documented behaviour a scheduler does or doesn't have."""
from __future__ import annotations

from dataclasses import dataclass, field

PLACEMENTS = ("spread", "binpack", "random", "most-pods")
QUEUES = ("best-effort", "strict")
PRIORITY_PREEMPTION = ("none", "team", "global")


@dataclass(frozen=True)
class Policy:
    name: str
    placement: str = "spread"       # spread: most free GPUs first (kube-scheduler's LeastAllocated default);
                                    # binpack: fewest free GPUs that still fit, keeping whole nodes free for big jobs;
                                    # random: any node that fits, chosen with a seeded generator. This is what a
                                    # scheduler does when its scoring ignores GPUs: every feasible node ties
                                    # and the scheduler picks one of the tied nodes at random;
                                    # most-pods: the node already running the most pods, ties at random. Volcano's
                                    # default binpack packs the 100m cpu it charges a pod without requests, so it
                                    # stacks pods by count whatever their GPU size
    queue: str = "best-effort"      # best-effort: a job that doesn't fit is skipped and later jobs may start;
                                    # strict: nothing behind the head of the queue starts until it does
    gang: bool = False              # all-or-nothing: a gang job's replicas are placed together or not at all
    quotas: dict[str, float] = field(default_factory=dict)  # team -> guaranteed share of the fleet's GPUs
    borrowing: bool = False         # a team may use other teams' unused quota (Kueue cohorts, KAI/Volcano queues)
    reclaim: bool = False           # a team within its quota evicts borrowers to get its GPUs back
    priority_preemption: str = "none"  # a job evicts lower-priority jobs: in its own team, anywhere, or never
    seed: int = 0                   # for random placement; the same seed gives the same run
    enqueue_overcommit: float = 0.0  # >0: a job is only considered once the GPUs queued jobs still wait for, plus
                                     # its own minimum, fit in factor x fleet minus what is in use (Volcano's
                                     # overcommit plugin, default factor 1.2); 0: every pending job is considered

    def __post_init__(self):
        if self.placement not in PLACEMENTS:
            raise ValueError(f"placement must be one of {', '.join(PLACEMENTS)}")
        if self.queue not in QUEUES:
            raise ValueError(f"queue must be one of {', '.join(QUEUES)}")
        if any(v < 0 for v in self.quotas.values()) or sum(self.quotas.values()) > 1.0 + 1e-9:
            raise ValueError("quota shares must be >= 0 and add up to at most 1.0")
        if self.borrowing and not self.quotas:
            raise ValueError("borrowing needs quotas")
        if self.priority_preemption not in PRIORITY_PREEMPTION:
            raise ValueError(f"priority_preemption must be one of {', '.join(PRIORITY_PREEMPTION)}")
        if self.enqueue_overcommit and self.enqueue_overcommit < 1.0:
            raise ValueError("enqueue_overcommit must be 0 (off) or at least 1.0")
        if self.reclaim and not self.borrowing:
            raise ValueError("reclaim needs borrowing (there is nothing to reclaim otherwise)")
