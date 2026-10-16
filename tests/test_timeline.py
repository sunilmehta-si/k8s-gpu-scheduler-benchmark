import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from gpu_sched_bench.cli import main
from gpu_sched_bench.timeline import timeline

DOC = {"mode": "cluster", "fleet": {"name": "lab"}, "trace": {"name": "t.jsonl"}, "stacks": {"volcano": {"placements": [
    {"job": "b", "replica": 0, "node": "n-001", "placed_s": 3600.0, "start_s": 3600.0, "end_s": 7200.0},
    {"job": "a", "replica": 0, "node": "n-001", "placed_s": 0.0, "start_s": 0.0, "end_s": 1800.0},
    {"job": "c", "replica": 0, "node": None, "placed_s": None, "start_s": None, "end_s": None}]}}}


class TimelineTests(unittest.TestCase):
    def test_rows_by_node_then_time_and_unplaced_jobs(self):
        text = timeline(DOC, "volcano")
        rows = [line for line in text.splitlines() if line.startswith("| n-")]
        self.assertEqual(rows, ["| n-001 | a | 0 | 0.00 | 0.00 | 0.50 |", "| n-001 | b | 0 | 1.00 | 1.00 | 2.00 |"])
        self.assertIn("Never placed: c.", text)

    def test_errors_name_the_problem(self):
        with self.assertRaisesRegex(ValueError, "no stack 'kai'"):
            timeline(DOC, "kai")
        with self.assertRaisesRegex(ValueError, "--placements"):
            timeline({**DOC, "stacks": {"kai": {}}}, "kai")

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "r.json"
            path.write_text(json.dumps(DOC))
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(["timeline", str(path), "--stack", "volcano"]), 0)
            self.assertIn("## Timeline: volcano (cluster)", out.getvalue())
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["timeline", str(path), "--stack", "kai"]), 2)
