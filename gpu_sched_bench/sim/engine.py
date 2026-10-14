"""Discrete-event engine: arrivals and replica completions, with a scheduling pass after every event.

Replicas are the unit of placement (one pod each). A gang job (distributed training) only makes progress
once all its replicas run; replicas placed before that hold their GPUs idle, which is recorded as
stranded GPU time. Independent replicas (inference, notebooks) start working as soon as they are placed.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from ..fleet import Fleet
from ..trace import Job
from .policy import Policy

ARRIVAL, FINISH = 0, 1
# Job controllers create a job's pods one after another, and kube-scheduler queues pods by priority then
# creation time. Pods of jobs submitted at the same moment therefore interleave, which is how pod-by-pod
# scheduling ends up with several half-placed gangs.
POD_CREATE_INTERVAL_S = 0.01


@dataclass
class NodeState:
    name: str
    pool: str
    gpus: int
    free: int
    price: float


@dataclass
class JobRecord:
    job: Job
    nodes: list[str | None] = field(default_factory=list)        # node per replica, None = not placed
    replica_start: list[float | None] = field(default_factory=list)
    replica_end: list[float | None] = field(default_factory=list)
    held_since: list[float | None] = field(default_factory=list)  # placed but waiting for the rest of its gang

    @property
    def placed(self) -> int:
        return sum(1 for n in self.nodes if n is not None)

    @property
    def start(self) -> float | None:
        """When the whole job was running: the last replica's start."""
        return None if None in self.replica_start else max(self.replica_start)

    @property
    def end(self) -> float | None:
        return None if None in self.replica_end else max(self.replica_end)

    @property
    def wait(self) -> float | None:
        return None if self.start is None else self.start - self.job.arrival_s


@dataclass
class Result:
    policy: Policy
    fleet: Fleet
    records: dict[str, JobRecord]
    makespan: float
    allocated_gpu_s: float = 0.0     # GPU-seconds held by placed replicas (working or stranded)
    stranded_gpu_s: float = 0.0      # GPU-seconds held by gang replicas waiting for the rest of their gang
    deadlocked: bool = False         # partial gangs blocked each other and nothing could ever finish
    samples: list[tuple[float, float, list[int]]] = field(default_factory=list)  # (time, dt, free GPUs per node)

    @property
    def unfinished(self) -> list[str]:
        return sorted(j for j, r in self.records.items() if r.end is None)


