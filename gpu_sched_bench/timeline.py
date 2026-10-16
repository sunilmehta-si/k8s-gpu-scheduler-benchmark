"""Per-node timeline of a results file's placements: which job held which node, and when.

Reading this next to the model's timeline for the same trace shows where a real scheduler's choices
diverged: a small pod on a big node, a gang waiting for its last replica, a node left idle."""
from __future__ import annotations


def _h(t: float | None) -> str:
    return "-" if t is None else f"{t / 3600:.2f}"


def timeline(results: dict, stack: str) -> str:
    if stack not in results["stacks"]:
        raise ValueError(f"no stack '{stack}' in this file; it has {', '.join(results['stacks'])}")
    rows = results["stacks"][stack].get("placements")
    if rows is None:
        raise ValueError("this file has no placements; use a cluster run or gsb simulate --placements")
    lines = [f"## Timeline: {stack} ({results['mode']}), {results['fleet']['name']}, {results['trace']['name']}", "",
             "| Node | Job | Replica | Placed (h) | Start (h) | End (h) |", "|---|---|---|---|---|---|"]
    placed = sorted((r for r in rows if r["node"]), key=lambda r: (r["node"], r["placed_s"] or 0.0, r["job"], r["replica"]))
    for r in placed:
        lines.append(f"| {r['node']} | {r['job']} | {r['replica']} | {_h(r['placed_s'])} | {_h(r['start_s'])} | {_h(r['end_s'])} |")
    never = sorted({r["job"] for r in rows if not r["node"]})
    if never:
        lines += ["", f"Never placed: {', '.join(never)}."]
    return "\n".join(lines) + "\n"
