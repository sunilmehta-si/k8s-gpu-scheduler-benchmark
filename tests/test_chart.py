import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from gpu_sched_bench.chart import svg

ROOT = Path(__file__).resolve().parents[1]


class ChartTests(unittest.TestCase):
    def test_valid_accessible_svg_with_one_bar_per_stack_and_panel(self):
        data = json.loads((ROOT / "results/mixed-256.json").read_text())
        root = ET.fromstring(svg(data))
        ns = "{http://www.w3.org/2000/svg}"
        self.assertEqual(root.get("role"), "img")
        self.assertIn("mixed-256", root.find(f"{ns}title").text)
        bars = root.findall(f"{ns}rect")
        self.assertEqual(len(bars), 3 * 4)                       # three panels x four stacks
        # all four stacks tie on cost and on time to finish on this trace, so neither panel has a winner;
        # kai alone is best on queue wait
        self.assertEqual(sum(1 for b in bars if b.get("class") == "best"), 0 + 0 + 1)
        self.assertIn("prefers-color-scheme: dark", root.find(f"{ns}style").text)

    def test_cli(self):
        import tempfile

        from gpu_sched_bench.cli import main
        out = Path(tempfile.mkdtemp()) / "c.svg"
        self.assertEqual(main(["chart", str(ROOT / "results/lab-32.json"), "-o", str(out), "--title", "Lab"]), 0)
        self.assertIn("<title id=\"title\">Lab</title>", out.read_text())
