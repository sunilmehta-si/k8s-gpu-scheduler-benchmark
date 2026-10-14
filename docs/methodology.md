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

| Stack | Gang | Placement | Queue | Team quotas | Borrowing | Reclaim |
|---|---|---|---|---|---|---|
| default (kube-scheduler) | no, pod by pod | spread (LeastAllocated) | skip what doesn't fit | - | - | - |
| Kueue | yes (all-or-nothing admission, as with waitForPodsReady) | spread (kube-scheduler places) | BestEffortFIFO | yes | cohort | yes, because gsb configures reclaimWithinCohort: Any (Kueue's default is Never) |
| Volcano | yes (minAvailable) | binpack | skip what doesn't fit | queue weights | yes | no (not in the default actions) |
| KAI | yes (pod groups) | binpack | skip what doesn't fit | queue quotas | over-quota | yes |

Pod-by-pod scheduling queues pods by priority, then creation time. Controllers create a job's pods one after another,
so pods of jobs submitted together interleave, and that's how half-placed gangs and deadlocks happen.

## Limits

- **It is a model.** Real schedulers have many more knobs, scoring plugins and timing effects (scheduling cycles,
  backoff, controller latency). The model is a reference to reason with and to check cluster runs against.
- **No hardware effects.** No GPU performance, NCCL, network topology, thermal throttling or noisy neighbours.
  Placement, queueing and packing only.
- **Synthetic traces.** The job mix is documented in [`generate.py`](../gpu_sched_bench/generate.py). Real traces
  in the same JSONL format can be dropped in.
- **One trace per fleet so far.** Results from a single seed should not be quoted as general truths. Run more seeds
  with `gsb trace generate --seed N` before drawing conclusions.

## Next: cluster runs

`gsb manifests` already renders each stack's configuration (queues, quotas) and every trace job, for kwok fake GPU
nodes (`gsb fleet render`). Each fake pod "finishes" after its trace duration through kwok's pod-complete stage. The
next milestone replays a trace against kind + kwok with each real scheduler installed, writes the same results schema
with `"mode": "cluster"`, and compares it to the model.
