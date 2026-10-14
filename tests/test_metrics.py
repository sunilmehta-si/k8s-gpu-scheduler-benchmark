import unittest

from gpu_sched_bench import metrics
from gpu_sched_bench.fleet import parse
from gpu_sched_bench.sim import Policy, simulate
from gpu_sched_bench.trace import Job

FLEET = parse({"name": "t", "pools": [{"name": "n", "count": 2, "gpus_per_node": 8}]})


def job(id, arrival=0, replicas=1, gpus=8, duration=600, gang=False, kind="training", team="a"):
    return Job(id, arrival, team, kind, replicas, gpus, duration, 0, gang)


class PercentileTests(unittest.TestCase):
    def test_nearest_rank(self):
        self.assertEqual(metrics.percentile([5, 1, 3, 2, 4], 50), 3)
        self.assertEqual(metrics.percentile(list(range(1, 101)), 95), 95)
        self.assertIsNone(metrics.percentile([], 50))


class CoreMetricTests(unittest.TestCase):
    def test_utilisation_and_waits(self):
        r = simulate(FLEET, [job("a"), job("b"), job("c", kind="notebook", gpus=8)], Policy("default"))
        m = metrics.core(r)
        self.assertEqual(m["makespan_h"], round(1200 / 3600, 2))
        self.assertEqual(m["utilisation"], round(3 * 8 * 600 / (16 * 1200), 4))
        self.assertEqual(m["queue_wait"]["max_min"], 10.0)                    # c waited one 600 s job
        self.assertEqual(m["queue_wait_by_kind"]["notebook"]["p50_min"], 10.0)
        self.assertEqual(m["jobs_finished"], 3)

    def test_stranded_gpus_lower_useful_utilisation(self):
        r = simulate(FLEET, [job("blocker", duration=300), job("g", replicas=2, gang=True, arrival=1)], Policy("default"))
        m = metrics.core(r)
        self.assertGreater(m["stranded_gpu_h"], 0)
        self.assertLess(m["useful_utilisation"], m["utilisation"])
