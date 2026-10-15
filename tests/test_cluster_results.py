"""The committed cluster runs must be real cluster runs that passed their runtime check."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CommittedClusterRunTests(unittest.TestCase):
    def test_every_stack_ran_on_a_cluster_and_passed_the_runtime_check(self):
        for stack in ("default", "kueue", "volcano", "kai"):
            with self.subTest(stack=stack):
                run = json.loads((ROOT / f"results/cluster/cluster-{stack}.json").read_text())
                model = json.loads((ROOT / f"results/cluster/model-{stack}.json").read_text())
                self.assertEqual((run["mode"], model["mode"]), ("cluster", "simulation"))
                self.assertTrue(run["runtime_check"]["ok"])
                self.assertEqual(run["stacks"][stack]["jobs_finished"], run["stacks"][stack]["jobs"])
                self.assertEqual(run["trace"]["name"], model["trace"]["name"])
