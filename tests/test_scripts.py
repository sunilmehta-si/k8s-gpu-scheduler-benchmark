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
        self.assertIn('. "$(dirname "$0")/lib.sh"', text)                 # KWOK_VERSION comes from versions.env

    def test_every_version_lives_in_versions_env_and_the_environment_can_override_it(self):
        pins = dict(line.split("=", 1) for line in (ROOT / "cluster/versions.env").read_text().splitlines()
                    if line and not line.startswith("#"))
        for script in sorted((ROOT / "scripts").glob("*.sh")):
            text = script.read_text()
            with self.subTest(script=script.name):
                self.assertNotRegex(text, r"_VERSION:-", "a version default belongs in cluster/versions.env")
                for used in set(__import__("re").findall(r"\$\{?([A-Z]+_VERSION)\b", text)):
                    self.assertIn(used, pins)
        self.assertRegex(pins["KIND_NODE_IMAGE"], r"^kindest/node:v[\d.]+@sha256:[0-9a-f]{64}$")
        probe = 'source scripts/lib.sh; echo "$KAI_VERSION $KUEUE_VERSION"'
        out = subprocess.run(["bash", "-c", probe], cwd=ROOT, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
        self.assertEqual(out.stdout.split(), [pins["KAI_VERSION"], pins["KUEUE_VERSION"]])
        out = subprocess.run(["bash", "-c", probe], cwd=ROOT, capture_output=True, text=True,
                             env={"PATH": "/usr/bin:/bin", "KAI_VERSION": "9.9.9"})
        self.assertEqual(out.stdout.split()[0], "9.9.9")
