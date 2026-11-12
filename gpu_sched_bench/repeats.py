"""Summarise many cluster runs of the same trace, so a real-scheduler claim rests on every run rather than one.

A stack that places GPU pods without looking at GPUs can land small pods on the big GPU nodes in one run and not in
the next, and its result jumps between two outcomes. One run shows only one of them. This module reads the
`gsb cluster run` files that CI uploads for each run, keeps a few numbers per run and stack, and reports the median,
the range and, when a stack's cost falls into separate groups, each group and how often it happened.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from . import __version__

# Metrics kept per run: (key, extractor from one stack's cluster results)
METRICS = {
    "makespan_h": lambda s: s["makespan_h"],
    "queue_wait_p95_min": lambda s: s["queue_wait"]["p95_min"] or 0.0,
    "stranded_gpu_h": lambda s: s["stranded_gpu_h"],
    "cost_per_useful_gpu_h": lambda s: s["cost"]["per_useful_gpu_h"] or 0.0,
}

# Two runs belong to different outcomes when the gap between their costs, with no run in between, is wider than this
# share of the stack's median cost. Run-to-run noise on the smoke trace is about 1-2%; the outcomes differ by 13-30%.
OUTCOME_GAP = 0.10

LABELS = {
    "default": "default kube-scheduler",
    "default-binpack": "default + GPU `MostAllocated` profile",
    "volcano": "Volcano",
    "volcano-binpack": "Volcano + `binpack.resources: nvidia.com/gpu`",
    "kueue": "Kueue",
    "kueue-binpack": "Kueue + GPU `MostAllocated` profile",
    "kai": "KAI Scheduler",
}


def _kind(job: str) -> str:
    return job.rsplit("-", 1)[0]


def pool(node: str) -> str:
    """kwok node names are <pool>-<index>, e.g. h100-001."""
    return node.rsplit("-", 1)[0]


def record(run: str, data: dict) -> list[dict]:
    """One row per stack in a `gsb cluster run` results file: the metrics, the nodes each job kind ran on, and the
    trace hour each job started (its last replica; None if one never started)."""
    if data.get("mode") != "cluster":
        raise ValueError(f"run {run}: not a cluster results file")
    rows = []
    for stack, s in data["stacks"].items():
        nodes: dict[str, set[str]] = {}
        starts: dict[str, float | None] = {}
        for p in s["placements"]:
            if p["node"]:
                nodes.setdefault(_kind(p["job"]), set()).add(p["node"])
            prev = starts.get(p["job"], 0.0)
            starts[p["job"]] = None if prev is None or p["start_s"] is None else max(prev, p["start_s"])
        rows.append({"run": run, "stack": stack, "tool_version": data.get("tool_version"),
                     **{k: f(s) for k, f in METRICS.items()},
                     "nodes": {k: sorted(v) for k, v in sorted(nodes.items())},
                     "starts_h": {j: None if v is None else round(v / 3600, 2) for j, v in sorted(starts.items())}})
    return rows


def collect(root: Path) -> tuple[list[dict], list[str]]:
    """Read `<root>/<run id>/**/cluster-*.json`. Returns the rows and the files skipped for a failed runtime check."""
    rows, skipped = [], []
    for path in sorted(root.glob("*/**/cluster-*.json")):
        run = path.relative_to(root).parts[0]
        data = json.loads(path.read_text())
        if not data.get("runtime_check", {}).get("ok"):
            skipped.append(str(path))
            continue
        rows += record(run, data)
    if not rows:
        raise ValueError(f"no passing cluster results under {root} (expected <run id>/**/cluster-*.json)")
    rows.sort(key=lambda r: (int(r["run"]) if r["run"].isdigit() else 0, r["run"], r["stack"]))
    return rows, skipped


def _stats(values: list[float]) -> dict:
    return {"median": round(statistics.median(values), 3), "min": round(min(values), 3), "max": round(max(values), 3)}


def outcomes(rows: list[dict]) -> list[list[dict]]:
    """Group one stack's runs by cost, splitting where neighbouring costs differ by more than OUTCOME_GAP of the
    median. Most frequent group first."""
    ordered = sorted(rows, key=lambda r: r["cost_per_useful_gpu_h"])
    gap = OUTCOME_GAP * statistics.median(r["cost_per_useful_gpu_h"] for r in rows)
    groups: list[list[dict]] = [[ordered[0]]]
    for prev, cur in zip(ordered, ordered[1:]):
        if cur["cost_per_useful_gpu_h"] - prev["cost_per_useful_gpu_h"] > gap:
            groups.append([])
        groups[-1].append(cur)
    return sorted(groups, key=lambda g: (-len(g), g[0]["cost_per_useful_gpu_h"]))


def summarise(rows: list[dict]) -> dict:
    by_stack: dict[str, list[dict]] = {}
    for r in rows:
        by_stack.setdefault(r["stack"], []).append(r)
    stacks = {}
    for stack, rs in by_stack.items():
        stacks[stack] = {
            "runs": len(rs),
            **{k: _stats([r[k] for r in rs]) for k in METRICS},
            "outcomes": [{"runs": len(g), "run_ids": [r["run"] for r in g], **{k: _stats([r[k] for r in g]) for k in METRICS}}
                         for g in outcomes(rs)],
        }
    return {"runs": sorted({r["run"] for r in rows}, key=lambda x: (int(x) if x.isdigit() else 0, x)), "stacks": stacks}


def build(rows: list[dict], source: str = "") -> dict:
    return {"schema_version": 1, "tool_version": __version__, "source": source, "summary": summarise(rows), "rows": rows}


def _order(stacks: dict) -> list[str]:
    return [s for s in LABELS if s in stacks] + sorted(s for s in stacks if s not in LABELS)


def cost_cell(st: dict) -> str:
    """'$3.97' when every run agrees; '$5.20 in 22 runs, $3.98 in 8' when the stack's runs split into outcomes."""
    outs = st["outcomes"]
    if len(outs) == 1:
        return f"${st['cost_per_useful_gpu_h']['median']:.2f}"
    first, *rest = outs
    return f"${first['cost_per_useful_gpu_h']['median']:.2f} in {first['runs']} runs, " + ", ".join(
        f"${o['cost_per_useful_gpu_h']['median']:.2f} in {o['runs']}" for o in rest)


