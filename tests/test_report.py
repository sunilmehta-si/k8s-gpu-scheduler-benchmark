import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from gpu_sched_bench.cli import main
from gpu_sched_bench.report import _row, to_markdown

ROOT = Path(__file__).resolve().parents[1]


class ReportTests(unittest.TestCase):
    def test_best_value_is_bold_in_the_right_direction(self):
        stacks = {"a": {"x": 0.5, "jobs": 1}, "b": {"x": 0.9, "jobs": 1}}
        self.assertEqual(_row("X", ("x",), True, lambda v, m: str(v), stacks), "| X <sub>higher is better</sub> | 0.5 | **0.9** |")
        self.assertEqual(_row("X", ("x",), False, lambda v, m: str(v), stacks), "| X <sub>lower is better</sub> | **0.5** | 0.9 |")
        tie = {"a": {"x": 1}, "b": {"x": 1}}
        self.assertNotIn("**", _row("X", ("x",), True, lambda v, m: str(v), tie))   # nothing to highlight

    def test_report_from_a_real_run(self):
        out = Path(tempfile.mkdtemp()) / "r.json"
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            main(["simulate", "--fleet", str(ROOT / "fleets/lab-32.yaml"), "--trace", str(ROOT / "traces/lab-32-8h.jsonl"),
                  "-o", str(out)])
        md = to_markdown(json.loads(out.read_text()))
        self.assertIn("| Metric | default | kueue | volcano | kai |", md)
        self.assertIn("Reference simulation", md)
        self.assertIn("**Queue wait p95 by team (min)**", md)
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(main(["report", str(out)]), 0)
        self.assertEqual(buf.getvalue(), md)
