"""What the README and docs say about the real schedulers must hold over every committed CI run, not one."""
import json
import statistics
import unittest
from pathlib import Path

from gpu_sched_bench import repeats

ROOT = Path(__file__).resolve().parents[1]
DOC = json.loads((ROOT / "results/cluster/repeats.json").read_text())
SUMMARY = DOC["summary"]
README = (ROOT / "README.md").read_text()
GPU_AWARE = ["kai", "default-binpack", "kueue-binpack", "volcano-binpack"]
AS_INSTALLED = ["default", "kueue", "volcano"]


def runs(stack):
    return [r for r in DOC["rows"] if r["stack"] == stack]


def outcome_rows(stack):
    """A stack's runs grouped by outcome, most frequent first, as the committed summary groups them."""
    by_id = {r["run"]: r for r in runs(stack)}
    return [[by_id[i] for i in o["run_ids"]] for o in SUMMARY["stacks"][stack]["outcomes"]]


def small_pods_on(row, pool):
    return {n for kind in ("notebook", "inference") for n in row["nodes"].get(kind, []) if repeats.pool(n) == pool}


def inference_on_h100(row):
    return any(repeats.pool(n) == "h100" for n in row["nodes"].get("inference", []))


def median(values):
    return statistics.median(values)


def cut(a, b):
    """How much cheaper (or faster) a is than b, in whole percent."""
    return round(100 * (1 - a / b))


class CommittedRepeatsTests(unittest.TestCase):
    def test_the_summary_and_report_regenerate_from_the_rows(self):
        self.assertEqual(repeats.summarise(DOC["rows"]), SUMMARY, "rerun gsb repeats")
        self.assertEqual((ROOT / "results/cluster/repeats.md").read_text(), repeats.to_markdown(DOC))

    def test_every_stack_ran_in_every_run(self):
        self.assertGreaterEqual(len(SUMMARY["runs"]), 30)
        for stack in GPU_AWARE + AS_INSTALLED:
            self.assertEqual(sorted(r["run"] for r in runs(stack)), sorted(SUMMARY["runs"]), stack)

    def test_the_readme_table_is_the_committed_summary(self):
        self.assertIn(repeats.readme_table(SUMMARY), README)
        self.assertIn(f"Medians of {len(SUMMARY['runs'])} runs", README)

    def test_the_run_in_detail_is_a_committed_run_and_shows_each_stacks_usual_outcome(self):
        detail = (ROOT / "results/cluster/README.md").read_text()
        run = detail.split("actions/runs/", 1)[1].split(")", 1)[0]
        self.assertIn(run, SUMMARY["runs"])
        for stack in GPU_AWARE + AS_INSTALLED:
            with self.subTest(stack=stack):
                cost = json.loads((ROOT / f"results/cluster/cluster-{stack}.json").read_text())["stacks"][stack]["cost"]
                self.assertIn(run, SUMMARY["stacks"][stack]["outcomes"][0]["run_ids"])
                row = next(r for r in runs(stack) if r["run"] == run)
                self.assertEqual(row["cost_per_useful_gpu_h"], cost["per_useful_gpu_h"])


class ScoringGpusTests(unittest.TestCase):
    def test_gpu_aware_stacks_give_one_outcome_within_4_percent_and_keep_small_pods_off_the_h100_nodes(self):
        for stack in GPU_AWARE:
            with self.subTest(stack=stack):
                st = SUMMARY["stacks"][stack]
                self.assertEqual(len(st["outcomes"]), 1)
                c = st["cost_per_useful_gpu_h"]
                self.assertLessEqual((c["max"] - c["min"]) / c["median"], 0.04)
                self.assertTrue(all(not small_pods_on(r, "h100") for r in runs(stack)))

    def test_each_stack_as_installed_splits_into_two_outcomes(self):
        for stack in AS_INSTALLED:
            self.assertEqual(len(SUMMARY["stacks"][stack]["outcomes"]), 2, stack)

    def test_a_gpu_aware_stack_beats_every_stack_as_installed_in_its_usual_outcome(self):
        worst_aware = max(SUMMARY["stacks"][s]["cost_per_useful_gpu_h"]["max"] for s in GPU_AWARE)
        for stack in AS_INSTALLED:
            usual = SUMMARY["stacks"][stack]["outcomes"][0]["cost_per_useful_gpu_h"]["min"]
            self.assertLess(worst_aware, usual, stack)