def readme_table(summary: dict) -> str:
    """The real-scheduler table in the README: medians over every run, and each outcome's cost where runs split."""
    lines = ["| Real scheduler | Time to finish | Queue wait p95 | Cost per useful GPU-hour |", "|---|---|---|---|"]
    for stack in _order(summary["stacks"]):
        st = summary["stacks"][stack]
        lines.append(f"| {LABELS.get(stack, stack)} | {st['makespan_h']['median']:.1f} h | "
                     f"{st['queue_wait_p95_min']['median']:.0f} min | {cost_cell(st)} |")
    return "\n".join(lines) + "\n"


def to_markdown(doc: dict) -> str:
    summary, rows = doc["summary"], doc["rows"]
    runs = summary["runs"]
    lines = [f"## Repeated cluster runs: {len(runs)} runs", ""]
    if doc.get("source"):
        lines += [doc["source"], ""]
    lines += ["Medians, with the range over every run in brackets. Where a stack's cost splits into separate outcomes, "
              "each outcome is listed below.", "",
              "| Stack | Runs | Time to finish (h) | Queue wait p95 (min) | Stranded GPU-hours | Cost per useful GPU-hour |",
              "|---|---|---|---|---|---|"]
    fmt = {"makespan_h": "{:.2f}", "queue_wait_p95_min": "{:.0f}", "stranded_gpu_h": "{:.1f}", "cost_per_useful_gpu_h": "${:.2f}"}

    def cell(stats: dict, key: str) -> str:
        f = fmt[key]
        return f"{f.format(stats['median'])} ({f.format(stats['min'])}-{f.format(stats['max'])})"

    for stack in _order(summary["stacks"]):
        st = summary["stacks"][stack]
        lines.append(f"| {stack} | {st['runs']} | " + " | ".join(cell(st[k], k) for k in METRICS) + " |")
    split = [s for s in _order(summary["stacks"]) if len(summary["stacks"][s]["outcomes"]) > 1]
    if split:
        lines += ["", "### Stacks whose runs split into outcomes", "",
                  "| Stack | Runs | Time to finish (h) | Queue wait p95 (min) | Stranded GPU-hours | Cost per useful GPU-hour |",
                  "|---|---|---|---|---|---|"]
        for stack in split:
            for o in summary["stacks"][stack]["outcomes"]:
                lines.append(f"| {stack} | {o['runs']} | " + " | ".join(cell(o[k], k) for k in METRICS) + " |")
    stacks = _order(summary["stacks"])
    lines += ["", "### Cost per useful GPU-hour, run by run", "", "| Run | " + " | ".join(stacks) + " |",
              "|---|" + "---|" * len(stacks)]
    table: dict[str, dict[str, float]] = {}
    for r in rows:
        table.setdefault(r["run"], {})[r["stack"]] = r["cost_per_useful_gpu_h"]
    for run in runs:
        lines.append(f"| {run} | " + " | ".join(f"${table[run][s]:.2f}" if s in table[run] else "-" for s in stacks) + " |")
    return "\n".join(lines) + "\n"
