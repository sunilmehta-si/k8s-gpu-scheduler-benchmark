import unittest

import yaml

from gpu_sched_bench.cluster.kube import FakeKubectl
from gpu_sched_bench.cluster.replay import plan, replay
from gpu_sched_bench.trace import Job


def job(id, arrival):
    return Job(id, arrival, "a", "notebook", 1, 1, 60)


class FakeClock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


class ReplayTests(unittest.TestCase):
    def test_plan_compresses_and_orders(self):
        p = plan([job("b", 130), job("a", 10), job("c", 610)], speedup=60)
        self.assertEqual([(round(t, 3), j.id) for t, j in p], [(0.0, "a"), (2.0, "b"), (10.0, "c")])
        with self.assertRaises(ValueError):
            plan([job("a", 0)], speedup=0)
        self.assertEqual(plan([], 60), [])

    def test_replay_submits_on_time_in_order(self):
        clock, kube = FakeClock(), FakeKubectl()
        jobs = [job("a", 0), job("b", 120), job("c", 120)]
        docs = {j.id: {"kind": "Job", "metadata": {"name": j.id}} for j in jobs}
        sent = replay(kube, docs, plan(jobs, 60), clock=clock, sleep=clock.sleep)
        self.assertEqual([(s.job_id, s.due_s, s.sent_s) for s in sent], [("a", 0, 0), ("b", 2, 2), ("c", 2, 2)])
        self.assertEqual([yaml.safe_load(a)["metadata"]["name"] for a in kube.applied], ["a", "b", "c"])
