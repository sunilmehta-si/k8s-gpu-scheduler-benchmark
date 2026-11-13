# Model vs real schedulers: smoke trace

From the [cluster workflow run 43266087495](https://github.com/sunilmehta-si/k8s-gpu-scheduler-benchmark/actions/runs/43266087495) at commit `c22d3b4`:
kind + kwok v0.8.0 with each real scheduler installed (Kueue v0.20.4, Volcano v1.16.0, KAI Scheduler 0.18.6), and the three
variants configured to bin-pack GPUs ([docs/gpu-scoring.md](../../docs/gpu-scoring.md)). The 12-job `traces/lab-32-smoke.jsonl` ran on
the 32-GPU lab at 300x speed. Every run passed both checks: pods ran 1.0x their expected time and started a median 0.0 s
after being bound. These files come from CI and are not regenerated locally; `gsb timeline` lists any run's placements.

This is one run. The default scheduler, Kueue and Volcano as installed land on one of two outcomes from run to run,
and this run shows the more common one for each; [repeats.md](repeats.md) has all 30 runs since 16 October.

## default

| Metric | default model | default cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 7.8 | +12% |
| GPU utilisation | 49.2% | 41.5% | -16% |
| Useful utilisation | 46.7% | 33.5% | -28% |
| Queue wait p95 (min) | 192.7 | 335.2 | +74% |
| Stranded GPU-hours | 5.4 | 20.0 | +270% |
| Idle GPUs too small for waiting work | 100.0% | 99.9% | -0% |
| Cost per useful GPU-hour | $3.74 | $5.24 | +40% |

### Per job: default

| Job | Model start (h) | Cluster start (h) | Difference (h) | Model pools | Cluster pools |
|---|---|---|---|---|---|
| training-00007 | 1.33 | 3.74 | +2.42 | h100 | h100 |
| finetune-00008 | 3.87 | 6.24 | +2.37 | h100 | h100 |
| inference-00006 | 0.47 | 0.41 | -0.06 | l40s | h100 |
| finetune-00002 | 0.13 | 0.08 | -0.06 | h100 | h100 |
| notebook-00011 | 0.87 | 0.83 | -0.04 | l40s | h100 |
| notebook-00004 | 0.36 | 0.33 | -0.04 | l40s | h100 |
| notebook-00001 | 0.03 | 0.00 | -0.03 | l40s | h100 |
| notebook-00003 | 0.19 | 0.16 | -0.03 | h100 | h100 |
| inference-00010 | 0.68 | 0.66 | -0.02 | l40s | h100, l40s |
| finetune-00009 | 0.68 | 0.66 | -0.02 | l40s | h100 |
| notebook-00005 | 0.43 | 0.41 | -0.02 | l40s | h100 |
| notebook-00012 | 0.99 | 0.99 | +0.00 | l40s | l40s |

## kueue

| Metric | kueue model | kueue cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 7.7 | +12% |
| GPU utilisation | 46.7% | 41.6% | -11% |
| Useful utilisation | 46.7% | 33.6% | -28% |
| Queue wait p95 (min) | 71.4 | 270.8 | +279% |
| Stranded GPU-hours | 0.0 | 20.0 | - |
| Idle GPUs too small for waiting work | 68.7% | 97.1% | +41% |
| Cost per useful GPU-hour | $3.74 | $5.19 | +39% |

### Per job: kueue

| Job | Model start (h) | Cluster start (h) | Difference (h) | Model pools | Cluster pools |
|---|---|---|---|---|---|
| training-00007 | 1.80 | 5.12 | +3.32 | h100 | h100 |
| finetune-00008 | 0.66 | 1.29 | +0.63 | h100 | h100 |
| notebook-00004 | 0.36 | 0.29 | -0.07 | l40s | h100 |
| notebook-00003 | 0.19 | 0.12 | -0.06 | h100 | h100 |
| notebook-00005 | 0.43 | 0.37 | -0.06 | l40s | h100 |
| notebook-00012 | 0.99 | 0.96 | -0.03 | l40s | l40s |
| finetune-00009 | 0.68 | 0.71 | +0.02 | l40s | h100 |
| inference-00010 | 0.68 | 0.71 | +0.02 | l40s | h100, l40s |
| inference-00006 | 0.47 | 0.46 | -0.02 | l40s | h100 |
| notebook-00001 | 0.03 | 0.04 | +0.01 | l40s | h100 |
| finetune-00002 | 0.13 | 0.12 | -0.01 | h100 | h100 |
| notebook-00011 | 0.87 | 0.87 | +0.01 | l40s | l40s |

## volcano

| Metric | volcano model | volcano cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 9.8 | +42% |
| GPU utilisation | 46.7% | 32.7% | -30% |
| Useful utilisation | 46.7% | 32.7% | -30% |
| Queue wait p95 (min) | 71.4 | 389.9 | +446% |
| Stranded GPU-hours | 0.0 | 0.0 | - |
| Idle GPUs too small for waiting work | 40.2% | 66.1% | +64% |
| Cost per useful GPU-hour | $3.74 | $5.33 | +42% |

### Per job: volcano

| Job | Model start (h) | Cluster start (h) | Difference (h) | Model pools | Cluster pools |
|---|---|---|---|---|---|
| training-00007 | 1.80 | 7.11 | +5.31 | h100 | h100 |
| finetune-00008 | 0.66 | 1.44 | +0.78 | h100 | h100 |
| notebook-00011 | 1.33 | 0.94 | -0.39 | l40s | h100 |
| notebook-00012 | 1.33 | 1.11 | -0.22 | l40s | h100 |
| notebook-00003 | 0.19 | 0.36 | +0.17 | l40s | h100 |
| notebook-00001 | 0.03 | 0.19 | +0.16 | l40s | h100 |
| notebook-00004 | 0.36 | 0.53 | +0.16 | l40s | h100 |
| finetune-00002 | 0.13 | 0.28 | +0.14 | h100 | h100 |
| inference-00006 | 0.47 | 0.61 | +0.14 | l40s | h100 |
| notebook-00005 | 0.43 | 0.53 | +0.09 | l40s | h100 |
| finetune-00009 | 0.68 | 0.78 | +0.09 | l40s | l40s |
| inference-00010 | 0.70 | 0.78 | +0.08 | l40s | h100, l40s |

## kai

| Metric | kai model | kai cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 7.3 | +6% |
| GPU utilisation | 46.7% | 44.0% | -6% |
| Useful utilisation | 46.7% | 44.0% | -6% |
| Queue wait p95 (min) | 71.4 | 79.5 | +11% |
| Stranded GPU-hours | 0.0 | 0.0 | - |
| Idle GPUs too small for waiting work | 66.2% | 39.4% | -40% |
| Cost per useful GPU-hour | $3.74 | $3.96 | +6% |

### Per job: kai

| Job | Model start (h) | Cluster start (h) | Difference (h) | Model pools | Cluster pools |
|---|---|---|---|---|---|
| training-00007 | 1.80 | 1.94 | +0.14 | h100 | h100 |
| inference-00010 | 0.68 | 0.77 | +0.09 | l40s | l40s |
| notebook-00001 | 0.03 | 0.10 | +0.07 | l40s | l40s |
| notebook-00004 | 0.36 | 0.44 | +0.07 | l40s | l40s |
| notebook-00011 | 0.87 | 0.94 | +0.07 | l40s | l40s |
| finetune-00002 | 0.13 | 0.19 | +0.05 | h100 | h100 |
| inference-00006 | 0.47 | 0.52 | +0.05 | l40s | l40s |
| notebook-00012 | 0.99 | 1.02 | +0.03 | l40s | l40s |
| finetune-00008 | 0.66 | 0.69 | +0.03 | h100 | h100 |
| notebook-00005 | 0.43 | 0.44 | +0.01 | l40s | l40s |
| finetune-00009 | 0.68 | 0.69 | +0.00 | l40s | l40s |
| notebook-00003 | 0.19 | 0.19 | -0.00 | l40s | l40s |

## default-binpack

| Metric | default-binpack model | default-binpack cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 7.3 | +6% |
| GPU utilisation | 49.3% | 43.9% | -11% |
| Useful utilisation | 46.7% | 41.7% | -11% |
| Queue wait p95 (min) | 192.7 | 146.3 | -24% |
| Stranded GPU-hours | 5.7 | 5.3 | -7% |
| Idle GPUs too small for waiting work | 100.0% | 100.0% | +0% |
| Cost per useful GPU-hour | $3.74 | $4.19 | +12% |

### Per job: default-binpack

| Job | Model start (h) | Cluster start (h) | Difference (h) | Model pools | Cluster pools |
|---|---|---|---|---|---|
| finetune-00008 | 3.87 | 3.10 | -0.77 | h100 | h100 |
| training-00007 | 1.33 | 1.26 | -0.06 | h100 | h100 |
| notebook-00012 | 0.99 | 0.93 | -0.06 | l40s | l40s |
| inference-00006 | 0.47 | 0.43 | -0.04 | l40s | l40s |
| finetune-00002 | 0.13 | 0.10 | -0.04 | h100 | h100 |
| notebook-00011 | 0.87 | 0.85 | -0.02 | l40s | l40s |
| notebook-00004 | 0.36 | 0.35 | -0.02 | l40s | l40s |
| notebook-00001 | 0.03 | 0.01 | -0.02 | l40s | l40s |
| notebook-00003 | 0.19 | 0.18 | -0.01 | l40s | l40s |
| inference-00010 | 0.68 | 0.68 | -0.01 | l40s | l40s |
| finetune-00009 | 0.68 | 0.68 | -0.00 | l40s | l40s |
| notebook-00005 | 0.43 | 0.43 | -0.00 | l40s | l40s |

## kueue-binpack

| Metric | kueue-binpack model | kueue-binpack cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 7.3 | +6% |
| GPU utilisation | 46.7% | 44.1% | -6% |
| Useful utilisation | 46.7% | 44.1% | -6% |
| Queue wait p95 (min) | 71.4 | 122.0 | +71% |
| Stranded GPU-hours | 0.0 | 0.0 | - |
| Idle GPUs too small for waiting work | 66.2% | 44.6% | -33% |
| Cost per useful GPU-hour | $3.74 | $3.98 | +6% |

### Per job: kueue-binpack

| Job | Model start (h) | Cluster start (h) | Difference (h) | Model pools | Cluster pools |
|---|---|---|---|---|---|
| training-00007 | 1.80 | 2.64 | +0.84 | h100 | h100 |
| finetune-00008 | 0.66 | 1.31 | +0.65 | h100 | h100 |
| finetune-00002 | 0.13 | 0.06 | -0.07 | h100 | h100 |
| notebook-00011 | 0.87 | 0.81 | -0.06 | l40s | l40s |
| notebook-00004 | 0.36 | 0.31 | -0.05 | l40s | l40s |
| notebook-00003 | 0.19 | 0.14 | -0.04 | l40s | l40s |
| inference-00010 | 0.68 | 0.64 | -0.04 | l40s | l40s |
| finetune-00009 | 0.68 | 0.64 | -0.04 | l40s | l40s |
| notebook-00005 | 0.43 | 0.39 | -0.04 | l40s | l40s |
| notebook-00001 | 0.03 | 0.00 | -0.03 | l40s | l40s |
| notebook-00012 | 0.99 | 0.98 | -0.01 | l40s | l40s |
| inference-00006 | 0.47 | 0.48 | +0.00 | l40s | l40s |

## volcano-binpack

| Metric | volcano-binpack model | volcano-binpack cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 7.3 | +6% |
| GPU utilisation | 46.7% | 43.9% | -6% |
| Useful utilisation | 46.7% | 43.9% | -6% |
| Queue wait p95 (min) | 71.4 | 79.9 | +12% |
| Stranded GPU-hours | 0.0 | 0.0 | - |
| Idle GPUs too small for waiting work | 40.2% | 33.8% | -16% |
| Cost per useful GPU-hour | $3.74 | $3.97 | +6% |

### Per job: volcano-binpack

| Job | Model start (h) | Cluster start (h) | Difference (h) | Model pools | Cluster pools |
|---|---|---|---|---|---|
| notebook-00011 | 1.33 | 0.94 | -0.39 | l40s | l40s |
| notebook-00012 | 1.33 | 1.03 | -0.30 | l40s | l40s |
| training-00007 | 1.80 | 1.94 | +0.14 | h100 | h100 |
| notebook-00005 | 0.43 | 0.53 | +0.10 | l40s | l40s |
| finetune-00009 | 0.68 | 0.78 | +0.09 | l40s | l40s |
| notebook-00003 | 0.19 | 0.28 | +0.09 | l40s | l40s |
| notebook-00001 | 0.03 | 0.11 | +0.08 | l40s | l40s |
| notebook-00004 | 0.36 | 0.44 | +0.08 | l40s | l40s |
| inference-00010 | 0.70 | 0.78 | +0.08 | l40s | l40s |
| finetune-00002 | 0.13 | 0.19 | +0.06 | h100 | h100 |
| inference-00006 | 0.47 | 0.53 | +0.05 | l40s | l40s |
| finetune-00008 | 0.66 | 0.69 | +0.04 | h100 | h100 |
