import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from gpu_sched_bench import repeats
from gpu_sched_bench.cli import main


def stack_result(cost, makespan=7.3, wait=80.0, stranded=0.0, placements=None):
    return {"makespan_h": makespan, "queue_wait": {"p95_min": wait}, "stranded_gpu_h": stranded,
            "cost": {"per_useful_gpu_h": cost},
            "placements": placements if placements is not None else [
                {"job": "notebook-00001", "replica": 0, "node": "l40s-000", "start_s": 3600.0},
                {"job": "training-00007", "replica": 0, "node": "h100-000", "start_s": 7200.0},
                {"job": "training-00007", "replica": 1, "node": "h100-001", "start_s": 9000.0}]}


def cluster_file(stacks: dict, ok=True):
    return {"mode": "cluster", "tool_version": "0.5.0", "runtime_check": {"ok": ok}, "stacks": stacks}


def row(run, stack, cost):
    return {"run": run, "stack": stack, "makespan_h": 7.3, "queue_wait_p95_min": 80.0, "stranded_gpu_h": 0.0,
            "cost_per_useful_gpu_h": cost, "nodes": {}, "starts_h": {}}


class RecordTests(unittest.TestCase):
    def test_keeps_the_metrics_the_nodes_per_job_kind_and_when_each_job_started(self):
        (r,) = repeats.record("42", cluster_file({"kueue": stack_result(5.2, 7.7, 270.0, 20.0)}))
        self.assertEqual((r["run"], r["stack"], r["makespan_h"], r["queue_wait_p95_min"], r["stranded_gpu_h"],
                          r["cost_per_useful_gpu_h"]), ("42", "kueue", 7.7, 270.0, 20.0, 5.2))
        self.assertEqual(r["nodes"], {"notebook": ["l40s-000"], "training": ["h100-000", "h100-001"]})
        self.assertEqual(r["starts_h"], {"notebook-00001": 1.0, "training-00007": 2.5})   # a gang starts with its last pod

    def test_a_job_with_a_replica_that_never_started_has_no_start(self):
        placements = [{"job": "training-00007", "replica": 0, "node": "h100-000", "start_s": 7200.0},
                      {"job": "training-00007", "replica": 1, "node": "", "start_s": None}]
        (r,) = repeats.record("1", cluster_file({"kai": stack_result(4.0, placements=placements)}))
        self.assertIsNone(r["starts_h"]["training-00007"])
        self.assertEqual(r["nodes"], {"training": ["h100-000"]})

    def test_rejects_a_simulation_file(self):
        with self.assertRaises(ValueError):
            repeats.record("1", {"mode": "simulation", "stacks": {}})

    def test_pool_is_the_node_name_without_its_index(self):
        self.assertEqual(repeats.pool("h100-001"), "h100")
        self.assertEqual(repeats.pool("big-gpu-pool-12"), "big-gpu-pool")


class CollectTests(unittest.TestCase):
    def write(self, root: Path, run: str, stack: str, cost: float, ok=True):
        path = root / run / f"cluster-{stack}" / f"cluster-{stack}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cluster_file({stack: stack_result(cost)}, ok)))

    def test_reads_every_run_in_run_order_and_skips_failed_runtime_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, "100", "kai", 4.0)
            self.write(root, "99", "kai", 3.9)
            self.write(root, "99", "volcano", 5.3)
            self.write(root, "101", "kai", 9.9, ok=False)
            (root / "99" / "cluster-kai" / "model-kai.json").write_text("{}")     # model files are not cluster runs
            rows, skipped = repeats.collect(root)
        self.assertEqual([(r["run"], r["stack"]) for r in rows], [("99", "kai"), ("99", "volcano"), ("100", "kai")])
        self.assertEqual(len(skipped), 1)
        self.assertIn("101", skipped[0])

    def test_an_empty_directory_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            repeats.collect(Path(tmp))


