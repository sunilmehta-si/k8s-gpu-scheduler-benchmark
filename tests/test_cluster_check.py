import unittest

from gpu_sched_bench.cluster.check import runtime_check
from gpu_sched_bench.cluster.collect import PodRun
from gpu_sched_bench.trace import Job

JOBS = [Job("a", 0, "t", "notebook", 1, 1, 600), Job("b", 0, "t", "training", 1, 8, 3000)]


def run(job, start, end):
    return PodRun(job, f"{job}-0", "n", start, start, end, "Succeeded")


class RuntimeCheckTests(unittest.TestCase):
    def test_pods_that_ran_their_time_pass(self):
        c = runtime_check(JOBS, [run("a", 0, 10.5), run("b", 0, 49)], speedup=60)   # expected 10 s and 50 s
        self.assertTrue(c["ok"])
        self.assertEqual(c["pods_checked"], 2)

    def test_pods_that_finished_immediately_fail_loudly(self):
        c = runtime_check(JOBS, [run("a", 0, 1), run("b", 0, 2)], speedup=60)
        self.assertFalse(c["ok"])
        self.assertIn("pod/general", c["reason"])

    def test_nothing_finished(self):
        self.assertFalse(runtime_check(JOBS, [PodRun("a", "a-0", None, None, None, None, "Pending")], 60)["ok"])
