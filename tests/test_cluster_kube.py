import subprocess
import unittest
from unittest import mock

from gpu_sched_bench.cluster.kube import FakeKubectl, KubeError, Kubectl


class KubectlTests(unittest.TestCase):
    def test_context_and_server_side_apply(self):
        done = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
        with mock.patch("subprocess.run", return_value=done) as run:
            Kubectl(context="kind-gsb").apply("kind: Namespace\n", server_side=True)
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["kubectl", "--context", "kind-gsb", "apply", "-f", "-", "--server-side", "--force-conflicts"])
        self.assertEqual(kwargs["input"], "kind: Namespace\n")

    def test_errors_are_clear(self):
        failed = subprocess.CompletedProcess([], 1, stdout="", stderr="error: no matching resources")
        with mock.patch("subprocess.run", return_value=failed), self.assertRaisesRegex(KubeError, "no matching resources"):
            Kubectl().get_json("pods", "-A")
        with mock.patch("subprocess.run", side_effect=FileNotFoundError), self.assertRaisesRegex(KubeError, "not found"):
            Kubectl().run("version")
        bad_json = subprocess.CompletedProcess([], 0, stdout="not json", stderr="")
        with mock.patch("subprocess.run", return_value=bad_json), self.assertRaisesRegex(KubeError, "invalid JSON"):
            Kubectl().get_json("pods")

    def test_fake_records_and_answers(self):
        fake = FakeKubectl({"pods": {"items": [{"metadata": {"name": "p"}}]}})
        fake.apply("a")
        self.assertEqual(fake.applied, ["a"])
        self.assertEqual(fake.get_json("pods", "-A")["items"][0]["metadata"]["name"], "p")
        self.assertEqual(fake.get_json("nodes"), {"items": []})
