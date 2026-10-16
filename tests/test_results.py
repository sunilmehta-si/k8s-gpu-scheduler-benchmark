import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from gpu_sched_bench.cli import main

ROOT = Path(__file__).resolve().parents[1]
ARGS = ["simulate", "--fleet", str(ROOT / "fleets/lab-32.yaml"), "--trace", str(ROOT / "traces/lab-32-8h.jsonl")]


def run(*extra):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main([*ARGS, *extra])
    return code, buf.getvalue()


class SimulateCliTests(unittest.TestCase):
    def test_results_document(self):
        code, text = run()
        self.assertEqual(code, 0)
        data = json.loads(text)
        self.assertEqual((data["schema_version"], data["mode"]), (1, "simulation"))
        self.assertEqual(list(data["stacks"]), ["default", "kueue", "volcano", "kai"])
        self.assertEqual(data["fleet"]["gpus"], 32)
        kai = data["stacks"]["kai"]
        for key in ("utilisation", "queue_wait", "fragmentation", "fairness", "cost", "policy"):
            self.assertIn(key, kai)
        self.assertEqual(set(data["quotas"]), {"research", "product", "platform"})

    def test_deterministic(self):
        self.assertEqual(run()[1], run()[1])

    def test_stack_subset_and_errors(self):
        self.assertEqual(list(json.loads(run("--stacks", "kai", "--quotas", "none")[1])["stacks"]), ["kai"])
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main([*ARGS, "--stacks", "slurm"]), 2)
            self.assertEqual(main(["simulate", "--fleet", "missing.yaml", "--trace", ARGS[4]]), 2)


class PlacementsTests(unittest.TestCase):
    def test_every_replica_with_its_node_and_times(self):
        from gpu_sched_bench.fleet import parse
        from gpu_sched_bench.results import placements
        from gpu_sched_bench.sim import Policy, simulate
        from gpu_sched_bench.trace import Job
        fleet = parse({"name": "t", "pools": [{"name": "n", "count": 1, "gpus_per_node": 8}]})
        jobs = [Job("a", 0, "red", "training", 1, 8, 100), Job("b", 10, "red", "inference", 2, 4, 50, 0, False)]
        rows = placements(simulate(fleet, jobs, Policy("default")))
        self.assertEqual([(r["job"], r["replica"], r["node"], r["start_s"], r["end_s"]) for r in rows],
                         [("a", 0, "n-000", 0.0, 100.0), ("b", 0, "n-000", 100.0, 150.0), ("b", 1, "n-000", 100.0, 150.0)])
