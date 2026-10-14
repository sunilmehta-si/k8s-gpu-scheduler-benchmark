import unittest

from gpu_sched_bench.fleet import parse
from gpu_sched_bench.sim import Policy, simulate
from gpu_sched_bench.trace import Job

FLEET = parse({"name": "t", "pools": [{"name": "n", "count": 2, "gpus_per_node": 8}]})


def job(id, arrival=0, replicas=1, gpus=8, duration=100, gang=False, priority=0, kind="training", team="a"):
    return Job(id, arrival, team, kind, replicas, gpus, duration, priority, gang)


class EngineTests(unittest.TestCase):
    def test_jobs_queue_when_full_and_start_when_capacity_frees(self):
        r = simulate(FLEET, [job("a"), job("b"), job("c", arrival=10)], Policy("default"))
        self.assertEqual((r.records["a"].start, r.records["b"].start), (0, 0))
        self.assertEqual(r.records["c"].start, 100)         # waited for a or b to finish
        self.assertEqual(r.records["c"].wait, 90)
        self.assertEqual(r.makespan, 200)
        self.assertEqual(r.allocated_gpu_s, 16 * 100 + 8 * 100)
        self.assertFalse(r.deadlocked)

    def test_spread_placement_uses_the_emptiest_node(self):
        r = simulate(FLEET, [job("a", gpus=2), job("b", gpus=2)], Policy("default"))
        self.assertNotEqual(r.records["a"].nodes[0], r.records["b"].nodes[0])

    def test_pod_by_pod_gangs_interleave_and_deadlock(self):
        # Submitted together, the pods interleave: g1-0 takes node A, g2-0 takes most of node B, and then
        # neither g1-1 (8 GPUs) nor g2-1 (6 GPUs) fits anywhere. Both gangs hold GPUs forever.
        r = simulate(FLEET, [job("g1", replicas=2, gang=True), job("g2", replicas=2, gpus=6, gang=True)], Policy("default"))
        self.assertTrue(r.deadlocked)
        self.assertEqual(r.unfinished, ["g1", "g2"])
        self.assertEqual((r.records["g1"].placed, r.records["g2"].placed), (1, 1))

    def test_partially_placed_gang_strands_gpus_until_complete(self):
        r = simulate(FLEET, [job("blocker", duration=50), job("g", replicas=2, gang=True, arrival=1)], Policy("default"))
        self.assertEqual(r.records["g"].start, 50)            # one replica waited 49 s for the other node
        self.assertEqual(r.stranded_gpu_s, 8 * 49)

    def test_independent_replicas_start_as_soon_as_placed(self):
        r = simulate(FLEET, [job("big", gpus=8, duration=50), job("inf", replicas=3, gpus=8, kind="inference")],
                     Policy("default"))
        starts = sorted(r.records["inf"].replica_start)
        self.assertEqual(starts, [0, 50, 100])               # each replica works as soon as it has a node
        self.assertEqual(r.records["inf"].start, 100)
        self.assertEqual(r.stranded_gpu_s, 0)                # independent replicas are never stranded


class GangTests(unittest.TestCase):
    def test_gang_admission_avoids_the_deadlock(self):
        jobs = [job("g1", replicas=2, gang=True), job("g2", replicas=2, gpus=6, gang=True)]
        r = simulate(FLEET, jobs, Policy("gang", gang=True))
        self.assertFalse(r.deadlocked)
        self.assertEqual((r.records["g1"].start, r.records["g2"].start), (0, 100))   # g2 runs after g1, nobody stuck
        self.assertEqual(r.stranded_gpu_s, 0)

    def test_gang_waits_whole_instead_of_holding_part(self):
        r = simulate(FLEET, [job("blocker", duration=50), job("g", replicas=2, gang=True, arrival=1)],
                     Policy("gang", gang=True))
        self.assertEqual(r.records["g"].start, 50)
        self.assertEqual(r.stranded_gpu_s, 0)            # nothing was held while it waited

    def test_smaller_jobs_backfill_around_a_waiting_gang(self):
        jobs = [job("blocker", duration=50), job("g", replicas=2, gang=True, arrival=1),
                job("small", gpus=4, arrival=2, duration=10)]
        r = simulate(FLEET, jobs, Policy("gang", gang=True))
        self.assertEqual(r.records["small"].start, 2)    # best-effort queue: the waiting gang doesn't block it


class PlacementTests(unittest.TestCase):
    def test_binpack_keeps_whole_nodes_free_for_big_jobs(self):
        small = [job(f"s{i}", gpus=2, duration=100, kind="notebook") for i in range(4)]
        big = job("big", gpus=8, arrival=1, duration=10)
        spread = simulate(FLEET, small + [big], Policy("spread", placement="spread"))
        packed = simulate(FLEET, small + [big], Policy("binpack", placement="binpack"))
        self.assertEqual(spread.records["big"].start, 100)   # 4 GPUs free on each node: the 8-GPU job can't fit
        self.assertEqual(packed.records["big"].start, 1)     # the small jobs share one node; the other is empty
        self.assertEqual(len({packed.records[f"s{i}"].nodes[0] for i in range(4)}), 1)

    def test_binpack_prefers_the_tightest_fit(self):
        jobs = [job("a", gpus=6, duration=100), job("b", gpus=3, duration=100, arrival=1), job("c", gpus=2, arrival=2)]
        r = simulate(FLEET, jobs, Policy("binpack", placement="binpack"))
        self.assertEqual(r.records["c"].nodes[0], r.records["a"].nodes[0])   # 2 GPUs left there: an exact fit

    def test_unknown_policy_values_are_rejected(self):
        with self.assertRaises(ValueError):
            Policy("x", placement="random")
