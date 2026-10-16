import unittest

from gpu_sched_bench.fleet import parse
from gpu_sched_bench.sim import Policy, simulate
from gpu_sched_bench.trace import Job

FLEET = parse({"name": "t", "pools": [{"name": "n", "count": 2, "gpus_per_node": 8}]})


def job(id, arrival=0, replicas=1, gpus=8, duration=100, gang=False, priority=0, kind="training", team="a"):
    return Job(id, arrival, team, kind, replicas, gpus, duration, priority, gang)


class EngineTests(unittest.TestCase):
    def test_jobs_queue_when_full_and_start_when_capacity_frees(self):
        r = simulate(FLEET, [job("a"), job("b"), job("c", arrival=10)], Policy("default"))
        self.assertEqual((r.records["a"].start, r.records["b"].start), (0, 0))
        self.assertEqual(r.records["c"].start, 100)         # waited for a or b to finish
        self.assertEqual(r.records["c"].wait, 90)
        self.assertEqual(r.makespan, 200)
        self.assertEqual(r.allocated_gpu_s, 16 * 100 + 8 * 100)
        self.assertFalse(r.deadlocked)

    def test_spread_placement_uses_the_emptiest_node(self):
        r = simulate(FLEET, [job("a", gpus=2), job("b", gpus=2)], Policy("default"))
        self.assertNotEqual(r.records["a"].nodes[0], r.records["b"].nodes[0])

    def test_random_placement_is_seeded_and_uses_any_feasible_node(self):
        fleet = parse({"name": "t", "pools": [{"name": "n", "count": 8, "gpus_per_node": 8}]})
        jobs = [job(f"j{i}", gpus=1) for i in range(8)]
        def nodes(seed):
            r = simulate(fleet, jobs, Policy("r", placement="random", seed=seed))
            return [r.records[f"j{i}"].nodes[0] for i in range(8)]
        self.assertEqual(nodes(1), nodes(1))
        self.assertNotEqual(nodes(1), nodes(2))
        self.assertGreater(len(set(nodes(1))), 1)            # neither packed onto one node nor forced apart
        big = simulate(fleet, [job("a", gpus=1), job("b", gpus=8)], Policy("r", placement="random"))
        self.assertNotEqual(big.records["a"].nodes[0], big.records["b"].nodes[0])   # only feasible nodes are drawn

    def test_pod_by_pod_gangs_interleave_and_deadlock(self):
        # Submitted together, the pods interleave: g1-0 takes node A, g2-0 takes most of node B, and then
        # neither g1-1 (8 GPUs) nor g2-1 (6 GPUs) fits anywhere. Both gangs hold GPUs forever.
        r = simulate(FLEET, [job("g1", replicas=2, gang=True), job("g2", replicas=2, gpus=6, gang=True)], Policy("default"))
        self.assertTrue(r.deadlocked)
        self.assertEqual(r.unfinished, ["g1", "g2"])
        self.assertEqual((r.records["g1"].placed, r.records["g2"].placed), (1, 1))

    def test_partially_placed_gang_strands_gpus_until_complete(self):
        r = simulate(FLEET, [job("blocker", duration=50), job("g", replicas=2, gang=True, arrival=1)], Policy("default"))
        self.assertEqual(r.records["g"].start, 50)            # one replica waited 49 s for the other node
        self.assertEqual(r.stranded_gpu_s, 8 * 49)

    def test_independent_replicas_start_as_soon_as_placed(self):
        r = simulate(FLEET, [job("big", gpus=8, duration=50), job("inf", replicas=3, gpus=8, kind="inference")],
                     Policy("default"))
        starts = sorted(r.records["inf"].replica_start)
        self.assertEqual(starts, [0, 50, 100])               # each replica works as soon as it has a node
        self.assertEqual(r.records["inf"].start, 100)
        self.assertEqual(r.stranded_gpu_s, 0)                # independent replicas are never stranded


