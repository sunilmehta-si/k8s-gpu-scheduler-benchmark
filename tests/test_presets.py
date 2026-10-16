import unittest

from gpu_sched_bench.fleet import parse
from gpu_sched_bench.presets import STACKS, equal_quotas, preset
from gpu_sched_bench.sim import simulate
from gpu_sched_bench.trace import Job

FLEET = parse({"name": "t", "pools": [{"name": "n", "count": 2, "gpus_per_node": 8}]})


class PresetTests(unittest.TestCase):
    def test_documented_defaults(self):
        q = equal_quotas(["a", "b"])
        d, k, v, kai = (preset(s, q) for s in STACKS)
        self.assertEqual((d.gang, d.placement, d.quotas), (False, "random", {}))
        self.assertEqual((k.gang, k.placement, k.borrowing, k.reclaim), (True, "random", True, True))
        self.assertEqual((v.gang, v.placement, v.borrowing, v.reclaim, v.enqueue_overcommit), (True, "random", True, False, 1.2))
        self.assertEqual((kai.gang, kai.placement, kai.reclaim), (True, "binpack", True))

    def test_without_teams_quota_features_are_off(self):
        self.assertEqual((preset("kai").quotas, preset("kai").borrowing, preset("kai").reclaim), ({}, False, False))

    def test_equal_quotas_and_unknown_stack(self):
        self.assertEqual(equal_quotas(["b", "a", "b", "c"]), {"a": 1 / 3, "b": 1 / 3, "c": 1 / 3})
        with self.assertRaisesRegex(ValueError, "unknown stack"):
            preset("slurm")

    def test_every_preset_runs_the_deadlock_case(self):
        jobs = [Job("g1", 0, "a", "training", 2, 8, 100, 0, True), Job("g2", 0, "b", "training", 2, 6, 100, 0, True)]
        outcomes = {s: simulate(FLEET, jobs, preset(s, equal_quotas(["a", "b"]))).deadlocked for s in STACKS}
        self.assertEqual(outcomes, {"default": True, "kueue": False, "volcano": False, "kai": False})
