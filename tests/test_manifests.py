import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import yaml

from gpu_sched_bench import manifests
from gpu_sched_bench.cli import main
from gpu_sched_bench.fleet import parse
from gpu_sched_bench.trace import Job

ROOT = Path(__file__).resolve().parents[1]
FLEET = parse({"name": "t", "pools": [{"name": "n", "count": 4, "gpus_per_node": 8}]})
JOBS = [Job("train-1", 30.0, "research", "training", 2, 8, 3600, 0, True, "llama"),
        Job("nb-2", 60.0, "product", "notebook", 1, 1, 600, 5, False, "notebook")]


def kinds(docs):
    return [d["kind"] for d in docs]


class CommonManifestTests(unittest.TestCase):
    def test_setup_has_team_namespaces_and_priority_classes(self):
        docs = manifests.render("default", FLEET, JOBS, {}, part="setup")
        self.assertEqual(kinds(docs), ["Namespace", "Namespace", "PriorityClass", "PriorityClass"])
        self.assertEqual([d["metadata"]["name"] for d in docs[:2]], ["gsb-product", "gsb-research"])
        self.assertEqual([d["value"] for d in docs[2:]], [0, 5])

    def test_default_job_targets_kwok_and_finishes_after_its_duration(self):
        job = manifests.render("default", FLEET, JOBS, {}, speedup=60, part="jobs")[0]
        self.assertEqual((job["kind"], job["metadata"]["namespace"]), ("Job", "gsb-research"))
        self.assertEqual((job["spec"]["parallelism"], job["spec"]["completions"]), (2, 2))
        pod = job["spec"]["template"]
        self.assertEqual(pod["metadata"]["annotations"]["pod-complete.stage.kwok.x-k8s.io/delay"], "60s")  # 3600 s / 60
        self.assertEqual(pod["spec"]["containers"][0]["resources"]["limits"], {"nvidia.com/gpu": "8"})
        self.assertEqual(pod["spec"]["nodeSelector"], {"type": "kwok"})
        self.assertNotIn("schedulerName", pod["spec"])                      # the default scheduler
        self.assertEqual(job["metadata"]["annotations"]["gsb.io/arrival-s"], "30.0")

    def test_cli_and_errors(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["manifests", "--stack", "default", "--fleet", str(ROOT / "fleets/lab-32.yaml"),
                         "--trace", str(ROOT / "traces/lab-32-8h.jsonl"), "--speedup", "60"])
        self.assertEqual(code, 0)
        docs = list(yaml.safe_load_all(buf.getvalue()))
        self.assertEqual(kinds(docs).count("Job"), 26)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["manifests", "--stack", "slurm", "--fleet", str(ROOT / "fleets/lab-32.yaml"),
                                   "--trace", str(ROOT / "traces/lab-32-8h.jsonl")]), 2)
