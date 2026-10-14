import json
import unittest

from gpu_sched_bench.trace import Job, TraceError, check_fits, dump, parse


def line(**over):
    base = {"id": "j1", "arrival_s": 0, "team": "a", "kind": "training", "replicas": 2, "gpus_per_replica": 8,
            "duration_s": 60}
    return json.dumps({**base, **over})


class TraceTests(unittest.TestCase):
    def test_round_trip_sorted_by_arrival(self):
        jobs = parse([line(id="late", arrival_s=10), "# comment", "", line(id="early", arrival_s=1, gang=True)])
        self.assertEqual([j.id for j in jobs], ["early", "late"])
        self.assertEqual(jobs[0].gpus, 16)
        self.assertEqual(jobs[0].gpu_seconds, 960)
        self.assertEqual(parse(dump(jobs).splitlines()), jobs)

    def test_mistakes_are_explained(self):
        cases = {
            "not valid JSON": "{oops",
            "missing team": json.dumps({k: v for k, v in json.loads(line()).items() if k != "team"}),
            "kind must be one of": line(kind="batch"),
            "replicas must be a positive integer": line(replicas=0),
            "duration_s must be a number > 0": line(duration_s=0),
            "unknown field": line(gpu=1),
        }
        for message, text in cases.items():
            with self.subTest(message=message), self.assertRaisesRegex(TraceError, message):
                parse([text])
        with self.assertRaisesRegex(TraceError, "Duplicate job id"):
            parse([line(), line()])

    def test_replicas_must_fit_a_node(self):
        jobs = [Job("big", 0, "a", "training", 1, 16, 60)]
        with self.assertRaisesRegex(TraceError, "more GPUs per replica than any node has"):
            check_fits(jobs, 8)