class GangTests(unittest.TestCase):
    def test_gang_admission_avoids_the_deadlock(self):
        jobs = [job("g1", replicas=2, gang=True), job("g2", replicas=2, gpus=6, gang=True)]
        r = simulate(FLEET, jobs, Policy("gang", gang=True))
        self.assertFalse(r.deadlocked)
        self.assertEqual((r.records["g1"].start, r.records["g2"].start), (0, 100))   # g2 runs after g1, nobody stuck
        self.assertEqual(r.stranded_gpu_s, 0)

    def test_gang_waits_whole_instead_of_holding_part(self):
        r = simulate(FLEET, [job("blocker", duration=50), job("g", replicas=2, gang=True, arrival=1)],
                     Policy("gang", gang=True))
        self.assertEqual(r.records["g"].start, 50)
        self.assertEqual(r.stranded_gpu_s, 0)            # nothing was held while it waited

    def test_smaller_jobs_backfill_around_a_waiting_gang(self):
        jobs = [job("blocker", duration=50), job("g", replicas=2, gang=True, arrival=1),
                job("small", gpus=4, arrival=2, duration=10)]
        r = simulate(FLEET, jobs, Policy("gang", gang=True))
        self.assertEqual(r.records["small"].start, 2)    # best-effort queue: the waiting gang doesn't block it


class PlacementTests(unittest.TestCase):
    def test_binpack_keeps_whole_nodes_free_for_big_jobs(self):
        small = [job(f"s{i}", gpus=2, duration=100, kind="notebook") for i in range(4)]
        big = job("big", gpus=8, arrival=1, duration=10)
        spread = simulate(FLEET, small + [big], Policy("spread", placement="spread"))
        packed = simulate(FLEET, small + [big], Policy("binpack", placement="binpack"))
        self.assertEqual(spread.records["big"].start, 100)   # 4 GPUs free on each node: the 8-GPU job can't fit
        self.assertEqual(packed.records["big"].start, 1)     # the small jobs share one node; the other is empty
        self.assertEqual(len({packed.records[f"s{i}"].nodes[0] for i in range(4)}), 1)

    def test_binpack_prefers_the_tightest_fit(self):
        jobs = [job("a", gpus=6, duration=100), job("b", gpus=3, duration=100, arrival=1), job("c", gpus=2, arrival=2)]
        r = simulate(FLEET, jobs, Policy("binpack", placement="binpack"))
        self.assertEqual(r.records["c"].nodes[0], r.records["a"].nodes[0])   # 2 GPUs left there: an exact fit

    def test_unknown_policy_values_are_rejected(self):
        with self.assertRaises(ValueError):
            Policy("x", placement="round-robin")


class OvercommitGateTests(unittest.TestCase):
    # c runs, then gang a is admitted but can't fit; b (1 GPU) still passes the gate, d (4 GPUs) does not:
    # 16 waiting + 4 > 1.2 x 16 - 2 in use. Without the gate d starts at once.
    JOBS = [job("c", gpus=1, duration=100), job("a", arrival=1, replicas=2, gang=True),
            job("b", arrival=2, gpus=1, duration=100), job("d", arrival=3, gpus=4, duration=10)]

    def test_queued_demand_holds_back_later_jobs(self):
        gated = simulate(FLEET, self.JOBS, Policy("v", gang=True, enqueue_overcommit=1.2))
        open_ = simulate(FLEET, self.JOBS, Policy("v", gang=True))
        self.assertEqual(open_.records["d"].start, 3)
        self.assertEqual(gated.records["b"].start, 2)
        self.assertGreater(gated.records["d"].start, gated.records["a"].start)   # d waited behind the admitted gang

    def test_factor_below_one_is_rejected(self):
        with self.assertRaises(ValueError):
            Policy("v", enqueue_overcommit=0.5)


class QueueTests(unittest.TestCase):
    JOBS = [job("blocker", duration=50), job("g", replicas=2, gang=True, arrival=1),
            job("small", gpus=4, arrival=2, duration=10)]

    def test_strict_fifo_blocks_behind_the_head(self):
        r = simulate(FLEET, self.JOBS, Policy("strict", gang=True, queue="strict"))
        self.assertEqual(r.records["g"].start, 50)
        self.assertEqual(r.records["small"].start, 50 + 100)   # waits for the head gang to start and finish
        # (the gang took both nodes at t=50, so small only fits after it ends)

    def test_best_effort_lets_small_jobs_through(self):
        r = simulate(FLEET, self.JOBS, Policy("best-effort", gang=True, queue="best-effort"))
        self.assertEqual(r.records["small"].start, 2)


