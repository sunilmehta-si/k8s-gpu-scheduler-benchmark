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


class KueueManifestTests(unittest.TestCase):
    def test_team_queues_in_a_cohort_with_reclaim(self):
        docs = manifests.render("kueue", FLEET, JOBS, {"research": 0.5, "product": 0.5}, part="setup")
        cqs = [d for d in docs if d["kind"] == "ClusterQueue"]
        self.assertEqual([d["metadata"]["name"] for d in cqs], ["gsb-product", "gsb-research"])
        spec = cqs[1]["spec"]
        self.assertEqual(cqs[1]["apiVersion"], "kueue.x-k8s.io/v1beta2")
        self.assertEqual((spec["cohortName"], spec["queueingStrategy"]), ("gsb", "BestEffortFIFO"))
        self.assertEqual(spec["resourceGroups"][0]["flavors"][0]["resources"], [{"name": "nvidia.com/gpu", "nominalQuota": 16}])
        self.assertEqual(spec["preemption"]["reclaimWithinCohort"], "Any")
        self.assertEqual(spec["namespaceSelector"]["matchExpressions"][0]["values"], ["research"])
        lqs = [d for d in docs if d["kind"] == "LocalQueue"]
        self.assertEqual({(d["metadata"]["namespace"], d["spec"]["clusterQueue"]) for d in lqs},
                         {("gsb-product", "gsb-product"), ("gsb-research", "gsb-research")})

    def test_without_quotas_one_shared_queue(self):
        docs = manifests.render("kueue", FLEET, JOBS, {}, part="setup")
        cqs = [d for d in docs if d["kind"] == "ClusterQueue"]
        self.assertEqual(len(cqs), 1)
        self.assertEqual(cqs[0]["spec"]["resourceGroups"][0]["flavors"][0]["resources"][0]["nominalQuota"], 32)

    def test_jobs_are_labelled_for_their_local_queue(self):
        job = manifests.render("kueue", FLEET, JOBS, {}, part="jobs")[0]
        self.assertEqual(job["metadata"]["labels"]["kueue.x-k8s.io/queue-name"], "gsb-queue")


class VolcanoManifestTests(unittest.TestCase):
    Q = {"research": 0.5, "product": 0.5}

    def test_weighted_team_queues(self):
        docs = [d for d in manifests.render("volcano", FLEET, JOBS, self.Q, part="setup") if d["kind"] == "Queue"]
        self.assertEqual([(d["metadata"]["name"], d["spec"]["weight"]) for d in docs],
                         [("gsb-product", 50), ("gsb-research", 50)])
        shared = [d for d in manifests.render("volcano", FLEET, JOBS, {}, part="setup") if d["kind"] == "Queue"]
        self.assertEqual([d["metadata"]["name"] for d in shared], ["gsb-shared"])

    def test_gangs_need_every_replica(self):
        train, nb = manifests.render("volcano", FLEET, JOBS, self.Q, speedup=60, part="jobs")
        self.assertEqual((train["apiVersion"], train["kind"]), ("batch.volcano.sh/v1alpha1", "Job"))
        self.assertEqual((train["spec"]["minAvailable"], train["spec"]["queue"]), (2, "gsb-research"))
        self.assertEqual(train["spec"]["tasks"][0]["replicas"], 2)
        self.assertEqual(train["spec"]["tasks"][0]["template"]["spec"]["schedulerName"], "volcano")
        self.assertEqual(nb["spec"]["minAvailable"], 1)                   # notebooks are not gangs


class KaiManifestTests(unittest.TestCase):
    Q = {"research": 0.5, "product": 0.5}

    def test_hierarchical_queues_with_gpu_quota(self):
        docs = manifests.render("kai", FLEET, JOBS, self.Q, part="setup")
        queues = [d for d in docs if d["kind"] == "Queue"]
        self.assertEqual([q["metadata"]["name"] for q in queues], ["gsb-parent", "gsb-product", "gsb-research"])
        self.assertTrue(all(q["apiVersion"] == "scheduling.run.ai/v2" for q in queues))
        leaf = queues[2]["spec"]
        self.assertEqual(leaf["parentQueue"], "gsb-parent")
        self.assertEqual(leaf["resources"]["gpu"], {"quota": 16, "limit": -1, "overQuotaWeight": 1})

    def test_jobs_use_kai_with_gang_annotation(self):
        train, nb = manifests.render("kai", FLEET, JOBS, self.Q, part="jobs")
        self.assertEqual(train["metadata"]["annotations"]["kai.scheduler/batch-min-member"], "2")
        self.assertNotIn("kai.scheduler/batch-min-member", nb["metadata"]["annotations"])
        pod = train["spec"]["template"]
        self.assertEqual(pod["spec"]["schedulerName"], "kai-scheduler")
        self.assertEqual(pod["metadata"]["labels"]["kai.scheduler/queue"], "gsb-research")

    def test_every_stack_renders_the_sample_trace(self):
        from gpu_sched_bench.fleet import load as load_fleet
        from gpu_sched_bench.presets import STACKS, equal_quotas
        from gpu_sched_bench.trace import load as load_trace
        fleet, jobs = load_fleet(ROOT / "fleets/mixed-256.yaml"), load_trace(ROOT / "traces/mixed-256-8h.jsonl")
        for stack in STACKS:
            docs = manifests.render(stack, fleet, jobs, equal_quotas([j.team for j in jobs]), speedup=60)
            names = [(d["kind"], d["metadata"].get("namespace"), d["metadata"]["name"]) for d in docs]
            self.assertEqual(len(names), len(set(names)), stack)                       # no duplicate objects
            self.assertEqual(sum(1 for d in docs if d["kind"] == "Job"), len(jobs), stack)
