import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from gpu_sched_bench.cli import main

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {"lab-32-8h.jsonl": ["--fleet", "fleets/lab-32.yaml", "--hours", "8", "--rate", "2.5", "--seed", "7"],
           "mixed-256-8h.jsonl": ["--fleet", "fleets/mixed-256.yaml", "--hours", "8", "--rate", "16", "--seed", "7"],
           "dc-1024-8h.jsonl": ["--fleet", "fleets/dc-1024.yaml", "--hours", "8", "--rate", "72", "--seed", "7"],
           "lab-32-smoke.jsonl": ["--fleet", "fleets/lab-32.yaml", "--hours", "1", "--rate", "10", "--seed", "13"]}


class TraceCliTests(unittest.TestCase):
    def test_committed_samples_regenerate_exactly(self):
        for name, args in SAMPLES.items():
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(main(["trace", "generate", *[str(ROOT / a) if a.startswith("fleets/") else a for a in args]]), 0)
            self.assertEqual(buf.getvalue(), (ROOT / "traces" / name).read_text(), name)

    def test_stats_reports_demand(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["trace", "stats", str(ROOT / "traces/lab-32-8h.jsonl"), "--fleet", str(ROOT / "fleets/lab-32.yaml")])
        self.assertIn("26 jobs", buf.getvalue())
        self.assertIn("demand: 105% of lab-32", buf.getvalue())

    def test_job_size_cap_keeps_every_job_placeable(self):
        from gpu_sched_bench.trace import load
        jobs = load(ROOT / "traces/lab-32-8h.jsonl")
        self.assertLessEqual(max(j.gpus for j in jobs), 16)   # half of the 32-GPU lab
