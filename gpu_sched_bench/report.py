"""Render a results JSON as a Markdown comparison: stacks as columns, the best value per row in bold."""
from __future__ import annotations

# (label, path into a stack's results, higher_is_better, formatter)
ROWS = [
    ("Jobs finished", ("jobs_finished",), True, lambda v, m: f"{v}/{m['jobs']}"),
    ("Deadlocked", ("deadlocked",), False, lambda v, m: "yes" if v else "no"),
    ("Makespan (h)", ("makespan_h",), False, lambda v, m: f"{v:.1f}"),
    ("GPU utilisation", ("utilisation",), True, lambda v, m: f"{v:.1%}"),
    ("Useful utilisation", ("useful_utilisation",), True, lambda v, m: f"{v:.1%}"),
    ("Queue wait p50 (min)", ("queue_wait", "p50_min"), False, lambda v, m: f"{v:.1f}"),
    ("Queue wait p95 (min)", ("queue_wait", "p95_min"), False, lambda v, m: f"{v:.1f}"),
    ("Training wait p95 (min)", ("queue_wait_by_kind", "training", "p95_min"), False, lambda v, m: f"{v:.1f}"),
    ("Notebook wait p95 (min)", ("queue_wait_by_kind", "notebook", "p95_min"), False, lambda v, m: f"{v:.1f}"),
    ("Stranded GPU-hours", ("stranded_gpu_h",), False, lambda v, m: f"{v:,.1f}"),
    ("Preempted work (GPU-h)", ("preempted_gpu_h",), False, lambda v, m: f"{v:,.1f}"),
    ("GPU-h idle while work waited", ("fragmentation", "idle_while_waiting_gpu_h"), False, lambda v, m: f"{v:,.1f}"),
    ("Idle GPUs too small for waiting work", ("fragmentation", "stranded_by_size"), False, lambda v, m: f"{v:.1%}"),
    ("Partly used nodes (fragmentation)", ("fragmentation", "partial_nodes"), False, lambda v, m: f"{v:.1%}"),
    ("Fairness between teams (Jain)", ("fairness", "jain_service"), True, lambda v, m: "-" if v is None else f"{v:.3f}"),
    ("Fleet cost until the last job finished", ("cost", "total"), False, lambda v, m: f"${v:,.0f}"),
    ("Cost per useful GPU-hour", ("cost", "per_useful_gpu_h"), False, lambda v, m: "-" if v is None else f"${v:.2f}"),
]


def _get(data: dict, path: tuple):
    for key in path:
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


def _row(label: str, path: tuple, higher: bool, fmt, stacks: dict) -> str:
    values = {s: _get(m, path) for s, m in stacks.items()}
    numeric = {s: v for s, v in values.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    best = set()
    if len(set(numeric.values())) > 1:
        target = (max if higher else min)(numeric.values())
        best = {s for s, v in numeric.items() if v == target}
    cells = []
    for s, v in values.items():
        text = "-" if v is None else fmt(v, stacks[s])
        cells.append(f"**{text}**" if s in best else text)
    arrow = "higher is better" if higher else "lower is better"
    return f"| {label} <sub>{arrow}</sub> | " + " | ".join(cells) + " |"


SWEEP_ROWS = [  # (label, metric key, formatter for one number)
    ("Makespan (h)", "makespan_h", lambda v: f"{v:.1f}"),
    ("Useful utilisation", "useful_utilisation", lambda v: f"{v:.1%}"),
    ("Queue wait p95 (min)", "queue_wait_p95_min", lambda v: f"{v:.0f}"),
    ("Stranded GPU-hours", "stranded_gpu_h", lambda v: f"{v:,.0f}"),
    ("Preempted work (GPU-h)", "preempted_gpu_h", lambda v: f"{v:,.0f}"),
    ("Cost per useful GPU-hour", "cost_per_useful_gpu_h", lambda v: f"${v:.2f}"),
    ("Fairness between teams (Jain)", "fairness", lambda v: f"{v:.3f}"),
]


def sweep_to_markdown(sweep: dict) -> str:
    from .sweep import METRICS
    stacks = list(sweep["summary"])
    n = len(sweep["seeds"])
    lines = [f"## {sweep['fleet']['name']}: {n} seeded traces, {sweep['rate_per_hour']:g} jobs/hour for {sweep['hours']:g} h", "",
             f"> Reference simulation. Each cell is the mean ± standard deviation over {n} traces, with the range in brackets.", "",
             "| Metric | " + " | ".join(stacks) + " |", "|---|" + "---|" * len(stacks)]
    for label, key, fmt in SWEEP_ROWS:
        lower = METRICS[key][1]
        means = {s: sweep["summary"][s][key]["mean"] for s in stacks}
        target = (min if lower else max)(means.values())
        cells = []
        for s in stacks:
            m = sweep["summary"][s][key]
            text = f"{fmt(m['mean'])} ± {fmt(m['stdev'])} ({fmt(m['min'])}–{fmt(m['max'])})"
            cells.append(f"**{text}**" if means[s] == target and len(set(means.values())) > 1 else text)
        lines.append(f"| {label} <sub>{'lower' if lower else 'higher'} is better</sub> | " + " | ".join(cells) + " |")
    wins = sweep["cheapest_wins"]
    lines.append("| Cheapest per useful GPU-hour | " + " | ".join(f"{wins[s]}/{n} seeds" for s in stacks) + " |")
    return "\n".join(lines) + "\n"


def to_markdown(results: dict) -> str:
    if results.get("mode") == "simulation-sweep":
        return sweep_to_markdown(results)
    stacks = results["stacks"]
    names = list(stacks)
    fleet, trace = results["fleet"], results["trace"]
    lines = [f"## {fleet['name']}: {fleet['gpus']} GPUs on {fleet['nodes']} nodes, {trace['jobs']} jobs "
             f"({trace['requested_gpu_h']:,.0f} GPU-hours requested)", ""]
    if results.get("mode") == "simulation":
        lines += ["> Reference simulation of each stack's documented default behaviour, not a run of the schedulers "
                  "themselves. See [the methodology](../docs/methodology.md).", ""]
    lines += ["| Metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    lines += [_row(label, path, higher, fmt, stacks) for label, path, higher, fmt in ROWS]
    teams = sorted({t for m in stacks.values() for t in m["fairness"]["teams"]})
    if teams:
        lines += ["", "**Queue wait p95 by team (min)**", "", "| Team | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
        for t in teams:
            cells = [_get(m, ("fairness", "teams", t, "p95_min")) for m in stacks.values()]
            lines.append(f"| {t} | " + " | ".join("-" if c is None else f"{c:.1f}" for c in cells) + " |")
        lines += ["", "**GPU cost by team**", "", "| Team | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
        for t in teams:
            cells = [_get(m, ("cost", "by_team", t)) for m in stacks.values()]
            lines.append(f"| {t} | " + " | ".join("-" if c is None else f"${c:,.0f}" for c in cells) + " |")
    return "\n".join(lines) + "\n"
