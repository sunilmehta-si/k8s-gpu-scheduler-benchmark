import unittest

from gpu_sched_bench.fleet import FleetError, parse

FLEET = {"name": "lab", "pools": [
    {"name": "h100", "count": 2, "gpus_per_node": 8, "price_per_gpu_hour": 2.5},
    {"name": "l4", "count": 3, "gpus_per_node": 2, "gpu_model": "NVIDIA-L4", "taints": ["gpu=l4:NoSchedule"]},
]}


class FleetTests(unittest.TestCase):
    def test_nodes_and_totals(self):
        fleet = parse(FLEET)
        self.assertEqual(fleet.total_gpus, 22)
        self.assertEqual(fleet.max_gpus_per_node, 8)
        self.assertEqual([n.name for n in fleet.nodes], ["h100-000", "h100-001", "l4-000", "l4-001", "l4-002"])
        self.assertEqual(fleet.nodes[0].price_per_gpu_hour, 2.5)

    def test_mistakes_are_explained(self):
        cases = {
            "must be a non-empty list": {"pools": []},
            "must be a DNS label": {"pools": [{"name": "H100", "count": 1, "gpus_per_node": 8}]},
            "count must be a positive integer": {"pools": [{"name": "a", "count": 0, "gpus_per_node": 8}]},
            "unknown key": {"pools": [{"name": "a", "count": 1, "gpus_per_node": 8, "gpu": 1}]},
            "taint": {"pools": [{"name": "a", "count": 1, "gpus_per_node": 8, "taints": ["bad"]}]},
            "Duplicate pool": {"pools": [{"name": "a", "count": 1, "gpus_per_node": 8}] * 2},
        }
        for message, data in cases.items():
            with self.subTest(message=message), self.assertRaisesRegex(FleetError, message):
                parse(data)


class SampleFleetTests(unittest.TestCase):
    def test_bundled_fleets_load(self):
        from pathlib import Path

        from gpu_sched_bench.fleet import load
        root = Path(__file__).resolve().parents[1] / "fleets"
        totals = {p.stem: load(p).total_gpus for p in sorted(root.glob("*.yaml"))}
        self.assertEqual(totals, {"lab-32": 32, "mixed-256": 256})
