import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import yaml

from gpu_sched_bench.cli import main
from gpu_sched_bench.fleet import parse
from gpu_sched_bench.kwok import node_manifests

FLEET = {"name": "lab", "pools": [{"name": "h100", "count": 2, "gpus_per_node": 8, "taints": ["gpu=h100:NoSchedule"],
                                   "labels": {"topology.kubernetes.io/zone": "a"}}]}


class KwokTests(unittest.TestCase):
    def test_nodes_advertise_gpus_and_carry_kwok_markers(self):
        nodes = node_manifests(parse(FLEET))
        self.assertEqual(len(nodes), 2)
        n = nodes[0]
        self.assertEqual(n["metadata"]["annotations"]["kwok.x-k8s.io/node"], "fake")
        self.assertEqual(n["status"]["allocatable"]["nvidia.com/gpu"], "8")
        self.assertEqual(n["metadata"]["labels"]["gsb.io/pool"], "h100")
        self.assertEqual(n["metadata"]["labels"]["topology.kubernetes.io/zone"], "a")
        self.assertIn({"key": "gpu", "value": "h100", "effect": "NoSchedule"}, n["spec"]["taints"])
        self.assertIn({"key": "kwok.x-k8s.io/node", "value": "fake", "effect": "NoSchedule"}, n["spec"]["taints"])

    def test_cli_render_and_summary(self):
        path = Path(tempfile.mkdtemp()) / "fleet.yaml"
        path.write_text(yaml.safe_dump(FLEET))
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(main(["fleet", "render", str(path)]), 0)
        self.assertEqual([d["metadata"]["name"] for d in yaml.safe_load_all(buf.getvalue())], ["h100-000", "h100-001"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["fleet", "summary", str(path)])
        self.assertIn("lab: 2 nodes, 16 GPUs", buf.getvalue())
