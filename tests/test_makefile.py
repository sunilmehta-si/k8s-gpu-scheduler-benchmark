"""`make results` must produce exactly what the committed-results tests expect."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MakefileTests(unittest.TestCase):
    def test_results_target_regenerates_every_committed_artifact(self):
        text = (ROOT / "Makefile").read_text()
        target = text.split("results:", 1)[1].split("\n\n", 1)[0]
        written = set(re.findall(r"-o (results/[\w.-]+)", target))
        committed = {f"results/{p.name}" for p in (ROOT / "results").iterdir()}
        self.assertEqual(written, committed)

    def test_recipes_use_tabs(self):
        for line in (ROOT / "Makefile").read_text().splitlines():
            if line.startswith(" ") and line.strip():
                self.fail(f"recipe lines must start with a tab: {line!r}")
