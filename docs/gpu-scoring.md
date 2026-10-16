# Which schedulers bin-pack GPUs out of the box?

Short answer: only KAI Scheduler. The default kube-scheduler, Kueue (which uses kube-scheduler for placement) and
Volcano all score nodes by cpu and memory, so a pod that requests only GPUs is placed without regard to how its
GPUs fit. One configuration setting fixes each of them. This page shows where that behaviour comes from in each
project's code, what it looks like on a real cluster, and the setting to change.

## Why GPU pods are not packed

A training or inference pod usually asks for `nvidia.com/gpu` and little else. Scoring plugins only weigh the
resources they are told about:

| Scheduler | Default node scoring | What a GPU-only pod gets |
|---|---|---|
| kube-scheduler (default, Kueue) | `NodeResourcesFit` with `LeastAllocated`, resources `cpu` and `memory`, weight 1 each | Requests count as kube-scheduler's non-zero defaults, 100m cpu and 200Mi memory. Scores are integers, and one more pod moves a 96-core node's score by about one point per ten pods, so every node that fits ties. kube-scheduler picks one of the tied nodes at random. |
| Volcano v1.16 | `nodeorder` (least-requested on cpu and memory, weight 1) plus `binpack` (cpu and memory, weight 1) | Volcano charges a pod without requests 100m cpu, and `binpack` packs that. Each pod goes to the node already running the most pods, whatever its GPU size. |
| KAI Scheduler | bin-packing of GPUs by default | Pods go to the node whose free GPUs fit them most tightly. |

Sources: kube-scheduler's `NodeResourcesFit` defaults
([scheduler configuration](https://kubernetes.io/docs/reference/scheduling/config/#scheduling-plugins));
Volcano v1.16.0's [`binpack.go`](https://github.com/volcano-sh/volcano/blob/v1.16.0/pkg/scheduler/plugins/binpack/binpack.go)
(the weight map holds `cpu` and `memory` unless `binpack.resources` adds more, and a resource missing from the map
is skipped), [`nodeorder.go`](https://github.com/volcano-sh/volcano/blob/v1.16.0/pkg/scheduler/plugins/nodeorder/nodeorder.go)
(least-requested on `cpu` and `memory`, weight 50 each) and the default scheduler configuration in
[`installer/volcano-development.yaml`](https://github.com/volcano-sh/volcano/blob/v1.16.0/installer/volcano-development.yaml).

## What it looks like on a real cluster

The same 12-job smoke trace (two 8-GPU H100 nodes, four 4-GPU L40S nodes), replayed on each real scheduler in CI
([results/cluster](../results/cluster/README.md)). Where each pod ran:

- **Volcano, as installed:** every notebook and inference pod went to `h100-000`, the node with the most pods,
  until it was full. The 16-GPU training gang needs both H100 nodes, so it waited for those inference pods to end,
  about seven hours later.
- **default kube-scheduler, as installed:** small pods landed on H100 and L40S nodes alike, at random.
- **Volcano, default and Kueue configured to bin-pack GPUs:** every notebook and inference pod went to the L40S
  nodes, and both H100 nodes stayed free for the 8-GPU fine-tunes and the training gang.

`gsb timeline` prints these placements from any cluster run, and `gsb compare` puts them next to the model's.

## The setting to change

**Volcano:** tell `binpack` about GPUs, and give it enough weight to outvote `nodeorder`'s cpu and memory score.
In the `volcano-scheduler-configmap`, keep the default plugin list and give `binpack` arguments:

```yaml
  - name: binpack
    arguments:
      binpack.weight: 10
      binpack.resources: nvidia.com/gpu
      binpack.resources.nvidia.com/gpu: 1
```

Then restart `volcano-scheduler`. `gsb manifests --stack volcano-binpack --part scheduler` prints the whole
ConfigMap, and `scripts/install-volcano-binpack.sh` applies it.

**kube-scheduler (and Kueue):** score GPUs with `MostAllocated`. On a managed cluster you usually can't change the
default scheduler's configuration, so run a second scheduler with its own profile and point GPU workloads at it
with `schedulerName`:

```yaml
apiVersion: kubescheduler.config.k8s.io/v1
kind: KubeSchedulerConfiguration
profiles:
  - schedulerName: gsb-binpack
    pluginConfig:
      - name: NodeResourcesFit
        args:
          scoringStrategy:
            type: MostAllocated
            resources:
              - name: nvidia.com/gpu
                weight: 1
```

`gsb manifests --stack default-binpack --part scheduler` prints the ServiceAccount, RBAC, ConfigMap and
Deployment, following the Kubernetes task
[Configure Multiple Schedulers](https://kubernetes.io/docs/tasks/extend-kubernetes/configure-multiple-schedulers/);
`scripts/install-kube-binpack-scheduler.sh` applies them. Kueue keeps doing admission and quotas; only placement
changes.

**KAI Scheduler:** nothing to do; bin-packing is its default.

## How the model represents this

The presets in [`presets.py`](../gpu_sched_bench/presets.py) carry these behaviours: `random` placement for
kube-scheduler and Kueue, `most-pods` for Volcano, `binpack` for KAI and for the three tuned variants
(`default-binpack`, `kueue-binpack`, `volcano-binpack`). An earlier version of the model assumed that the default
scheduler spread GPU pods and that Volcano bin-packed them. The first real-scheduler runs disagreed by up to 84%,
and the placements recorded by the cluster runs showed why.
