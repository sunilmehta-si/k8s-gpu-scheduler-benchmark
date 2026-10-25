# Methodology

## What is measured

Every stack receives the same fleet and the same trace: identical jobs, in the same order, at the same times.
Each run reports placement and queueing outcomes, not GPU performance.

| Metric | Definition |
|---|---|
| Makespan | Time from the first arrival until the last job finishes |
| GPU utilisation | GPU-time held by placed replicas / (fleet GPUs x makespan) |
| Useful utilisation | The same, minus GPU-time held by gang replicas still waiting for the rest of their gang |
| Queue wait | From a job's arrival until its *last* replica starts (when the job as a whole can run); nearest-rank percentiles |
| Stranded GPU-hours | GPUs held by a partly placed gang, doing nothing |
| Preempted work | Work lost to preemption: training and fine-tunes lose progress since their last 30-minute checkpoint; inference and notebooks resume |
| GPU-hours idle while work waited | Free GPU-time during any period in which at least one job was waiting |
| Idle GPUs too small for waiting work | Of those idle GPUs, the share on nodes with fewer free GPUs than the smallest waiting replica needs. It counts fragmentation and node-shape mismatch alike |
| Partly used nodes | Time-weighted share of nodes that are neither empty nor full |
| Fairness between teams | Jain's index over each team's mean runtime / (wait + runtime): 1.0 means every team was delayed equally |
| Fleet cost until the last job finished | Every GPU in the fleet at its pool's price for the makespan, idle or not |
| Cost per useful GPU-hour | That cost / GPU-hours of useful work. The number to compare across stacks |

## How each stack is modelled

`gsb simulate` runs a discrete-event model, not the schedulers. Each preset combines a few documented behaviours, and
the code says where each one comes from ([`presets.py`](../gpu_sched_bench/presets.py)):

| Stack | Gang | Placement | Queue | Team quotas | Borrowing | Reclaim | Priority preemption |
|---|---|---|---|---|---|---|---|
| default (kube-scheduler) | no, pod by pod | random among nodes that fit (its scoring ignores GPUs) | skip what doesn't fit | - | - | - | cluster-wide (gsb's PriorityClasses use PreemptLowerPriority) |
| Kueue | yes (all-or-nothing admission, as with waitForPodsReady) | random (kube-scheduler places) | BestEffortFIFO | yes | cohort | yes, because gsb configures reclaimWithinCohort: Any (Kueue's default is Never) | within a team (withinClusterQueue: LowerPriority) |
| Volcano | yes (minAvailable) | most-pods (its binpack packs the default cpu request, not GPUs) | skip what doesn't fit, behind the 1.2x overcommit gate | queue weights | yes | no (not in the default actions) | no (not in the default actions) |
| KAI | yes (pod groups) | binpack | skip what doesn't fit | queue quotas | over-quota | yes | within a queue |
| default-binpack, kueue-binpack, volcano-binpack | as their base stack | binpack (configured to score GPUs) | as base | as base | as base | as base | as base |

Why placement differs from what each project's docs suggest is explained, with sources, in
[gpu-scoring.md](gpu-scoring.md). `random` and `most-pods` break ties with a seeded generator, so a single run is one
draw; sweeps vary the seed.

Victims of any preemption are the lowest-priority, most recently placed jobs, and nothing is evicted unless the
evictions let the waiting job start. Training and fine-tunes resume from their last 30-minute checkpoint; inference
and notebooks resume where they stopped. Jobs that require a GPU model (`gpu_model` in the trace) are only placed on
nodes of that model.

Pod-by-pod scheduling queues pods by priority, then creation time. Controllers create a job's pods one after another,
so pods of jobs submitted together interleave, and that's how half-placed gangs and deadlocks happen.

## Reading sweeps and ablations

- **`gsb sweep`** repeats the comparison over many seeded traces and reports mean, standard deviation and range per
  metric, plus how many seeds each stack was cheapest on. Quote these, not a single trace.
- **`gsb ablate`** starts from the default scheduler (random placement) and switches on one behaviour at a time
  (gang, bin-packing, quotas, borrowing, reclaim), plus bin-packing alone and GPU spreading alone. It attributes a
  stack's advantage to the behaviour behind it. On the 256-GPU sample trace, spreading by GPUs is what costs time
  (26.0 h against 19.9 h); random placement and bin-packing finish together.

## Limits

- **It is a model.** Real schedulers have many more knobs, scoring plugins and timing effects (scheduling cycles,
  backoff, controller latency). The model is a reference to reason with and to check cluster runs against.
- **No hardware effects.** No GPU performance, NCCL, network topology, thermal throttling or noisy neighbours.
  Placement, queueing and packing only.
- **Synthetic traces.** The job mix is documented in [`generate.py`](../gpu_sched_bench/generate.py). Real traces
  in the same JSONL format can be dropped in.
- **Seeds matter.** On the 256-GPU fleet the cheapest stack changes between seeds (see the committed sweep), so a
  single trace is an example, not a verdict. Use `gsb sweep`.
- **Checked at one scale.** The comparison with the real schedulers below uses the 32-GPU lab. The 256-GPU and
  1,024-GPU results are simulation only; the stacks' relative order there follows from the same modelled
  behaviours, but has not been measured on a cluster.

## How close is the model?

Real-scheduler runs of all seven stacks ([results/cluster](../results/cluster/README.md); 12-job smoke trace, 32-GPU
lab, kind + kwok, CI run 38889757797) against the model over 100 placement seeds:

| Stack | Model, median (range) | Real scheduler | Read |
|---|---|---|---|
| default | 10.3 h (6.9-10.6) | 7.8 h | inside the model's range; one random draw on each side |
| Kueue v0.20.1 | 9.1 h (6.9-9.5) | 7.3 h | inside the range |
| Volcano v1.16.0 | 9.5 h (6.9-9.5) | 9.9 h | within 4% of the median: small pods stack on one H100 node and hold the training gang back |
| KAI 0.18.5 | 6.9 h | 7.3 h | +6% |
| default-, kueue-, volcano-binpack | 6.9 h | 7.3 h each | +6% |

Every stack that packs GPUs is 6% slower on the real control plane than in the model, consistently: that is
scheduling and controller latency, which the model does not include. The stacks that place GPU pods without looking at
GPUs vary from run to run, on the real scheduler as in the model, because their outcome depends on which nodes small
pods happen to land on.

Getting here took two harness fixes and a better Volcano model, each found by comparing placements rather than
totals. The first runs disagreed by up to 84%. kwok's pod-create and pod-ready delays had idled every pod for 30 trace
minutes ([cluster-runs.md](cluster-runs.md#how-a-run-is-checked)), and the Volcano preset assumed GPU bin-packing that
Volcano's defaults don't do. Use the simulation to reason about behaviours and to rank configurations, and use
cluster runs before choosing a scheduler.

## Cluster runs

`gsb cluster run` replays a trace against a kind + kwok cluster with the real scheduler installed and writes the same
results schema with `"mode": "cluster"`; `gsb compare` puts it next to the model. See [cluster-runs.md](cluster-runs.md).
