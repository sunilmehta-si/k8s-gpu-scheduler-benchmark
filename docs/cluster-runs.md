# Running the real schedulers

`gsb simulate` predicts; a cluster run checks the prediction against the real scheduler. Both write the same
results schema and are measured by the same code, so they can be compared metric by metric.

## What runs where

| Piece | Real | Simulated |
|---|---|---|
| Kubernetes API server, the scheduler under test, its controllers and webhooks | yes | |
| GPU nodes | Node objects with `nvidia.com/gpu` capacity | no kubelet, no hardware (kwok) |
| Workloads | Jobs and pods created by the stack's own controllers | pods "run" for the trace duration / speedup, then succeed (kwok) |

So placement, queueing, quotas, gang behaviour and preemption are the scheduler's own. GPU performance, network
topology and container start-up are not part of the measurement.

## Run it yourself

Needs Docker, [kind](https://kind.sigs.k8s.io/), kubectl, and Helm for KAI.

```bash
pip install -e .
scripts/cluster-up.sh                       # kind cluster + kwok with delayed pod completion
scripts/install-kai.sh                      # or install-kueue.sh / install-volcano.sh; nothing for "default"
gsb cluster run --stack kai --fleet fleets/lab-32.yaml --trace traces/lab-32-smoke.jsonl \
  --speedup 300 --strict -o cluster-kai.json
gsb simulate --stacks kai --fleet fleets/lab-32.yaml --trace traces/lab-32-smoke.jsonl -o model-kai.json
gsb compare model-kai.json cluster-kai.json
```

Use a fresh cluster per stack: schedulers installed side by side would compete for the same pods.

`gsb cluster run` creates the kwok GPU nodes, applies the stack's queues and quotas (retrying while admission
webhooks start), submits each job at its arrival time divided by `--speedup`, waits until every pod has succeeded or
`--timeout` passes, and collects each pod's node and its scheduled, started and finished times.

## How a run is checked

Every run compares each pod's observed runtime with its expected runtime (trace duration / speedup) and records the
median ratio as `runtime_check` in the results. With `--strict` the command exits 1 when the median is outside
0.75–1.33x. That catches a misconfigured kwok, which otherwise produces plausible-looking but meaningless numbers.

It caught exactly that during development. kwok picks a random completion delay between
`pod-complete.stage.kwok.x-k8s.io/delay` and `.../jitter-delay`, and uses the jitter value outright when it is not
larger (`Stage.Delay` in kwok's `pkg/utils/lifecycle/lifecycle.go`). A jitter of `0s` therefore means *no* delay,
and leaving it out caps every delay at kwok's 5-second default. The manifests set both annotations to the same value.

kwok's `stage-fast.yaml` release asset completes pods immediately; `scripts/cluster-up.sh` installs the
`pod/general` stages instead, which read the delay annotations.

## In CI

The [`cluster` workflow](../.github/workflows/cluster.yml) runs the smoke trace through all four stacks on every
push to `main` and weekly, posts the cluster and model reports to the job summary, and uploads both results files.
Versions are pinned in the install scripts: kwok v0.8.0, Kueue v0.20.1, Volcano v1.16.0, KAI Scheduler 0.18.5.

## Known gaps

- Preemptions are not reconstructed from final pod state, so cluster runs report preempted work as 0.
- The smoke trace is small (12 jobs) to keep CI fast. Larger traces work the same way; they just take longer.
- The NVIDIA Run:ai full platform and DRA-based GPU allocation are not covered yet.
