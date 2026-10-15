import unittest

from gpu_sched_bench.fleet import parse
from gpu_sched_bench.sweep import METRICS, run_sweep

FLEET = parse({"name": "t", "pools": [{"name": "n", "count": 4, "gpus_per_node": 8, "price_per_gpu_hour": 2.0}]})


class SweepTests(unittest.TestCase):
    def test_summary_over_seeds(self):
        d = run_sweep(FLEET, ["default", "kai"], seeds=[1, 2, 3], rate=6, hours=2)
        self.assertEqual(d["mode"], "simulation-sweep")
        self.assertEqual([r["seed"] for r in d["per_seed"]], [1, 2, 3])
        for stack in ("default", "kai"):
            self.assertEqual(set(d["summary"][stack]), set(METRICS))
            s = d["summary"][stack]["makespan_h"]
            self.assertLessEqual(s["min"], s["mean"])
            self.assertLessEqual(s["mean"], s["max"])
        self.assertEqual(sum(d["cheapest_wins"].values()) >= 3, True)    # ties can credit several stacks

    def test_deterministic(self):
        a = run_sweep(FLEET, ["kai"], seeds=[5], rate=6, hours=2)
        self.assertEqual(a, run_sweep(FLEET, ["kai"], seeds=[5], rate=6, hours=2))