class QuotaTests(unittest.TestCase):
    JOBS = [job("a1", team="a"), job("a2", team="a", arrival=1), job("b1", team="b", arrival=30)]

    def test_without_borrowing_idle_gpus_stay_idle(self):
        r = simulate(FLEET, self.JOBS, Policy("q", gang=True, quotas={"a": 0.5, "b": 0.5}))
        self.assertEqual(r.records["a2"].start, 100)     # team a is at its 8-GPU quota; node 2 sits idle until a1 ends
        self.assertEqual(r.records["b1"].start, 30)      # team b's quota was kept free for it

    def test_borrowing_uses_idle_quota(self):
        r = simulate(FLEET, self.JOBS, Policy("q", gang=True, quotas={"a": 0.5, "b": 0.5}, borrowing=True))
        self.assertEqual(r.records["a2"].start, 1)       # borrowed team b's idle quota
        self.assertEqual(r.records["b1"].start, 100)     # ...so b waits until a GPU frees (preemption comes later)

    def test_quota_validation(self):
        with self.assertRaises(ValueError):
            Policy("bad", quotas={"a": 0.7, "b": 0.6})
        with self.assertRaises(ValueError):
            Policy("bad", borrowing=True)


class ReclaimTests(unittest.TestCase):
    POLICY = Policy("reclaim", gang=True, quotas={"a": 0.5, "b": 0.5}, borrowing=True, reclaim=True)

    def test_owner_reclaims_borrowed_quota(self):
        jobs = [job("a1", team="a"), job("a2", team="a", arrival=1), job("b1", team="b", arrival=30)]
        r = simulate(FLEET, jobs, self.POLICY)
        self.assertEqual(r.records["b1"].start, 30)               # took its quota back immediately
        self.assertEqual(r.records["a2"].preemptions, 1)          # the borrower was evicted...
        self.assertEqual(r.records["a2"].start, 100)              # ...and restarted when a1 finished
        self.assertEqual(r.preempted_gpu_s, 8 * 29)               # 29 s of a2's work on 8 GPUs was lost
        self.assertEqual(r.records["a2"].end, 200)                # it ran its full duration again

    def test_jobs_within_quota_are_never_evicted(self):
        jobs = [job("a1", team="a"), job("b1", team="b"), job("b2", team="b", arrival=1)]
        r = simulate(FLEET, jobs, self.POLICY)
        self.assertEqual(r.records["a1"].preemptions, 0)          # team a is inside its quota
        self.assertEqual(r.records["b2"].start, 100)

    def test_reclaim_requires_borrowing(self):
        with self.assertRaises(ValueError):
            Policy("bad", quotas={"a": 1.0}, reclaim=True)


class CheckpointTests(unittest.TestCase):
    POLICY = Policy("reclaim", gang=True, quotas={"a": 0.5, "b": 0.5}, borrowing=True, reclaim=True)

    def test_training_resumes_from_its_last_checkpoint(self):
        # a2 started last, so it is the victim when team b reclaims its quota at t=4000
        jobs = [job("a1", team="a", duration=7200), job("a2", team="a", duration=7200, arrival=1),
                job("b1", team="b", arrival=4000, duration=100)]
        r = simulate(FLEET, jobs, self.POLICY)
        a2 = r.records["a2"]
        self.assertEqual((a2.preemptions, r.records["a1"].preemptions), (1, 0))
        # it ran 3999 s: checkpoints at 1800 and 3600 are kept, the last 399 s are lost
        self.assertEqual(r.preempted_gpu_s, 8 * 399)
        self.assertEqual(a2.end, 4100 + 7200 - 3600)           # restarted when b1 finished, with 3600 s left

    def test_inference_resumes_without_loss(self):
        jobs = [job("a1", team="a", duration=7200), job("svc", team="a", kind="inference", duration=7200, arrival=1),
                job("b1", team="b", arrival=4000, duration=100)]
        r = simulate(FLEET, jobs, self.POLICY)
        self.assertEqual(r.records["svc"].preemptions, 1)
        self.assertEqual(r.preempted_gpu_s, 0)                  # a service loses nothing but its place
        self.assertEqual(r.records["svc"].end, 4100 + (7200 - 3999))


