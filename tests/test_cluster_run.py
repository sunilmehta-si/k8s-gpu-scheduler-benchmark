import unittest

import yaml

from gpu_sched_bench.cluster.kube import FakeKubectl
from gpu_sched_bench.cluster.run import run_cluster
from gpu_sched_bench.fleet import parse
from gpu_sched_bench.trace import Job

FLEET = parse({"name": "t", "pools": [{"name": "n", "count": 2, "gpus_per_node": 8}]})
JOBS = [Job("a", 0, "red", "notebook", 1, 1, 600), Job("b", 60, "blue", "notebook", 1, 1, 600)]


def finished_pod(job, node, start, end):
    iso = lambda t: f"2026-10-15T00:{int(t) // 60:02d}:{int(t) % 60:02d}Z"   # noqa: E731
    return {"metadata": {"name": f"{job}-0", "labels": {"gsb.io/job": job}}, "spec": {"nodeName": node},
            "status": {"phase": "Succeeded", "startTime": iso(start),
                       "conditions": [{"type": "PodScheduled", "status": "True", "lastTransitionTime": iso(start)}],
                       "containerStatuses": [{"state": {"terminated": {"finishedAt": iso(end)}}}]}}


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


class ClusterRunTests(unittest.TestCase):
    def test_applies_nodes_setup_and_jobs_then_reports_cluster_mode(self):
        from gpu_sched_bench.cluster.collect import ts
        t0 = ts("2026-10-15T00:00:00Z")
        kube = FakeKubectl({"pods": {"items": [finished_pod("a", "n-000", 0, 10), finished_pod("b", "n-001", 1, 11)]}})
        doc = run_cluster(kube, FLEET, JOBS, "kueue", {"red": 0.5, "blue": 0.5}, speedup=60, clock=Clock(t0),
                          sleep=lambda s: None)
        kinds = [d["kind"] for chunk in kube.applied for d in yaml.safe_load_all(chunk)]
        self.assertEqual(kinds[:2], ["Node", "Node"])
        self.assertIn("ClusterQueue", kinds)
        self.assertEqual(kinds.count("Job"), 2)
        self.assertEqual(doc["mode"], "cluster")
        stack = doc["stacks"]["kueue"]
        self.assertEqual(stack["jobs_finished"], 2)
        self.assertEqual(stack["queue_wait"]["max_min"], 0.0)       # b was scheduled at its (compressed) arrival

    def test_timeout_reports_what_finished(self):
        clock = Clock(0.0)
        doc = run_cluster(FakeKubectl(), FLEET, JOBS, "default", {}, speedup=60, timeout_s=30, poll_s=10,
                          clock=clock, sleep=clock.sleep)
        self.assertEqual(doc["stacks"]["default"]["jobs_finished"], 0)
        self.assertGreaterEqual(clock.t, 30)


class SetupRetryTests(unittest.TestCase):
    def test_retries_until_the_webhook_is_ready(self):
        from gpu_sched_bench.cluster.kube import KubeError
        from gpu_sched_bench.cluster.run import _apply_with_retry

        class Flaky:
            calls = 0

            def apply(self, text, server_side=False):
                Flaky.calls += 1
                if Flaky.calls < 3:
                    raise KubeError("failed calling webhook: connection refused")
        waits = []
        _apply_with_retry(Flaky(), "x", waits.append, lambda m: None)
        self.assertEqual((Flaky.calls, waits), (3, [10.0, 10.0]))

    def test_gives_up_after_the_last_attempt(self):
        from gpu_sched_bench.cluster.kube import KubeError
        from gpu_sched_bench.cluster.run import _apply_with_retry

        class Broken:
            def apply(self, text, server_side=False):
                raise KubeError("no matches for kind ClusterQueue")
        with self.assertRaisesRegex(KubeError, "ClusterQueue"):
            _apply_with_retry(Broken(), "x", lambda s: None, lambda m: None, attempts=2)
