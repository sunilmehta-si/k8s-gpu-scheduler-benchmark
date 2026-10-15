"""The committed results and report must match what the code produces today, so the README never drifts."""
import json
import unittest
from pathlib import Path

from gpu_sched_bench import results
from gpu_sched_bench.fleet import load as load_fleet
from gpu_sched_bench.presets import STACKS
from gpu_sched_bench.report import to_markdown
from gpu_sched_bench.trace import load as load_trace

ROOT = Path(__file__).resolve().parents[1]
RUNS = ["mixed-256", "lab-32"]


class CommittedResultsTests(unittest.TestCase):
    def test_results_regenerate_exactly(self):
        for name in RUNS:
            fresh = results.run(load_fleet(ROOT / f"fleets/{name}.yaml"), load_trace(ROOT / f"traces/{name}-8h.jsonl"),
                                list(STACKS), "equal", trace_name=f"{name}-8h.jsonl")
            committed = json.loads((ROOT / f"results/{name}.json").read_text())
            self.assertEqual(fresh, committed, f"results/{name}.json is stale: rerun gsb simulate")

    def test_report_matches_results(self):
        expected = "\n".join(to_markdown(json.loads((ROOT / f"results/{n}.json").read_text())) for n in RUNS)
        self.assertEqual((ROOT / "results/README.md").read_text(), expected, "results/README.md is stale: rerun gsb report")


class CommittedSweepAndChartTests(unittest.TestCase):
    def test_sweep_regenerates_exactly(self):
        from gpu_sched_bench.sweep import run_sweep
        fresh = run_sweep(load_fleet(ROOT / "fleets/mixed-256.yaml"), list(STACKS), list(range(1, 11)), rate=16, hours=8)
        self.assertEqual(fresh, json.loads((ROOT / "results/sweep-mixed-256.json").read_text()),
                         "results/sweep-mixed-256.json is stale: rerun gsb sweep")
        self.assertEqual((ROOT / "results/sweep-mixed-256.md").read_text(), to_markdown(fresh))

    def test_charts_match_results(self):
        from gpu_sched_bench.chart import svg
        titles = {"mixed-256": "256-GPU fleet, 131 jobs (reference simulation)", "lab-32": "32-GPU lab, 26 jobs (reference simulation)"}
        for name, title in titles.items():
            data = json.loads((ROOT / f"results/{name}.json").read_text())
            self.assertEqual((ROOT / f"results/{name}.svg").read_text(), svg(data, title), f"results/{name}.svg is stale")
