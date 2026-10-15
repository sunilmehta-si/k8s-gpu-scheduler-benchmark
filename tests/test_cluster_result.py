import unittest

from gpu_sched_bench import metrics
from gpu_sched_bench.cluster.collect import PodRun
from gpu_sched_bench.cluster.result import to_result
from gpu_sched_bench.fleet import parse
from gpu_sched_bench.trace import Job

FLEET = parse({"name": "t", "pools": [{"name": "n", "count": 2, "gpus_per_node": 8, "price_per_gpu_hour": 3.6}]})
START = 1_000_000.0          # wall-clock epoch when the replay began
SPEED = 60.0                 # 1 wall second = 60 trace seconds


def run(job, name, node, sched, start, end):
    w = lambda t: None if t is None else START + t / SPEED   # trace seconds -> wall clock  # noqa: E731
    return PodRun(job, name, node, w(sched), w(start), w(end), "Succeeded" if end is not None else "Running")


class ClusterResultTests(unittest.TestCase):
    def test_times_map_back_to_trace_time_and_metrics_work(self):
        jobs = [Job("a", 0, "red", "training", 1, 8, 600, 0, False), Job("g", 60, "blue", "training", 2, 8, 600, 0, True)]
        runs = [run("a", "a-0", "n-000", 0, 0, 600),
                run("g", "g-0", "n-001", 60, 60, 1260),       # waited for its partner until 600 (stranded 540 s)
                run("g", "g-1", "n-000", 600, 660, 1260)]
        r = to_result(FLEET, jobs, runs, "default", START, SPEED)
        self.assertAlmostEqual(r.records["a"].start, 0, places=6)
        self.assertAlmostEqual(r.records["g"].start, 660, places=6)          # the last pod's start
        self.assertAlmostEqual(r.records["g"].wait, 600, places=6)
        self.assertAlmostEqual(r.makespan, 1260, places=6)
        # g-0 held 8 GPUs from 60 to 660, and g-1 from 600 (scheduled) to 660 (when the gang could start)
        self.assertAlmostEqual(r.stranded_gpu_s, 8 * 600 + 8 * 60, places=3)
        m = metrics.core(r)
        self.assertEqual(m["jobs_finished"], 2)
        self.assertGreater(metrics.cost(r)["total"], 0)

    def test_unscheduled_pods_leave_the_job_unfinished(self):
        jobs = [Job("x", 0, "red", "notebook", 1, 1, 60)]
        r = to_result(FLEET, jobs, [PodRun("x", "x-0", None, None, None, None, "Pending")], "kai", START, SPEED,
                      collected_at=START + 10)
        self.assertEqual(r.unfinished, ["x"])
        self.assertAlmostEqual(r.makespan, 600, places=6)                     # until collection, in trace time
        self.assertGreater(metrics.fragmentation(r)["idle_while_waiting_gpu_h"], 0)
