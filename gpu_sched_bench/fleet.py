"""A GPU fleet: pools of identical nodes. The same fleet drives the simulator and the kwok cluster."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

NAME = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")


class FleetError(ValueError):
    pass


@dataclass(frozen=True)
class Pool:
    name: str
    count: int                      # number of nodes
    gpus_per_node: int
    gpu_model: str = "NVIDIA-H100-80GB-HBM3"
    price_per_gpu_hour: float = 0.0  # used for cost per team / model; 0 disables cost
    cpu: int = 96                   # per node, for the kwok manifests
    memory_gib: int = 1024
    labels: dict[str, str] = field(default_factory=dict)
    taints: tuple[str, ...] = ()    # "key=value:Effect"


@dataclass(frozen=True)
class Node:
    name: str
    pool: str
    gpus: int
    gpu_model: str
    price_per_gpu_hour: float


@dataclass(frozen=True)
class Fleet:
    name: str
    pools: tuple[Pool, ...]

    @property
    def nodes(self) -> list[Node]:
        return [Node(f"{p.name}-{i:03d}", p.name, p.gpus_per_node, p.gpu_model, p.price_per_gpu_hour)
                for p in self.pools for i in range(p.count)]

    @property
    def total_gpus(self) -> int:
        return sum(p.count * p.gpus_per_node for p in self.pools)

    @property
    def max_gpus_per_node(self) -> int:
        return max(p.gpus_per_node for p in self.pools)

    @property
    def max_gpus_by_model(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.pools:
            out[p.gpu_model] = max(out.get(p.gpu_model, 0), p.gpus_per_node)
        return out


def _pool(raw: dict, where: str) -> Pool:
    if not isinstance(raw, dict):
        raise FleetError(f"{where} must be a mapping.")
    unknown = set(raw) - {"name", "count", "gpus_per_node", "gpu_model", "price_per_gpu_hour", "cpu", "memory_gib",
                          "labels", "taints"}
    if unknown:
        raise FleetError(f"{where}: unknown key(s) {', '.join(sorted(unknown))}.")
    name = str(raw.get("name", ""))
    if not NAME.match(name):
        raise FleetError(f"{where}: name '{name}' must be a DNS label (lowercase letters, digits and '-').")
    for key in ("count", "gpus_per_node"):
        if not isinstance(raw.get(key), int) or raw[key] < 1:
            raise FleetError(f"{where} ({name}): {key} must be a positive integer.")
    price = raw.get("price_per_gpu_hour", 0.0)
    if not isinstance(price, (int, float)) or price < 0:
        raise FleetError(f"{where} ({name}): price_per_gpu_hour must be a number >= 0.")
    taints = tuple(raw.get("taints") or ())
    for t in taints:
        if not re.match(r"^[\w./-]+(=[\w./-]*)?:(NoSchedule|PreferNoSchedule|NoExecute)$", str(t)):
            raise FleetError(f"{where} ({name}): taint '{t}' must look like key=value:NoSchedule.")
    return Pool(name=name, count=raw["count"], gpus_per_node=raw["gpus_per_node"],
                gpu_model=str(raw.get("gpu_model", Pool.gpu_model)), price_per_gpu_hour=float(price),
                cpu=int(raw.get("cpu", Pool.cpu)), memory_gib=int(raw.get("memory_gib", Pool.memory_gib)),
                labels={str(k): str(v) for k, v in (raw.get("labels") or {}).items()}, taints=taints)


def parse(data: dict) -> Fleet:
    if not isinstance(data, dict):
        raise FleetError("A fleet file must be a mapping with 'name' and 'pools'.")
    pools_raw = data.get("pools")
    if not isinstance(pools_raw, list) or not pools_raw:
        raise FleetError("'pools' must be a non-empty list.")
    pools = tuple(_pool(p, f"pools[{i}]") for i, p in enumerate(pools_raw, start=1))
    names = [p.name for p in pools]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise FleetError(f"Duplicate pool name(s): {', '.join(dupes)}.")
    return Fleet(name=str(data.get("name", "fleet")), pools=pools)


def load(path: str | Path) -> Fleet:
    import yaml
    try:
        data = yaml.safe_load(Path(path).read_text())
    except yaml.YAMLError as exc:
        raise FleetError(f"{path} is not valid YAML: {exc}") from exc
    return parse(data)
