# Model vs real schedulers: smoke trace

From the [cluster workflow run 38889757797](https://github.com/sunilmehta-si/k8s-gpu-scheduler-benchmark/actions/runs/38889757797) at commit `6538709`:
kind + kwok v0.8.0 with each real scheduler installed (Kueue v0.20.1, Volcano v1.16.0, KAI Scheduler 0.18.5), and the three
variants configured to bin-pack GPUs ([docs/gpu-scoring.md](../../docs/gpu-scoring.md)). The 12-job `traces/lab-32-smoke.jsonl` ran on
the 32-GPU lab at 300x speed. Every run passed both checks: pods ran 1.0x their expected time and started a median 0.0 s
after being bound. These files come from CI and are not regenerated locally; `gsb timeline` lists any run's placements.

## default

| Metric | default model | default cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 7.8 | +12% |
| GPU utilisation | 49.2% | 41.6% | -15% |
| Useful utilisation | 46.7% | 33.5% | -28% |
| Queue wait p95 (min) | 192.7 | 338.2 | +76% |
| Stranded GPU-hours | 5.4 | 20.0 | +270% |
| Idle GPUs too small for waiting work | 100.0% | 100.0% | +0% |
| Cost per useful GPU-hour | $3.74 | $5.25 | +40% |

### Per job: default

| Job | Model start (h) | Cluster start (h) | Difference (h) | Model pools | Cluster pools |
|---|---|---|---|---|---|
| training-00007 | 1.33 | 3.79 | +2.47 | h100 | h100 |
| finetune-00008 | 3.87 | 6.29 | +2.42 | h100 | h100 |
| notebook-00011 | 0.87 | 0.79 | -0.07 | l40s | h100 |
| notebook-00004 | 0.36 | 0.29 | -0.07 | l40s | h100 |
| notebook-00003 | 0.19 | 0.13 | -0.06 | h100 | h100 |
| inference-00010 | 0.68 | 0.63 | -0.06 | l40s | h100, l40s |
| finetune-00009 | 0.68 | 0.63 | -0.06 | l40s | h100 |
| notebook-00005 | 0.43 | 0.38 | -0.05 | l40s | h100 |
| notebook-00001 | 0.03 | 0.00 | -0.03 | l40s | h100 |
| notebook-00012 | 0.99 | 0.96 | -0.03 | l40s | l40s |
| inference-00006 | 0.47 | 0.46 | -0.01 | l40s | h100 |
| finetune-00002 | 0.13 | 0.13 | -0.01 | h100 | h100 |

## kueue

| Metric | kueue model | kueue cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 7.3 | +6% |
| GPU utilisation | 46.7% | 43.9% | -6% |
| Useful utilisation | 46.7% | 43.9% | -6% |
| Queue wait p95 (min) | 71.4 | 99.7 | +40% |
| Stranded GPU-hours | 0.0 | 0.0 | - |
| Idle GPUs too small for waiting work | 68.7% | 48.0% | -30% |
| Cost per useful GPU-hour | $3.74 | $3.97 | +6% |

### Per job: kueue

| Job | Model start (h) | Cluster start (h) | Difference (h) | Model pools | Cluster pools |
|---|---|---|---|---|---|
| training-00007 | 1.80 | 2.27 | +0.47 | h100 | h100 |
| finetune-00008 | 0.66 | 0.94 | +0.28 | h100 | h100 |
| notebook-00012 | 0.99 | 0.94 | -0.05 | l40s | l40s |
| inference-00006 | 0.47 | 0.44 | -0.03 | l40s | l40s |
| finetune-00002 | 0.13 | 0.11 | -0.03 | h100 | h100 |
| notebook-00011 | 0.87 | 0.86 | -0.01 | l40s | l40s |
| notebook-00005 | 0.43 | 0.44 | +0.01 | l40s | l40s |
| notebook-00004 | 0.36 | 0.36 | -0.01 | l40s | l40s |
| notebook-00001 | 0.03 | 0.02 | -0.01 | l40s | l40s |
| finetune-00009 | 0.68 | 0.69 | +0.01 | l40s | l40s |
| inference-00010 | 0.68 | 0.69 | +0.01 | l40s | l40s |
| notebook-00003 | 0.19 | 0.19 | +0.00 | h100 | l40s |

## volcano

| Metric | volcano model | volcano cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 9.9 | +42% |
| GPU utilisation | 46.7% | 32.7% | -30% |
| Useful utilisation | 46.7% | 32.7% | -30% |
| Queue wait p95 (min) | 71.4 | 391.1 | +448% |
| Stranded GPU-hours | 0.0 | 0.0 | - |
| Idle GPUs too small for waiting work | 40.2% | 68.3% | +70% |
| Cost per useful GPU-hour | $3.74 | $5.34 | +43% |

### Per job: volcano

| Job | Model start (h) | Cluster start (h) | Difference (h) | Model pools | Cluster pools |
|---|---|---|---|---|---|
| training-00007 | 1.80 | 7.13 | +5.33 | h100 | h100 |
| finetune-00008 | 0.66 | 1.46 | +0.80 | h100 | h100 |
| notebook-00011 | 1.33 | 0.96 | -0.37 | l40s | h100 |
| notebook-00012 | 1.33 | 1.13 | -0.20 | l40s | h100 |
| notebook-00003 | 0.19 | 0.30 | +0.11 | l40s | h100 |
| notebook-00001 | 0.03 | 0.13 | +0.10 | l40s | h100 |
| notebook-00004 | 0.36 | 0.46 | +0.10 | l40s | h100 |
| finetune-00002 | 0.13 | 0.21 | +0.08 | h100 | h100 |
| inference-00006 | 0.47 | 0.55 | +0.07 | l40s | h100 |
| notebook-00005 | 0.43 | 0.46 | +0.03 | l40s | h100 |
| finetune-00009 | 0.68 | 0.71 | +0.03 | l40s | l40s |
| inference-00010 | 0.70 | 0.71 | +0.01 | l40s | h100, l40s |

## kai

| Metric | kai model | kai cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 7.3 | +6% |
| GPU utilisation | 46.7% | 43.9% | -6% |
| Useful utilisation | 46.7% | 43.9% | -6% |
| Queue wait p95 (min) | 71.4 | 81.2 | +14% |
| Stranded GPU-hours | 0.0 | 0.0 | - |
| Idle GPUs too small for waiting work | 66.2% | 43.1% | -35% |
| Cost per useful GPU-hour | $3.74 | $3.97 | +6% |

### Per job: kai

| Job | Model start (h) | Cluster start (h) | Difference (h) | Model pools | Cluster pools |
|---|---|---|---|---|---|
| training-00007 | 1.80 | 1.96 | +0.16 | h100 | h100 |
| inference-00010 | 0.68 | 0.80 | +0.11 | l40s | l40s |
| notebook-00012 | 0.99 | 1.05 | +0.06 | l40s | l40s |
| finetune-00008 | 0.66 | 0.71 | +0.06 | h100 | h100 |
| notebook-00005 | 0.43 | 0.46 | +0.03 | l40s | l40s |
| finetune-00009 | 0.68 | 0.71 | +0.03 | l40s | l40s |
| notebook-00003 | 0.19 | 0.21 | +0.02 | l40s | l40s |
| notebook-00001 | 0.03 | 0.05 | +0.02 | l40s | l40s |
| notebook-00004 | 0.36 | 0.38 | +0.02 | l40s | l40s |
| notebook-00011 | 0.87 | 0.88 | +0.01 | l40s | l40s |
| inference-00006 | 0.47 | 0.46 | -0.01 | l40s | l40s |
| finetune-00002 | 0.13 | 0.13 | -0.00 | h100 | h100 |

## default-binpack

| Metric | default-binpack model | default-binpack cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 7.3 | +6% |
| GPU utilisation | 49.3% | 44.5% | -10% |
| Useful utilisation | 46.7% | 41.9% | -10% |
| Queue wait p95 (min) | 192.7 | 148.6 | -23% |
| Stranded GPU-hours | 5.7 | 6.0 | +5% |
| Idle GPUs too small for waiting work | 100.0% | 93.1% | -7% |
| Cost per useful GPU-hour | $3.74 | $4.19 | +12% |

### Per job: default-binpack

| Job | Model start (h) | Cluster start (h) | Difference (h) | Model pools | Cluster pools |
|---|---|---|---|---|---|
| finetune-00008 | 3.87 | 3.13 | -0.73 | h100 | h100 |
| inference-00010 | 0.68 | 0.80 | +0.12 | l40s | l40s |
| notebook-00011 | 0.87 | 0.80 | -0.07 | l40s | l40s |
| notebook-00005 | 0.43 | 0.38 | -0.05 | l40s | l40s |
| finetune-00009 | 0.68 | 0.72 | +0.03 | l40s | l40s |
| notebook-00001 | 0.03 | 0.00 | -0.03 | l40s | l40s |
| notebook-00003 | 0.19 | 0.22 | +0.03 | l40s | l40s |
| training-00007 | 1.33 | 1.30 | -0.03 | h100 | h100 |
| notebook-00012 | 0.99 | 0.97 | -0.02 | l40s | l40s |
| notebook-00004 | 0.36 | 0.38 | +0.02 | l40s | l40s |
| inference-00006 | 0.47 | 0.47 | -0.01 | l40s | l40s |
| finetune-00002 | 0.13 | 0.13 | +0.00 | h100 | h100 |

## kueue-binpack

| Metric | kueue-binpack model | kueue-binpack cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 7.3 | +6% |
| GPU utilisation | 46.7% | 43.9% | -6% |
| Useful utilisation | 46.7% | 43.9% | -6% |
| Queue wait p95 (min) | 71.4 | 120.1 | +68% |
| Stranded GPU-hours | 0.0 | 0.0 | - |
| Idle GPUs too small for waiting work | 66.2% | 41.2% | -38% |
| Cost per useful GPU-hour | $3.74 | $3.97 | +6% |

### Per job: kueue-binpack

| Job | Model start (h) | Cluster start (h) | Difference (h) | Model pools | Cluster pools |
|---|---|---|---|---|---|
| training-00007 | 1.80 | 2.61 | +0.81 | h100 | h100 |
| finetune-00008 | 0.66 | 1.28 | +0.62 | h100 | h100 |
| finetune-00009 | 0.68 | 0.78 | +0.10 | l40s | l40s |
| inference-00010 | 0.68 | 0.78 | +0.10 | l40s | l40s |
| notebook-00005 | 0.43 | 0.36 | -0.07 | l40s | l40s |
| notebook-00012 | 0.99 | 0.95 | -0.04 | l40s | l40s |
| inference-00006 | 0.47 | 0.45 | -0.03 | l40s | l40s |
| finetune-00002 | 0.13 | 0.11 | -0.02 | h100 | h100 |
| notebook-00003 | 0.19 | 0.20 | +0.01 | l40s | l40s |
| notebook-00011 | 0.87 | 0.86 | -0.00 | l40s | l40s |
| notebook-00004 | 0.36 | 0.36 | -0.00 | l40s | l40s |
| notebook-00001 | 0.03 | 0.03 | +0.00 | l40s | l40s |

## volcano-binpack

| Metric | volcano-binpack model | volcano-binpack cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 7.3 | +6% |
| GPU utilisation | 46.7% | 43.9% | -6% |
| Useful utilisation | 46.7% | 43.9% | -6% |
| Queue wait p95 (min) | 71.4 | 80.2 | +12% |
| Stranded GPU-hours | 0.0 | 0.0 | - |
| Idle GPUs too small for waiting work | 40.2% | 32.8% | -18% |
| Cost per useful GPU-hour | $3.74 | $3.97 | +6% |

### Per job: volcano-binpack

| Job | Model start (h) | Cluster start (h) | Difference (h) | Model pools | Cluster pools |
|---|---|---|---|---|---|
| notebook-00011 | 1.33 | 0.95 | -0.38 | l40s | l40s |
| notebook-00012 | 1.33 | 1.03 | -0.30 | l40s | l40s |
| training-00007 | 1.80 | 1.95 | +0.15 | h100 | h100 |
| notebook-00005 | 0.43 | 0.53 | +0.10 | l40s | l40s |
| finetune-00009 | 0.68 | 0.78 | +0.10 | l40s | l40s |
| notebook-00003 | 0.19 | 0.28 | +0.09 | l40s | l40s |
| notebook-00001 | 0.03 | 0.11 | +0.08 | l40s | l40s |
| notebook-00004 | 0.36 | 0.45 | +0.08 | l40s | l40s |
| inference-00010 | 0.70 | 0.78 | +0.08 | l40s | l40s |
| finetune-00002 | 0.13 | 0.20 | +0.07 | h100 | h100 |
| inference-00006 | 0.47 | 0.53 | +0.06 | l40s | l40s |
| finetune-00008 | 0.66 | 0.70 | +0.04 | h100 | h100 |
