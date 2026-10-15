import unittest

from gpu_sched_bench.cluster.collect import collect, pod_runs, ts
from gpu_sched_bench.cluster.kube import FakeKubectl


def pod(name, job, node=None, scheduled=None, start=None, finished=None, phase="Pending"):
    status = {"phase": phase, "conditions": []}
    if scheduled:
        status["conditions"].append({"type": "PodScheduled", "status": "True", "lastTransitionTime": scheduled})
    if start:
        status["startTime"] = start
    if finished:
        status["containerStatuses"] = [{"name": "main", "state": {"terminated": {"finishedAt": finished, "exitCode": 0}}}]
    return {"metadata": {"name": name, "labels": {"gsb.io/job": job}}, "spec": {"nodeName": node} if node else {},
            "status": status}


PODS = {"items": [
    pod("train-1-b", "train-1", "h100-001", "2026-10-15T10:00:05Z", "2026-10-15T10:00:06Z", "2026-10-15T10:01:06Z", "Succeeded"),
    pod("train-1-a", "train-1", "h100-000", "2026-10-15T10:00:01Z", "2026-10-15T10:00:02Z", None, "Running"),
    pod("nb-2-x", "nb-2"),
    {"metadata": {"name": "unrelated", "labels": {}}, "spec": {}, "status": {}},
]}


class CollectTests(unittest.TestCase):
    def test_timestamps(self):
        self.assertEqual(ts("2026-10-15T10:00:01Z") - ts("2026-10-15T10:00:00Z"), 1.0)
        self.assertIsNone(ts(None))

    def test_pod_runs(self):
        runs = pod_runs(PODS)
        self.assertEqual([r.name for r in runs], ["nb-2-x", "train-1-a", "train-1-b"])   # unrelated pods are ignored
        pending, running, done = runs
        self.assertEqual((pending.node, pending.scheduled_at, pending.phase), (None, None, "Pending"))
        self.assertEqual(running.node, "h100-000")
        self.assertIsNone(running.finished_at)                                         # still running
        self.assertEqual(done.finished_at - done.started_at, 60.0)
        self.assertEqual(done.started_at - done.scheduled_at, 1.0)

    def test_collect_uses_the_job_label_selector(self):
        self.assertEqual(len(collect(FakeKubectl({"pods": PODS}))), 3)
