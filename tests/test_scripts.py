import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ScriptTests(unittest.TestCase):
    def test_scripts_are_valid_bash_and_executable(self):
        scripts = sorted((ROOT / "scripts").glob("*.sh"))
        self.assertTrue(scripts)
        for script in scripts:
            with self.subTest(script=script.name):
                self.assertEqual(subprocess.run(["bash", "-n", str(script)], capture_output=True).returncode, 0)
                self.assertTrue(script.stat().st_mode & 0o111, "not executable")
                self.assertIn("set -euo pipefail", script.read_text())

    def test_kwok_stages_include_the_delayed_pod_completion(self):
        text = (ROOT / "scripts/cluster-up.sh").read_text()
        self.assertIn("pod/general", text)            # the fast pod stages complete pods immediately
        self.assertIn('KWOK_VERSION="${KWOK_VERSION:-v', text)