class PriorityPreemptionTests(unittest.TestCase):
    def jobs(self, team_b="a"):
        return [job("train", duration=1000, gpus=8, team="a"), job("train2", duration=1000, gpus=8, team=team_b, arrival=1),
                Job("urgent", 10, "a", "inference", 1, 8, 100, 10, False)]

    def test_global_preemption_evicts_the_newest_lower_priority_job(self):
        r = simulate(FLEET, self.jobs(), Policy("p", priority_preemption="global"))
        self.assertEqual(r.records["urgent"].start, 10)
        self.assertEqual(r.records["train2"].preemptions, 1)       # same priority: the most recently placed goes
        self.assertEqual(r.records["train"].preemptions, 0)

    def test_team_scope_protects_other_teams(self):
        r = simulate(FLEET, self.jobs(team_b="b"), Policy("p", gang=True, priority_preemption="team"))
        self.assertEqual(r.records["urgent"].start, 10)
        self.assertEqual(r.records["train"].preemptions, 1)        # team a's own lower-priority job
        self.assertEqual(r.records["train2"].preemptions, 0)

    def test_evicting_a_partly_finished_job_frees_only_its_running_replicas(self):
        one = parse({"name": "t", "pools": [{"name": "n", "count": 1, "gpus_per_node": 8}]})
        # inf's first replica runs 0-100; its second waits for the blocker and runs from 50. At 120 the urgent
        # job evicts inf, whose finished replica must not hand its 4 GPUs back a second time.
        jobs = [job("blocker", gpus=4, duration=50), Job("inf", 0, "a", "inference", 2, 4, 100, 0, False),
                Job("urgent", 120, "a", "inference", 1, 8, 10, 10, False)]
        r = simulate(one, jobs, Policy("p", priority_preemption="global"))
        self.assertEqual((r.records["urgent"].start, r.records["inf"].preemptions), (120, 1))
        self.assertTrue(all(0 <= free <= 8 for _, _, frees, _ in r.samples for free in frees))
        self.assertEqual(r.records["inf"].replica_end[0], 100)        # the finished replica keeps its result
        self.assertEqual(r.records["inf"].end, 160)                   # resumes its last 30 s after urgent (120-130)

    def test_no_preemption_means_waiting(self):
        r = simulate(FLEET, self.jobs(), Policy("p"))
        self.assertEqual(r.records["urgent"].start, 1000)
        with self.assertRaises(ValueError):
            Policy("bad", priority_preemption="sometimes")


class GpuModelTests(unittest.TestCase):
    MIXED = parse({"name": "m", "pools": [{"name": "h100", "count": 1, "gpus_per_node": 8, "gpu_model": "H100"},
                                           {"name": "l4", "count": 1, "gpus_per_node": 8, "gpu_model": "L4"}]})

    def test_replicas_only_land_on_the_required_model(self):
        jobs = [Job("a", 0, "t", "training", 1, 8, 100, 0, False, "", "H100"),
                Job("b", 0, "t", "training", 1, 8, 100, 0, False, "", "H100")]
        r = simulate(self.MIXED, jobs, Policy("p"))
        self.assertEqual((r.records["a"].nodes[0], r.records["b"].nodes[0]), ("h100-000", "h100-000"))
        self.assertEqual(r.records["b"].start, 100)             # waited for the H100 node; the L4 node stayed idle

    def test_trace_validation_and_manifests(self):
        from gpu_sched_bench import manifests
        from gpu_sched_bench.trace import TraceError, check_fits, dump, parse as parse_trace
        jobs = [Job("x", 0, "t", "training", 1, 8, 60, 0, False, "", "B200")]
        with self.assertRaisesRegex(TraceError, "GPU model"):
            check_fits(jobs, 8, self.MIXED.max_gpus_by_model)
        self.assertEqual(parse_trace(dump(jobs).splitlines())[0].gpu_model, "B200")
        plain = [Job("y", 0, "t", "notebook", 1, 1, 60)]
        self.assertNotIn("gpu_model", dump(plain))              # older traces stay byte-identical
        pod = manifests.render("default", self.MIXED, [Job("z", 0, "t", "training", 1, 8, 60, 0, False, "", "H100")],
                               {}, part="jobs")[0]["spec"]["template"]
        self.assertEqual(pod["spec"]["nodeSelector"]["nvidia.com/gpu.product"], "H100")
