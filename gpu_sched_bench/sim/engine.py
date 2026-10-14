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
    placed_at: list[float | None] = field(default_factory=list)    # when each replica got its node (billing starts)
    wasted_cost: float = 0.0                                       # GPU cost of work discarded by preemption
    epoch: int = 0                                                 # bumped on preemption; stale finishes are ignored
    preemptions: int = 0

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
    preempted_gpu_s: float = 0.0     # GPU-seconds of work thrown away by preemption (jobs restart from scratch)
    deadlocked: bool = False         # partial gangs blocked each other and nothing could ever finish
    # (time, dt, free GPUs per node in fleet order, smallest replica still waiting for a node or 0)
    samples: list[tuple[float, float, list[int], int]] = field(default_factory=list)

    @property
    def unfinished(self) -> list[str]:
        return sorted(j for j, r in self.records.items() if r.end is None)


class Simulator:
    def __init__(self, fleet: Fleet, jobs: list[Job], policy: Policy):
        self.fleet, self.policy = fleet, policy
        self.nodes = [NodeState(n.name, n.pool, n.gpus, n.gpus, n.price_per_gpu_hour) for n in fleet.nodes]
        self.by_name = {n.name: n for n in self.nodes}
        self.records = {j.id: JobRecord(j, [None] * j.replicas, [None] * j.replicas, [None] * j.replicas,
                                        [None] * j.replicas, [None] * j.replicas) for j in jobs}
        self.pending: list[str] = []
        self.events: list[tuple[float, int, int, str, int, int]] = []
        self._seq = 0
        for j in jobs:
            self._push(j.arrival_s, ARRIVAL, j.id, -1, 0)
        self.now = 0.0
        self.nominal = {team: int(share * fleet.total_gpus) for team, share in policy.quotas.items()}
        self.usage: dict[str, int] = {}
        self.allocated_gpu_s = self.stranded_gpu_s = self.preempted_gpu_s = 0.0
        self.samples: list[tuple[float, float, list[int], int]] = []

    def _push(self, t: float, kind: int, job_id: str, replica: int, epoch: int) -> None:
        self._seq += 1
        heapq.heappush(self.events, (t, self._seq, kind, job_id, replica, epoch))

    # -- accounting -------------------------------------------------------------------------------
    def _advance(self, t: float) -> None:
        dt = t - self.now
        if dt > 0:
            allocated = sum(n.gpus - n.free for n in self.nodes)
            stranded = sum(r.job.gpus_per_replica for r in self.records.values() for h in r.held_since if h is not None)
            self.allocated_gpu_s += allocated * dt
            self.stranded_gpu_s += stranded * dt
            waiting = [self.records[j].job.gpus_per_replica for j in self.pending if self.records[j].placed < self.records[j].job.replicas]
            self.samples.append((self.now, dt, [n.free for n in self.nodes], min(waiting, default=0)))
        self.now = t

    # -- placement --------------------------------------------------------------------------------
    def _choose(self, need: int, free: dict[str, int]) -> str | None:
        fits = [n for n in self.nodes if free[n.name] >= need]
        if not fits:
            return None
        if self.policy.placement == "binpack":     # tightest fit: the busiest node that still has room
            return min(fits, key=lambda n: (free[n.name] - need, n.name)).name
        # spread: the node with the most free GPUs; ties broken by name for determinism
        return min(fits, key=lambda n: (-free[n.name], n.name)).name

    def _admissible(self, team: str, need: int) -> bool:
        """Quota check at admission. A team may always use its nominal quota; with borrowing it may also use
        GPUs other teams are entitled to but not using. Teams without a quota can only borrow."""
        if not self.nominal:
            return True
        used = self.usage.get(team, 0)
        over = used + need - self.nominal.get(team, 0)
        if over <= 0:
            return True
        if not self.policy.borrowing:
            return False
        lendable = sum(max(0, q - self.usage.get(t, 0)) for t, q in self.nominal.items() if t != team)
        borrowed_by_others = sum(max(0, self.usage.get(t, 0) - self.nominal.get(t, 0))
                                 for t in set(self.usage) | set(self.nominal) if t != team)
        return over <= lendable - borrowed_by_others

    def _place_replica(self, rec: JobRecord, i: int, node: str) -> None:
        rec.nodes[i] = node
        rec.placed_at[i] = self.now
        self.usage[rec.job.team] = self.usage.get(rec.job.team, 0) + rec.job.gpus_per_replica
        self.by_name[node].free -= rec.job.gpus_per_replica
        if rec.job.gang:
            rec.held_since[i] = self.now
        else:
            self._start(rec, i)

    def _start(self, rec: JobRecord, i: int) -> None:
        rec.held_since[i] = None
        rec.replica_start[i] = self.now
        self._push(self.now + rec.job.duration_s, FINISH, rec.job.id, i, rec.epoch)

    def _schedule(self) -> None:
        if self.policy.gang or self.policy.queue == "strict" or self.nominal:
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

    def _fit_all(self, rec: JobRecord, free: dict[str, int] | None = None) -> list[str] | None:
        """A node for every unplaced replica at once, or None: placement is decided on a copy of the free map."""
        free = dict(free) if free is not None else {n.name: n.free for n in self.nodes}
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

    def _preempt(self, rec: JobRecord) -> None:
        """Evict a job: free its GPUs, discard its progress, and queue it again."""
        for i, node in enumerate(rec.nodes):
            if node is None:
                continue
            self.by_name[node].free += rec.job.gpus_per_replica
            self.usage[rec.job.team] -= rec.job.gpus_per_replica
            rec.wasted_cost += (self.now - rec.placed_at[i]) * rec.job.gpus_per_replica * self.by_name[node].price / 3600
            if rec.replica_start[i] is not None and rec.replica_end[i] is None:
                self.preempted_gpu_s += (self.now - rec.replica_start[i]) * rec.job.gpus_per_replica
        n = rec.job.replicas
        rec.nodes, rec.replica_start, rec.replica_end, rec.held_since, rec.placed_at = \
            [None] * n, [None] * n, [None] * n, [None] * n, [None] * n
        rec.epoch += 1
        rec.preemptions += 1
        self.pending.append(rec.job.id)

    def _reclaim_for(self, rec: JobRecord, need: int, fits) -> bool:
        """Evict borrowers (lowest priority, most recently started first) until `rec` is admissible and fits.
        Only jobs of teams above their nominal quota are victims, and only while their team stays above it.
        Nothing is evicted unless the full set of evictions would let `rec` start."""
        team = rec.job.team
        if self.usage.get(team, 0) + need > self.nominal.get(team, 0):
            return False                               # reclaim only restores a team's own quota
        candidates = [r for r in self.records.values()
                      if r.placed and r.end is None and r.job.id not in self.pending and r.job.team != team]
        candidates.sort(key=lambda r: (r.job.priority, -(r.start or 0), r.job.id))
        free = {n.name: n.free for n in self.nodes}
        usage = dict(self.usage)
        victims = []
        for v in candidates:
            if usage.get(v.job.team, 0) <= self.nominal.get(v.job.team, 0):
                continue                               # that team is not borrowing (any more): leave it alone
            victims.append(v)
            usage[v.job.team] -= sum(v.job.gpus_per_replica for x in v.nodes if x is not None)
            for x in v.nodes:
                if x is not None:
                    free[x] += v.job.gpus_per_replica
            if fits(free):
                for victim in victims:
                    self._preempt(victim)
                return True
        return False

    def _schedule_jobs(self) -> None:
        """Job by job in priority then arrival order; with gang on, gang jobs are placed all-or-nothing.
        In a strict queue the first job that can't be fully placed stops the pass (head-of-line blocking)."""
        order = sorted(self.pending, key=lambda j: (-self.records[j].job.priority, self.records[j].job.arrival_s, j))
        for job_id in order:
            rec = self.records[job_id]
            if rec.job.gang and self.policy.gang:
                unplaced = sum(1 for n in rec.nodes if n is None)
                need = unplaced * rec.job.gpus_per_replica
                plan = self._fit_all(rec) if self._admissible(rec.job.team, need) else None
                if plan is None and self.policy.reclaim and \
                        self._reclaim_for(rec, need, lambda free: self._fit_all(rec, free) is not None):
                    plan = self._fit_all(rec)
                if plan is not None:
                    for i, node in zip([k for k, n in enumerate(rec.nodes) if n is None], plan):
                        self._place_replica(rec, i, node)
            else:
                for i, node in enumerate(rec.nodes):    # independent replicas: as many as fit now
                    if node is None:
                        need = rec.job.gpus_per_replica
                        current = {n.name: n.free for n in self.nodes}
                        choice = self._choose(need, current) if self._admissible(rec.job.team, need) else None
                        if choice is None and self.policy.reclaim and \
                                self._reclaim_for(rec, need, lambda free: self._choose(need, free) is not None):
                            choice = self._choose(need, {n.name: n.free for n in self.nodes})
                        if choice is None:
                            break
                        self._place_replica(rec, i, choice)
            if self.policy.queue == "strict" and rec.placed < rec.job.replicas:
                break

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
                _, _, kind, job_id, replica, epoch = heapq.heappop(self.events)
                rec = self.records[job_id]
                if kind == FINISH and epoch != rec.epoch:
                    continue                           # the replica was preempted before it finished
                if kind == ARRIVAL:
                    self.pending.append(job_id)
                else:
                    rec.replica_end[replica] = t
                    self.by_name[rec.nodes[replica]].free += rec.job.gpus_per_replica
                    self.usage[rec.job.team] -= rec.job.gpus_per_replica
            self._schedule()
            if not self.events and self.pending:
                deadlocked = True      # nothing will ever finish, and what is pending can never be placed
        return Result(self.policy, self.fleet, self.records, makespan=self.now, allocated_gpu_s=self.allocated_gpu_s,
                      stranded_gpu_s=self.stranded_gpu_s, preempted_gpu_s=self.preempted_gpu_s, deadlocked=deadlocked,
                      samples=self.samples)


def simulate(fleet: Fleet, jobs: list[Job], policy: Policy) -> Result:
    return Simulator(fleet, jobs, policy).run()
