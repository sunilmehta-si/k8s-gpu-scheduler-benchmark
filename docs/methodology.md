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
| default (kube-scheduler) | no, pod by pod | spread (LeastAllocated) | skip what doesn't fit | - | - | - | cluster-wide (gsb's PriorityClasses use PreemptLowerPriority) |
| Kueue | yes (all-or-nothing admission, as with waitForPodsReady) | spread (kube-scheduler places) | BestEffortFIFO | yes | cohort | yes, because gsb configures reclaimWithinCohort: Any (Kueue's default is Never) | within a team (withinClusterQueue: LowerPriority) |
| Volcano | yes (minAvailable) | binpack | skip what doesn't fit | queue weights | yes | no (not in the default actions) | no (not in the default actions) |
| KAI | yes (pod groups) | binpack | skip what doesn't fit | queue quotas | over-quota | yes | within a queue |

Victims of any preemption are the lowest-priority, most recently placed jobs, and nothing is evicted unless the
evictions let the waiting job start. Training and fine-tunes resume from their last 30-minute checkpoint; inference
and notebooks resume where they stopped. Jobs that require a GPU model (`gpu_model` in the trace) are only placed on
nodes of that model.

Pod-by-pod scheduling queues pods by priority, then creation time. Controllers create a job's pods one after another,
so pods of jobs submitted together interleave, and that's how half-placed gangs and deadlocks happen.

## Reading sweeps and ablations

- **`gsb sweep`** repeats the comparison over many seeded traces and reports mean, standard deviation and range per
  metric, plus how many seeds each stack was cheapest on. Quote these, not a single trace.
- **`gsb ablate`** starts from the default scheduler and switches on one behaviour at a time (gang, bin-packing,
  quotas, borrowing, reclaim), plus bin-packing alone. It attributes a stack's advantage to the behaviour behind it.

## Limits

- **It is a model.** Real schedulers have many more knobs, scoring plugins and timing effects (scheduling cycles,
  backoff, controller latency). The model is a reference to reason with and to check cluster runs against.
- **No hardware effects.** No GPU performance, NCCL, network topology, thermal throttling or noisy neighbours.
  Placement, queueing and packing only.
- **Synthetic traces.** The job mix is documented in [`generate.py`](../gpu_sched_bench/generate.py). Real traces
  in the same JSONL format can be dropped in.
- **Seeds matter.** On the 256-GPU fleet the cheapest stack changes between seeds (see the committed sweep), so a
  single trace is an example, not a verdict. Use `gsb sweep`.

## Cluster runs

`gsb cluster run` replays a trace against a kind + kwok cluster with the real scheduler installed and writes the same
results schema with `"mode": "cluster"`; `gsb compare` puts it next to the model. See [cluster-runs.md](cluster-runs.md).
