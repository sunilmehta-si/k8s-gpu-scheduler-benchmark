"""Seeded synthetic traces with the job mix of a shared AI platform.

The shapes are deliberately simple and documented, so results can be reasoned about:
- training: multi-node gangs of full nodes, hours long, the jobs that suffer most from fragmentation
- finetune: one or two partial-node replicas, under an hour
- inference: small, long-running, higher priority, independent replicas
- notebook: one GPU, short, interactive priority
Durations are log-normal around a median; arrivals are a Poisson process.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .trace import Job


@dataclass(frozen=True)
class Shape:
    weight: float                                   # share of arrivals
    replicas: tuple[tuple[int, float], ...]         # (value, weight)
    gpus_per_replica: tuple[tuple[int, float], ...]
    median_minutes: float
    sigma: float                                    # log-normal spread
    priority: int
    gang: bool                                      # gang when replicas > 1
    models: tuple[str, ...]


DEFAULT_SHAPES: dict[str, Shape] = {
    "training": Shape(0.15, ((1, 2), (2, 3), (4, 3), (8, 1)), ((8, 1),), 120, 0.8, 0, True,
                      ("llama-70b", "mixtral-8x22b", "vision-encoder")),
    "finetune": Shape(0.25, ((1, 3), (2, 1)), ((2, 2), (4, 2), (8, 1)), 45, 0.7, 0, True,
                      ("llama-8b-lora", "qwen-14b-lora", "embedder")),
    "inference": Shape(0.20, ((1, 2), (2, 2), (4, 1)), ((1, 3), (2, 2)), 240, 0.6, 10, False,
                       ("chat-api", "rerank-api", "embed-api")),
    "notebook": Shape(0.40, ((1, 1),), ((1, 1),), 30, 0.9, 5, False, ("notebook",)),
}


@dataclass(frozen=True)
class TraceSpec:
    hours: float = 8.0
    jobs_per_hour: float = 40.0
    teams: dict[str, float] = field(default_factory=lambda: {"research": 0.4, "product": 0.35, "platform": 0.25})
    shapes: dict[str, Shape] = field(default_factory=lambda: dict(DEFAULT_SHAPES))
    max_gpus_per_node: int = 8
    max_job_gpus: int = 0          # cap on replicas x GPUs per job (0 = no cap); keep it below the fleet size
    seed: int = 7


def _pick(rng: random.Random, options: tuple[tuple[int, float], ...]) -> int:
    values, weights = zip(*options)
    return rng.choices(values, weights=weights)[0]


def generate(spec: TraceSpec) -> list[Job]:
    rng = random.Random(spec.seed)      # deterministic: same seed, same trace
    kinds = list(spec.shapes)
    kind_weights = [spec.shapes[k].weight for k in kinds]
    teams, team_weights = zip(*spec.teams.items())
    jobs: list[Job] = []
    t, horizon, n = 0.0, spec.hours * 3600, 0
    while True:
        t += rng.expovariate(spec.jobs_per_hour / 3600)
        if t >= horizon:
            break
        kind = rng.choices(kinds, weights=kind_weights)[0]
        shape = spec.shapes[kind]
        replicas = _pick(rng, shape.replicas)
        gpus = min(_pick(rng, shape.gpus_per_replica), spec.max_gpus_per_node)
        while spec.max_job_gpus and replicas > 1 and replicas * gpus > spec.max_job_gpus:
            replicas //= 2          # a job bigger than the cap could never be placed, so shrink it
        minutes = shape.median_minutes * math.exp(rng.gauss(0, shape.sigma))
        n += 1
        jobs.append(Job(id=f"{kind}-{n:05d}", arrival_s=round(t, 1), team=rng.choices(teams, weights=team_weights)[0],
                        kind=kind, replicas=replicas, gpus_per_replica=gpus, duration_s=round(max(60.0, minutes * 60), 1),
                        priority=shape.priority, gang=shape.gang and replicas > 1, model=rng.choice(shape.models)))
    return jobs
