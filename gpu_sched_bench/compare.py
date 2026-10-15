"""Put the reference model next to a cluster run of the same stack, fleet and trace."""
from __future__ import annotations

from .report import ROWS, _get

COMPARED = ["Makespan (h)", "GPU utilisation", "Useful utilisation", "Queue wait p95 (min)", "Stranded GPU-hours",
            "Idle GPUs too small for waiting work", "Cost per useful GPU-hour"]


def compare(model: dict, cluster: dict) -> str:
    if model.get("mode") != "simulation" or cluster.get("mode") != "cluster":
        raise ValueError("compare needs a simulation results file and a cluster results file")
    if (model["fleet"]["name"], model["trace"]["name"]) != (cluster["fleet"]["name"], cluster["trace"]["name"]):
        raise ValueError("the two files are for different fleets or traces")
    stacks = [s for s in cluster["stacks"] if s in model["stacks"]]
    if not stacks:
        raise ValueError("no stack appears in both files")
    check = cluster.get("runtime_check", {})
    lines = [f"## Model vs cluster: {cluster['fleet']['name']}, {cluster['trace']['name']}", ""]
    if check and not check.get("ok"):
        lines += [f"> **Warning:** the cluster run failed its runtime check ({check.get('reason')}). Its numbers are not "
                  "comparable.", ""]
    lines += ["| Metric | " + " | ".join(f"{s} model | {s} cluster | difference" for s in stacks) + " |",
              "|---|" + "---|---|---|" * len(stacks)]
    rows = {label: (path, fmt) for label, path, _, fmt in ROWS}
    for label in COMPARED:
        path, fmt = rows[label]
        cells = []
        for s in stacks:
            m, c = _get(model["stacks"][s], path), _get(cluster["stacks"][s], path)
            diff = "-"
            if isinstance(m, (int, float)) and isinstance(c, (int, float)) and m:
                diff = f"{(c - m) / abs(m):+.0%}"
            cells += ["-" if m is None else fmt(m, model["stacks"][s]), "-" if c is None else fmt(c, cluster["stacks"][s]), diff]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"
