"""Workload traces: the jobs every scheduler under test receives, in the same order at the same times.

One JSON object per line (JSONL), for example:

    {"id": "train-0007", "arrival_s": 120.0, "team": "research", "kind": "training", "replicas": 4,
     "gpus_per_replica": 8, "duration_s": 7200, "priority": 0, "gang": true, "model": "llama-70b"}
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

KINDS = ("training", "finetune", "inference", "notebook")


class TraceError(ValueError):
    pass


@dataclass(frozen=True)
class Job:
    id: str
    arrival_s: float
    team: str
    kind: str
    replicas: int
    gpus_per_replica: int
    duration_s: float
    priority: int = 0
    gang: bool = False       # all replicas must start together (distributed training)
    model: str = ""
    gpu_model: str = ""      # required GPU product (a node's nvidia.com/gpu.product); empty = any

    @property
    def gpus(self) -> int:
        return self.replicas * self.gpus_per_replica

    @property
    def gpu_seconds(self) -> float:
        return self.gpus * self.duration_s


def _job(raw: dict, line: int) -> Job:
    where = f"line {line}"
    if not isinstance(raw, dict):
        raise TraceError(f"{where}: each line must be a JSON object.")
    unknown = set(raw) - {f for f in Job.__dataclass_fields__}
    if unknown:
        raise TraceError(f"{where}: unknown field(s) {', '.join(sorted(unknown))}.")
    missing = [f for f in ("id", "arrival_s", "team", "kind", "replicas", "gpus_per_replica", "duration_s") if f not in raw]
    if missing:
        raise TraceError(f"{where}: missing {', '.join(missing)}.")
    if raw["kind"] not in KINDS:
        raise TraceError(f"{where} ({raw['id']}): kind must be one of {', '.join(KINDS)}.")
    for key in ("replicas", "gpus_per_replica"):
        if not isinstance(raw[key], int) or isinstance(raw[key], bool) or raw[key] < 1:
            raise TraceError(f"{where} ({raw['id']}): {key} must be a positive integer.")
    if not isinstance(raw["arrival_s"], (int, float)) or raw["arrival_s"] < 0:
        raise TraceError(f"{where} ({raw['id']}): arrival_s must be a number >= 0.")
    if not isinstance(raw["duration_s"], (int, float)) or raw["duration_s"] <= 0:
        raise TraceError(f"{where} ({raw['id']}): duration_s must be a number > 0.")
    return Job(id=str(raw["id"]), arrival_s=float(raw["arrival_s"]), team=str(raw["team"]), kind=raw["kind"],
               replicas=raw["replicas"], gpus_per_replica=raw["gpus_per_replica"], duration_s=float(raw["duration_s"]),
               priority=int(raw.get("priority", 0)), gang=bool(raw.get("gang", False)), model=str(raw.get("model", "")),
               gpu_model=str(raw.get("gpu_model", "")))


def parse(lines: list[str]) -> list[Job]:
    jobs: list[Job] = []
    for n, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            raw = json.loads(line)
        except ValueError as exc:
            raise TraceError(f"line {n}: not valid JSON ({exc}).") from exc
        jobs.append(_job(raw, n))
    ids = [j.id for j in jobs]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise TraceError(f"Duplicate job id(s): {', '.join(dupes[:5])}.")
    return sorted(jobs, key=lambda j: (j.arrival_s, j.id))


def load(path: str | Path) -> list[Job]:
    return parse(Path(path).read_text().splitlines())


def dump(jobs: list[Job]) -> str:
    """One JSON object per job; the optional gpu_model is written only when set, so older traces stay byte-identical."""
    out = []
    for j in jobs:
        d = asdict(j)
        if not d["gpu_model"]:
            del d["gpu_model"]
        out.append(json.dumps(d, separators=(",", ":")) + "\n")
    return "".join(out)


def check_fits(jobs: list[Job], max_gpus_per_node: int, nodes_by_model: dict[str, int] | None = None) -> None:
    """Every replica must fit on one node of the fleet (of its required GPU model), or no scheduler could place it.
    nodes_by_model maps a GPU product to the most GPUs any node of that product has."""
    too_big = [j.id for j in jobs if j.gpus_per_replica > max_gpus_per_node]
    if too_big:
        raise TraceError(f"{len(too_big)} job(s) ask for more GPUs per replica than any node has ({max_gpus_per_node}), "
                         f"e.g. {', '.join(too_big[:3])}.")
    if nodes_by_model is not None:
        unmet = [j.id for j in jobs if j.gpu_model and j.gpus_per_replica > nodes_by_model.get(j.gpu_model, 0)]
        if unmet:
            raise TraceError(f"{len(unmet)} job(s) need a GPU model the fleet doesn't have enough of on one node, "
                             f"e.g. {', '.join(unmet[:3])}.")


def stats(jobs: list[Job], fleet=None) -> str:
    """Jobs and GPU-hours by kind and team; with a fleet, demand as a share of capacity over the arrival window."""
    lines = [f"{len(jobs)} jobs, {sum(j.gpu_seconds for j in jobs) / 3600:,.0f} GPU-hours requested"]
    for label, key in (("kind", lambda j: j.kind), ("team", lambda j: j.team)):
        groups: dict[str, list[Job]] = {}
        for j in jobs:
            groups.setdefault(key(j), []).append(j)
        lines.append(f"\nby {label}:")
        for name, js in sorted(groups.items()):
            lines.append(f"  {name:<12} {len(js):>5} jobs  {sum(j.gpu_seconds for j in js) / 3600:>9,.0f} GPU-hours"
                         f"  largest {max(j.gpus for j in js):>3} GPUs")
    if fleet is not None and jobs:
        window_h = max(j.arrival_s for j in jobs) / 3600 or 1.0
        demand = sum(j.gpu_seconds for j in jobs) / 3600 / (fleet.total_gpus * window_h)
        lines.append(f"\ndemand: {demand:.0%} of {fleet.name} ({fleet.total_gpus} GPUs) over the {window_h:.1f} h arrival window")
    return "\n".join(lines)