class Simulator:
    def __init__(self, fleet: Fleet, jobs: list[Job], policy: Policy):
        self.fleet, self.policy = fleet, policy
        self.nodes = [NodeState(n.name, n.pool, n.gpus, n.gpus, n.price_per_gpu_hour) for n in fleet.nodes]
        self.by_name = {n.name: n for n in self.nodes}
        self.records = {j.id: JobRecord(j, [None] * j.replicas, [None] * j.replicas, [None] * j.replicas,
                                        [None] * j.replicas) for j in jobs}
        self.pending: list[str] = []
        self.events: list[tuple[float, int, int, str, int]] = []
        self._seq = 0
        for j in jobs:
            self._push(j.arrival_s, ARRIVAL, j.id, -1)
        self.now = 0.0
        self.allocated_gpu_s = self.stranded_gpu_s = 0.0
        self.samples: list[tuple[float, float, list[int]]] = []

    def _push(self, t: float, kind: int, job_id: str, replica: int) -> None:
        self._seq += 1
        heapq.heappush(self.events, (t, self._seq, kind, job_id, replica))

    # -- accounting -------------------------------------------------------------------------------
    def _advance(self, t: float) -> None:
        dt = t - self.now
        if dt > 0:
            allocated = sum(n.gpus - n.free for n in self.nodes)
            stranded = sum(r.job.gpus_per_replica for r in self.records.values() for h in r.held_since if h is not None)
            self.allocated_gpu_s += allocated * dt
            self.stranded_gpu_s += stranded * dt
            self.samples.append((self.now, dt, [n.free for n in self.nodes]))
        self.now = t

    # -- placement --------------------------------------------------------------------------------
    def _choose(self, need: int, free: dict[str, int]) -> str | None:
        fits = [n for n in self.nodes if free[n.name] >= need]
        if not fits:
            return None
        # spread: the node with the most free GPUs; ties broken by name for determinism
        return min(fits, key=lambda n: (-free[n.name], n.name)).name

    def _place_replica(self, rec: JobRecord, i: int, node: str) -> None:
        rec.nodes[i] = node
        self.by_name[node].free -= rec.job.gpus_per_replica
        if rec.job.gang:
            rec.held_since[i] = self.now
        else:
            self._start(rec, i)

    def _start(self, rec: JobRecord, i: int) -> None:
        rec.held_since[i] = None
        rec.replica_start[i] = self.now
        self._push(self.now + rec.job.duration_s, FINISH, rec.job.id, i)

    def _schedule(self) -> None:
        if self.policy.gang:
            self._schedule_jobs()
        else:
            self._schedule_pods()
        for job_id in list(self.pending):
            rec = self.records[job_id]
            if rec.placed == rec.job.replicas:
                self.pending.remove(job_id)
                if rec.job.gang:                       # the gang is complete: everyone starts together
                    for i in range(rec.job.replicas):
                        self._start(rec, i)

    def _fit_all(self, rec: JobRecord) -> list[str] | None:
        """A node for every unplaced replica at once, or None: placement is decided on a copy of the free map."""
        free = {n.name: n.free for n in self.nodes}
        plan = []
        for i, node in enumerate(rec.nodes):
            if node is not None:
                continue
            choice = self._choose(rec.job.gpus_per_replica, free)
            if choice is None:
                return None
            free[choice] -= rec.job.gpus_per_replica
            plan.append(choice)
        return plan

    def _schedule_jobs(self) -> None:
        """Job by job in priority then arrival order; gang jobs are placed all-or-nothing."""
        order = sorted(self.pending, key=lambda j: (-self.records[j].job.priority, self.records[j].job.arrival_s, j))
        for job_id in order:
            rec = self.records[job_id]
            if rec.job.gang:
                plan = self._fit_all(rec)
                if plan is None:
                    continue
                for i, node in zip([k for k, n in enumerate(rec.nodes) if n is None], plan):
                    self._place_replica(rec, i, node)
                continue
            for i, node in enumerate(rec.nodes):        # independent replicas: as many as fit now
                if node is None:
                    choice = self._choose(rec.job.gpus_per_replica, {n.name: n.free for n in self.nodes})
                    if choice is None:
                        break
                    self._place_replica(rec, i, choice)

    def _schedule_pods(self) -> None:
        """Pod by pod, in kube-scheduler queue order; a pod that doesn't fit is skipped."""
        pods = [(job_id, i) for job_id in self.pending for i, n in enumerate(self.records[job_id].nodes) if n is None]
        pods.sort(key=lambda p: (-self.records[p[0]].job.priority,
                                 self.records[p[0]].job.arrival_s + p[1] * POD_CREATE_INTERVAL_S, p[0], p[1]))
        for job_id, i in pods:
            rec = self.records[job_id]
            node = self._choose(rec.job.gpus_per_replica, {n.name: n.free for n in self.nodes})
            if node is not None:
                self._place_replica(rec, i, node)

    # -- main loop --------------------------------------------------------------------------------
    def run(self) -> Result:
        deadlocked = False
        while self.events:
            t = self.events[0][0]
            self._advance(t)
            while self.events and self.events[0][0] == t:
                _, _, kind, job_id, replica = heapq.heappop(self.events)
                rec = self.records[job_id]
                if kind == ARRIVAL:
                    self.pending.append(job_id)
                else:
                    rec.replica_end[replica] = t
                    self.by_name[rec.nodes[replica]].free += rec.job.gpus_per_replica
            self._schedule()
            if not self.events and self.pending:
                deadlocked = True      # nothing will ever finish, and what is pending can never be placed
        return Result(self.policy, self.fleet, self.records, makespan=self.now, allocated_gpu_s=self.allocated_gpu_s,
                      stranded_gpu_s=self.stranded_gpu_s, deadlocked=deadlocked, samples=self.samples)


def simulate(fleet: Fleet, jobs: list[Job], policy: Policy) -> Result:
    return Simulator(fleet, jobs, policy).run()
