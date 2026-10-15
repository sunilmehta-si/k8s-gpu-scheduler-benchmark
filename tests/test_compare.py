import copy
import unittest
from pathlib import Path

from gpu_sched_bench.compare import compare
from gpu_sched_bench.fleet import load as load_fleet
from gpu_sched_bench.results import run
from gpu_sched_bench.trace import load as load_trace

ROOT = Path(__file__).resolve().parents[1]
MODEL = run(load_fleet(ROOT / "fleets/lab-32.yaml"), load_trace(ROOT / "traces/lab-32-smoke.jsonl"), ["default", "kai"],
            trace_name="lab-32-smoke.jsonl")


def cluster_from(model, makespan_factor=1.1, ok=True):
    c = copy.deepcopy(model)
    c["mode"] = "cluster"
    c["stacks"] = {"kai": c["stacks"]["kai"]}
    c["stacks"]["kai"]["makespan_h"] = round(model["stacks"]["kai"]["makespan_h"] * makespan_factor, 2)
    c["runtime_check"] = {"ok": ok, "reason": "" if ok else "pods ran 0.00x their expected time"}
    return c


class CompareTests(unittest.TestCase):
    def test_side_by_side_with_differences(self):
        md = compare(MODEL, cluster_from(MODEL))
        self.assertIn("| Metric | kai model | kai cluster | difference |", md)
        self.assertIn("+10%", md)
        self.assertNotIn("Warning", md)

    def test_failed_runtime_check_is_called_out(self):
        self.assertIn("Warning", compare(MODEL, cluster_from(MODEL, ok=False)))

    def test_mismatched_inputs_are_refused(self):
        other = cluster_from(MODEL)
        other["trace"] = {**other["trace"], "name": "other.jsonl"}
        for bad, msg in ((other, "different fleets or traces"), (MODEL, "needs a simulation")):
            with self.assertRaisesRegex(ValueError, msg):
                compare(MODEL, bad)
