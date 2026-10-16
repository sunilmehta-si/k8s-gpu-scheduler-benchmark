import unittest
from pathlib import Path

from gpu_sched_bench.ablate import run_ablation, variants
from gpu_sched_bench.fleet import load as load_fleet
from gpu_sched_bench.report import to_markdown
from gpu_sched_bench.trace import load as load_trace

ROOT = Path(__file__).resolve().parents[1]


class AblationTests(unittest.TestCase):
    def test_steps_are_cumulative(self):
        names = [p.name for p in variants({"a": 0.5, "b": 0.5})]
        self.assertEqual(names, ["1 default", "2 + gang", "3 + gang, binpack", "4 + quotas", "5 + borrowing",
                                 "6 + reclaim", "binpack only", "GPU spread only"])
        self.assertEqual([p.name for p in variants({})],
                         ["1 default", "2 + gang", "3 + gang, binpack", "binpack only", "GPU spread only"])
        self.assertEqual(variants({})[0].placement, "random")        # kube-scheduler's scoring ignores GPUs
        reclaim = variants({"a": 1.0})[5]
        self.assertTrue(reclaim.gang and reclaim.borrowing and reclaim.reclaim and reclaim.placement == "binpack")

    def test_gang_removes_stranding_on_the_sample(self):
        doc = run_ablation(load_fleet(ROOT / "fleets/mixed-256.yaml"), load_trace(ROOT / "traces/mixed-256-8h.jsonl"))
        s = doc["stacks"]
        self.assertGreater(s["1 default"]["stranded_gpu_h"], 0)
        self.assertEqual(s["2 + gang"]["stranded_gpu_h"], 0)
        self.assertIn("| Metric | 1 default | 2 + gang |", to_markdown(doc))
        # spreading by GPUs, not the lack of bin-packing, is what slows this trace down
        self.assertGreater(s["GPU spread only"]["makespan_h"], s["1 default"]["makespan_h"])
        self.assertEqual(s["binpack only"]["makespan_h"], s["1 default"]["makespan_h"])
