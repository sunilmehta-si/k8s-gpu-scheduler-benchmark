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


class FragmentationTests(unittest.TestCase):
    def test_spread_fragments_and_binpack_does_not(self):
        small = [job(f"s{i}", gpus=2, duration=600, kind="notebook") for i in range(4)]
        big = job("big", gpus=8, arrival=1, duration=60)
        spread = metrics.fragmentation(simulate(FLEET, small + [big], Policy("spread")))
        packed = metrics.fragmentation(simulate(FLEET, small + [big], Policy("binpack", placement="binpack")))
        # Spread leaves 4 free GPUs on each node while the 8-GPU job waits: all of them are unusable to it.
        self.assertEqual(spread["stranded_by_size"], 1.0)
        self.assertGreater(spread["idle_while_waiting_gpu_h"], 0)
        self.assertEqual(packed["idle_while_waiting_gpu_h"], 0.0)          # nothing ever waited
        self.assertGreater(spread["partial_nodes"], packed["partial_nodes"])

    def test_empty_fleet_time_is_not_fragmented(self):
        m = metrics.fragmentation(simulate(FLEET, [job("a", gpus=8)], Policy("default")))
        self.assertEqual((m["stranded_by_size"], m["scattered_free"], m["partial_nodes"]), (0.0, 0.0, 0.0))


class FairnessTests(unittest.TestCase):
    def test_jain_index(self):
        self.assertEqual(metrics.jain([1, 1, 1]), 1.0)
        self.assertEqual(metrics.jain([1, 0, 0, 0]), 0.25)
        self.assertIsNone(metrics.jain([]))

    def test_per_team_service_and_waits(self):
        jobs = [job("a1", team="a"), job("a2", team="a"), job("b1", team="b", arrival=1)]
        f = metrics.fairness(simulate(FLEET, jobs, Policy("default")))
        self.assertEqual(f["teams"]["a"]["jobs"], 2)
        self.assertEqual(f["teams"]["b"]["max_min"], round(599 / 60, 1))   # b waited for a GPU node
        self.assertEqual(f["teams"]["a"]["served_share"], 1.0)
        self.assertEqual(f["jain_served_share"], 1.0)                       # everyone finished in the end

    def test_deadlock_shows_up_as_unfair_service(self):
        jobs = [job("g1", replicas=2, gang=True, team="a"), job("g2", replicas=2, gpus=6, gang=True, team="b"),
                job("n", gpus=2, team="c", kind="notebook", arrival=5)]
        f = metrics.fairness(simulate(FLEET, jobs, Policy("default")))
        self.assertEqual(f["teams"]["a"]["never_started"], 1)
        self.assertLess(f["jain_served_share"], 1.0)
