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


class PinTrainingTests(unittest.TestCase):
    def test_only_training_is_pinned(self):
        jobs = generate(TraceSpec(hours=12, jobs_per_hour=20, seed=4, pin_training="H100"))
        self.assertTrue(all(j.gpu_model == "H100" for j in jobs if j.kind == "training"))
        self.assertTrue(all(j.gpu_model == "" for j in jobs if j.kind != "training"))
        self.assertEqual([j.id for j in jobs], [j.id for j in generate(TraceSpec(hours=12, jobs_per_hour=20, seed=4))])

    def test_cli_rejects_a_model_the_fleet_lacks(self):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from pathlib import Path

        from gpu_sched_bench.cli import main
        fleet = str(Path(__file__).resolve().parents[1] / "fleets/mixed-256.yaml")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(["trace", "generate", "--fleet", fleet, "--pin-training", "B200"]), 2)
            self.assertEqual(main(["trace", "generate", "--fleet", fleet, "--pin-training", "NVIDIA-H100-80GB-HBM3"]), 0)
