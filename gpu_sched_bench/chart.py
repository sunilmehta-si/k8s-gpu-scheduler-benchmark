"""Small, dependency-free SVG bar charts of a results file, for READMEs and reports.

Bars share one colour (the stacks are categories, not a scale), values are printed at the end of each bar, and the
SVG adapts to light and dark themes through prefers-color-scheme.
"""
from __future__ import annotations

from xml.sax.saxutils import escape

PANELS = [  # (title, path into a stack's results, unit formatter, lower_is_better)
    ("Cost per useful GPU-hour", ("cost", "per_useful_gpu_h"), lambda v: f"${v:.2f}", True),
    ("Time to finish all work", ("makespan_h",), lambda v: f"{v:.1f} h", True),
    ("Queue wait p95", ("queue_wait", "p95_min"), lambda v: f"{v:,.0f} min", True),
]
STYLE = """
.t{font:600 14px system-ui,-apple-system,Segoe UI,sans-serif;fill:#1f2328}
.l{font:13px system-ui,-apple-system,Segoe UI,sans-serif;fill:#1f2328}
.v{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;fill:#59636e}
.n{font:12px system-ui,-apple-system,Segoe UI,sans-serif;fill:#59636e}
.b{fill:#2f6fde}.best{fill:#1a7f37}.g{stroke:#d1d9e0}
@media (prefers-color-scheme: dark){.t,.l{fill:#f0f6fc}.v,.n{fill:#9198a1}.b{fill:#4493f8}.best{fill:#3fb950}.g{stroke:#3d444d}}
"""


def _get(data: dict, path: tuple):
    for key in path:
        data = data.get(key) if isinstance(data, dict) else None
    return data


def svg(results: dict, title: str = "") -> str:
    stacks = list(results["stacks"])
    label_w, bar_w, row_h, panel_gap, width = 90, 330, 24, 26, 560
    height = 34 + len(PANELS) * (28 + len(stacks) * row_h + panel_gap)
    fleet, trace = results["fleet"], results["trace"]
    heading = title or f"{fleet['name']}: {trace['jobs']} jobs on {fleet['gpus']} GPUs ({results.get('mode', '')})"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
           f'role="img" aria-labelledby="title desc">',
           f"<title id=\"title\">{escape(heading)}</title>",
           f"<desc id=\"desc\">Bar charts comparing {', '.join(stacks)}. Shorter bars are better; the best stack is green.</desc>",
           f"<style>{STYLE}</style>", f'<text class="t" x="0" y="18">{escape(heading)}</text>']
    y = 34
    for label, path, fmt, lower in PANELS:
        values = {s: _get(results["stacks"][s], path) for s in stacks}
        numbers = [v for v in values.values() if isinstance(v, (int, float))]
        top = max(numbers, default=0) or 1
        best = (min if lower else max)(numbers) if numbers else None
        out.append(f'<text class="l" x="0" y="{y + 16}">{escape(label)} <tspan class="n">(lower is better)</tspan></text>')
        y += 26
        out.append(f'<line class="g" x1="{label_w}" y1="{y - 2}" x2="{label_w}" y2="{y + len(stacks) * row_h - 4}"/>')
        for s in stacks:
            v = values[s]
            w = 0 if not isinstance(v, (int, float)) else max(2, round(v / top * bar_w))
            cls = "best" if v == best and len(set(numbers)) > 1 else "b"
            out.append(f'<text class="n" x="{label_w - 8}" y="{y + 15}" text-anchor="end">{escape(s)}</text>')
            out.append(f'<rect class="{cls}" x="{label_w}" y="{y + 3}" width="{w}" height="{row_h - 8}" rx="3"/>')
            out.append(f'<text class="v" x="{label_w + w + 6}" y="{y + 15}">{escape(fmt(v)) if v is not None else "-"}</text>')
            y += row_h
        y += panel_gap
    out.append("</svg>")
    return "\n".join(out) + "\n"