class AsInstalledTests(unittest.TestCase):
    def test_an_inference_pod_on_an_h100_node_decides_every_default_and_kueue_run(self):
        for stack in ("default", "kueue"):
            usual, other = outcome_rows(stack)
            with self.subTest(stack=stack):
                self.assertTrue(all(inference_on_h100(r) for r in usual))
                self.assertFalse(any(inference_on_h100(r) for r in other))
                self.assertGreater(usual[0]["cost_per_useful_gpu_h"], other[0]["cost_per_useful_gpu_h"])

    def test_kueue_numbers_in_the_readme(self):
        usual, other = outcome_rows("kueue")
        train = lambda rows: [r["starts_h"]["training-00007"] for r in rows]   # noqa: E731
        self.assertEqual(round(median(train(usual)), 1), 5.1)
        self.assertEqual((round(min(train(other)), 1), round(max(train(other)), 1)), (2.3, 2.9))
        self.assertGreaterEqual(min(r["stranded_gpu_h"] for r in usual), 20.0)        # one 8-GPU pod for 2.5 hours
        self.assertIn("held a whole H100 node for 2.5 hours; the gang started at 5.1 h instead of 2.3 to 2.9 h", README)
        aware = SUMMARY["stacks"]["kueue-binpack"]["cost_per_useful_gpu_h"]
        self.assertEqual((f"{aware['median']:.2f}", f"{aware['max']:.2f}"), ("3.98", "4.11"))
        self.assertEqual(cut(aware["median"], SUMMARY["stacks"]["kueue"]["cost_per_useful_gpu_h"]["median"]), 23)
        self.assertIn("a median $3.98 per useful GPU-hour and never more than $4.11, 23% less", README)

    def test_default_scheduler_numbers_in_the_readme(self):
        usual, _ = outcome_rows("default")
        later = median(r["starts_h"]["training-00007"] for r in usual) - median(
            r["starts_h"]["training-00007"] for r in runs("default-binpack"))
        self.assertEqual(round(later, 1), 2.5)
        costs = {s: SUMMARY["stacks"][s]["cost_per_useful_gpu_h"]["median"] for s in ("default", "default-binpack")}
        self.assertEqual(cut(costs["default-binpack"], costs["default"]), 20)
        self.assertIn("started 2.5 hours later than with GPU-aware placement", README)
        self.assertIn("cut its median cost\n  per useful GPU-hour by 20%", README)

    def test_volcano_numbers_in_the_readme(self):
        usual, other = outcome_rows("volcano")
        self.assertTrue(all(small_pods_on(r, "h100") for r in runs("volcano")))       # an H100 node in every run
        self.assertEqual(round(median(r["starts_h"]["training-00007"] for r in usual), 1), 7.1)
        self.assertTrue(all(len(small_pods_on(r, "h100")) == 2 for r in other))       # both H100 nodes
        fine_tunes = [r["starts_h"][j] for r in other for j in ("finetune-00002", "finetune-00008")]
        self.assertEqual(round(min(fine_tunes), 1), 6.7)
        self.assertEqual(round(median(r["makespan_h"] for r in other), 1), 11.1)
        self.assertIn("until 6.7 h or later: 11.1 h to\n  finish", README)
        v, b = SUMMARY["stacks"]["volcano"], SUMMARY["stacks"]["volcano-binpack"]
        self.assertEqual(cut(b["makespan_h"]["median"], v["makespan_h"]["median"]), 26)
        self.assertEqual(cut(b["cost_per_useful_gpu_h"]["median"], v["cost_per_useful_gpu_h"]["median"]), 26)

    def test_volcanos_slower_outcome_is_slower_than_any_model_seed(self):
        from dataclasses import replace

        from gpu_sched_bench import metrics
        from gpu_sched_bench.fleet import load as load_fleet
        from gpu_sched_bench.presets import equal_quotas, preset
        from gpu_sched_bench.sim import simulate
        from gpu_sched_bench.trace import load as load_trace
        fleet, jobs = load_fleet(ROOT / "fleets/lab-32.yaml"), load_trace(ROOT / "traces/lab-32-smoke.jsonl")
        shares = equal_quotas([j.team for j in jobs])
        model = max(metrics.core(simulate(fleet, jobs, replace(preset("volcano", shares), seed=s)))["makespan_h"]
                    for s in range(100))
        self.assertEqual(round(model, 1), 9.5)
        _, slower = outcome_rows("volcano")
        self.assertGreater(min(r["makespan_h"] for r in slower), model)
        self.assertIn("is slower than any of the model's seeds (9.5 h at most)", README)


class DocsTests(unittest.TestCase):
    def test_the_outcome_counts_in_the_docs(self):
        n = len(SUMMARY["runs"])
        usual = {s: SUMMARY["stacks"][s]["outcomes"][0] for s in AS_INSTALLED}
        other = {s: SUMMARY["stacks"][s]["outcomes"][1] for s in AS_INSTALLED}
        scoring = (ROOT / "docs/gpu-scoring.md").read_text()
        self.assertIn(f"it did in {usual['default']['runs']} of {n} default-scheduler runs and {usual['kueue']['runs']} of {n} "
                      "Kueue", scoring)
        for s in ("default", "kueue"):
            self.assertEqual(f"{usual[s]['cost_per_useful_gpu_h']['median']:.1f}", "5.2", s)  # "about $5.2"
        cheap = [f"${other[s]['cost_per_useful_gpu_h']['median']:.1f}" for s in ("default", "kueue")]
        self.assertIn(f"the others cost {cheap[0]} and {cheap[1]}", scoring)
        self.assertIn(f"In {other['volcano']['runs']} of the {n} runs small pods held GPUs on both H100 nodes", scoring)
        runs_doc = (ROOT / "docs/cluster-runs.md").read_text()
        for s in ("default", "kueue"):
            self.assertEqual(round(10 * usual[s]["runs"] / n), 7, s)                    # "about seven runs of ten"
        self.assertEqual(round(10 * other["volcano"]["runs"] / n), 3)                   # "on its slower one in three"
        self.assertIn("in about seven runs of ten, Volcano on its slower one in three", runs_doc)


if __name__ == "__main__":
    unittest.main()
