"""The committed cluster runs must be real cluster runs that passed their runtime check."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CommittedClusterRunTests(unittest.TestCase):
    def test_every_stack_ran_on_a_cluster_and_passed_the_runtime_check(self):
        from gpu_sched_bench.presets import ALL_STACKS
        for stack in ALL_STACKS:
            with self.subTest(stack=stack):
                run = json.loads((ROOT / f"results/cluster/cluster-{stack}.json").read_text())
                model = json.loads((ROOT / f"results/cluster/model-{stack}.json").read_text())
                self.assertEqual((run["mode"], model["mode"]), ("cluster", "simulation"))
                self.assertTrue(run["runtime_check"]["ok"])
                self.assertLessEqual(run["runtime_check"]["median_start_lag_s"], 2.0)      # pods ran once bound
                self.assertTrue(all(p["node"] for p in run["stacks"][stack]["placements"]))
                self.assertEqual(run["stacks"][stack]["jobs_finished"], run["stacks"][stack]["jobs"])
                self.assertEqual(run["trace"]["name"], model["trace"]["name"])

    def test_bin_packing_gpus_beats_each_stack_as_installed_on_the_real_scheduler(self):
        def makespan(stack):
            return json.loads((ROOT / f"results/cluster/cluster-{stack}.json").read_text())["stacks"][stack]["makespan_h"]
        for stack in ("default", "volcano"):
            self.assertLess(makespan(f"{stack}-binpack"), makespan(stack), stack)