class OutcomeTests(unittest.TestCase):
    def test_run_to_run_noise_is_one_outcome(self):
        rows = [row(str(i), "kai", c) for i, c in enumerate([3.92, 3.96, 3.97, 3.98, 4.05])]
        self.assertEqual(len(repeats.outcomes(rows)), 1)

    def test_a_gap_wider_than_a_tenth_of_the_median_splits_the_runs_most_frequent_first(self):
        costs = [3.96, 3.98, 5.18, 5.2, 5.21, 5.25]
        groups = repeats.outcomes([row(str(i), "kueue", c) for i, c in enumerate(costs)])
        self.assertEqual([[r["cost_per_useful_gpu_h"] for r in g] for g in groups], [[5.18, 5.2, 5.21, 5.25], [3.96, 3.98]])

    def test_equal_sized_outcomes_put_the_cheaper_first(self):
        groups = repeats.outcomes([row("1", "x", 6.0), row("2", "x", 4.0)])
        self.assertEqual([g[0]["cost_per_useful_gpu_h"] for g in groups], [4.0, 6.0])


class SummaryTests(unittest.TestCase):
    rows = [row("1", "kueue", 5.2), row("2", "kueue", 3.98), row("3", "kueue", 5.22), row("1", "kai", 3.97),
            row("2", "kai", 3.96), row("3", "kai", 3.98)]

    def test_median_range_and_outcomes(self):
        s = repeats.summarise(self.rows)
        self.assertEqual(s["runs"], ["1", "2", "3"])
        self.assertEqual(s["stacks"]["kueue"]["cost_per_useful_gpu_h"], {"median": 5.2, "min": 3.98, "max": 5.22})
        self.assertEqual([(o["runs"], o["run_ids"]) for o in s["stacks"]["kueue"]["outcomes"]], [(2, ["1", "3"]), (1, ["2"])])
        self.assertEqual(len(s["stacks"]["kai"]["outcomes"]), 1)

    def test_cost_cell_names_each_outcome_only_when_runs_split(self):
        s = repeats.summarise(self.rows)
        self.assertEqual(repeats.cost_cell(s["stacks"]["kai"]), "$3.97")
        self.assertEqual(repeats.cost_cell(s["stacks"]["kueue"]), "$5.21 in 2 runs, $3.98 in 1")

    def test_readme_table_lists_known_stacks_in_a_fixed_order(self):
        table = repeats.readme_table(repeats.summarise(self.rows))
        lines = table.splitlines()
        self.assertEqual(lines[0], "| Real scheduler | Time to finish | Queue wait p95 | Cost per useful GPU-hour |")
        self.assertEqual(lines[2], "| Kueue | 7.3 h | 80 min | $5.21 in 2 runs, $3.98 in 1 |")
        self.assertEqual(lines[3], "| KAI Scheduler | 7.3 h | 80 min | $3.97 |")

    def test_markdown_shows_the_split_section_only_when_a_stack_splits(self):
        doc = repeats.build(self.rows, "From three runs.")
        md = repeats.to_markdown(doc)
        self.assertIn("## Repeated cluster runs: 3 runs", md)
        self.assertIn("From three runs.", md)
        self.assertIn("### Stacks whose runs split into outcomes", md)
        self.assertIn("| 2 | $3.98 | $3.96 |", md)                  # run 2: each stack's cost, stacks in label order
        steady = repeats.to_markdown(repeats.build([r for r in self.rows if r["stack"] == "kai"]))
        self.assertNotIn("split into outcomes", steady)


class CliTests(unittest.TestCase):
    def test_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for run, cost in (("7", 3.97), ("8", 3.96)):
                path = root / "runs" / run / "cluster-kai" / "cluster-kai.json"
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(cluster_file({"kai": stack_result(cost)})))
            with redirect_stderr(io.StringIO()) as err:
                code = main(["repeats", str(root / "runs"), "-o", str(root / "r.json"), "--markdown", str(root / "r.md"),
                             "--source", "Two runs."])
            self.assertEqual(code, 0)
            self.assertIn("2 runs, 2 stack results", err.getvalue())
            doc = json.loads((root / "r.json").read_text())
            self.assertEqual((doc["source"], doc["summary"]["runs"]), ("Two runs.", ["7", "8"]))
            self.assertEqual((root / "r.md").read_text(), repeats.to_markdown(doc))

    def test_an_empty_directory_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            self.assertEqual(main(["repeats", tmp]), 2)


if __name__ == "__main__":
    unittest.main()
