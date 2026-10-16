"""Put the reference model next to a cluster run of the same stack, fleet and trace."""
from __future__ import annotations

from .report import ROWS, _get

COMPARED = ["Makespan (h)", "GPU utilisation", "Useful utilisation", "Queue wait p95 (min)", "Stranded GPU-hours",
            "Idle GPUs too small for waiting work", "Cost per useful GPU-hour"]


def _jobs(placements: list[dict]) -> dict[str, tuple[float | None, list[str]]]:
    """Per job: when its last replica started (None if one never did) and the node pools it ran on."""
    out: dict[str, tuple[float | None, set[str]]] = {}
    for r in placements:
        start, pools = out.get(r["job"], (0.0, set()))
        start = None if start is None or r["start_s"] is None else max(start, r["start_s"])
        if r["node"]:
            pools.add(r["node"].rsplit("-", 1)[0])
        out[r["job"]] = (start, pools)
    return {job: (start, sorted(pools)) for job, (start, pools) in out.items()}


def per_job(model_stack: dict, cluster_stack: dict, stack: str) -> list[str]:
    """Jobs whose start differs most between model and cluster first, with the GPU pools each ran on."""
    m, c = _jobs(model_stack["placements"]), _jobs(cluster_stack["placements"])
    rows = []
    for job in sorted(set(m) & set(c)):
        (ms, mp), (cs, cp) = m[job], c[job]
        delta = None if ms is None or cs is None else (cs - ms) / 3600
        rows.append((-(abs(delta) if delta is not None else float("inf")), job, ms, cs, delta, mp, cp))
    h = lambda t: "-" if t is None else f"{t / 3600:.2f}"   # noqa: E731
    lines = [f"### Per job: {stack}", "", "| Job | Model start (h) | Cluster start (h) | Difference (h) | Model pools | Cluster pools |",
             "|---|---|---|---|---|---|"]
    for _, job, ms, cs, delta, mp, cp in sorted(rows):
        lines.append(f"| {job} | {h(ms)} | {h(cs)} | {'-' if delta is None else f'{delta:+.2f}'} | {', '.join(mp) or '-'} | "
                     f"{', '.join(cp) or '-'} |")
    return lines


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
    for st in stacks:
        if "placements" in model["stacks"][st] and "placements" in cluster["stacks"][st]:
            lines += [""] + per_job(model["stacks"][st], cluster["stacks"][st], st)
    return "\n".join(lines) + "\n"
