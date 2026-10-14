"""Render a fleet as kwok fake nodes: real Node objects with GPU capacity and no kubelet behind them.

The control plane and the scheduler under test treat them like real GPU nodes, which is all a
scheduling benchmark needs. See https://kwok.sigs.k8s.io/ for how kwok manages these nodes.
"""
from __future__ import annotations

from .fleet import Fleet

POOL_LABEL = "gsb.io/pool"
KWOK_TAINT = {"key": "kwok.x-k8s.io/node", "value": "fake", "effect": "NoSchedule"}


def _taint(spec: str) -> dict:
    keyval, effect = spec.rsplit(":", 1)
    key, _, value = keyval.partition("=")
    return {"key": key, "value": value, "effect": effect} if value else {"key": key, "effect": effect}


def node_manifests(fleet: Fleet) -> list[dict]:
    pools = {p.name: p for p in fleet.pools}
    out = []
    for node in fleet.nodes:
        pool = pools[node.pool]
        resources = {"cpu": str(pool.cpu), "memory": f"{pool.memory_gib}Gi", "pods": "110", "nvidia.com/gpu": str(node.gpus)}
        out.append({
            "apiVersion": "v1",
            "kind": "Node",
            "metadata": {
                "name": node.name,
                "annotations": {"node.alpha.kubernetes.io/ttl": "0", "kwok.x-k8s.io/node": "fake"},
                "labels": {"kubernetes.io/hostname": node.name, "kubernetes.io/os": "linux", "type": "kwok",
                           POOL_LABEL: node.pool, "nvidia.com/gpu.product": node.gpu_model,
                           "nvidia.com/gpu.count": str(node.gpus), **pool.labels},
            },
            "spec": {"taints": [KWOK_TAINT, *(_taint(t) for t in pool.taints)]},
            "status": {"allocatable": dict(resources), "capacity": dict(resources),
                       "nodeInfo": {"architecture": "amd64", "operatingSystem": "linux", "kubeletVersion": "fake"},
                       "phase": "Running"},
        })
    return out


def render(fleet: Fleet) -> str:
    import yaml
    return yaml.safe_dump_all(node_manifests(fleet), sort_keys=False)
