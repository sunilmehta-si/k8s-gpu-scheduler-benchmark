import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def test_the_cluster_runs_the_pinned_kind_and_kubernetes(self):
        steps = yaml.safe_load((ROOT / ".github/workflows/cluster.yml").read_text())["jobs"]["run"]["steps"]
        load = next(i for i, s in enumerate(steps) if "cluster/versions.env" in s.get("run", ""))
        self.assertIn("$GITHUB_ENV", steps[load]["run"])
        kind = next(i for i, s in enumerate(steps) if s.get("uses", "").startswith("helm/kind-action@"))
        self.assertLess(load, kind)                                   # the pins are in env before kind starts
        self.assertEqual(steps[kind]["with"]["version"], "${{ env.KIND_VERSION }}")
        self.assertEqual(steps[kind]["with"]["node_image"], "${{ env.KIND_NODE_IMAGE }}")

    def test_every_action_is_pinned_to_a_commit(self):
        for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
            for job in yaml.safe_load(path.read_text())["jobs"].values():
                for step in job.get("steps", []):
                    if "uses" in step:
                        with self.subTest(workflow=path.name, uses=step["uses"]):
                            self.assertRegex(step["uses"], r"@[0-9a-f]{40}$")
