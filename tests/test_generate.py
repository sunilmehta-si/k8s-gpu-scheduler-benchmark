import unittest

from gpu_sched_bench.generate import TraceSpec, generate


class GenerateTests(unittest.TestCase):
    def test_same_seed_same_trace_and_different_seed_differs(self):
        a, b = generate(TraceSpec(hours=2, seed=1)), generate(TraceSpec(hours=2, seed=1))
        self.assertEqual(a, b)
        self.assertNotEqual(a, generate(TraceSpec(hours=2, seed=2)))

    def test_shapes_follow_the_spec(self):
        jobs = generate(TraceSpec(hours=24, jobs_per_hour=60, max_gpus_per_node=4, seed=3))
        self.assertGreater(len(jobs), 1000)
        self.assertTrue(all(j.gpus_per_replica <= 4 for j in jobs))          # capped to the fleet's node size
        self.assertTrue(all(j.duration_s >= 60 for j in jobs))
        self.assertTrue(all(j.gang == (j.kind in ("training", "finetune") and j.replicas > 1) for j in jobs))
        self.assertEqual({j.kind for j in jobs}, {"training", "finetune", "inference", "notebook"})
        self.assertEqual({j.team for j in jobs}, {"research", "product", "platform"})
        arrivals = [j.arrival_s for j in jobs]
        self.assertEqual(arrivals, sorted(arrivals))
        self.assertLess(arrivals[-1], 24 * 3600)
        rate = len(jobs) / 24
        self.assertTrue(50 < rate < 70, rate)                                # Poisson around 60/hour
