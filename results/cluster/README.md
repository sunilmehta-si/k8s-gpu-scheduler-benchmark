# Model vs real schedulers: smoke trace

From the [cluster workflow run 38688052418](https://github.com/sunilmehta-si/k8s-gpu-scheduler-benchmark/actions/runs/38688052418) at commit `64ca0d5`:
kind + kwok v0.8.0 with each real scheduler installed (Kueue v0.20.1, Volcano v1.16.0, KAI Scheduler 0.18.5), the
12-job `traces/lab-32-smoke.jsonl` on the 32-GPU lab at 300x speed. Every run passed the runtime check (pods ran
1.0x their expected time). These files come from CI and are not regenerated locally.

### Model vs cluster: lab-32, lab-32-smoke.jsonl

| Metric | default model | default cluster | difference |
|---|---|---|---|
| Makespan (h) | 10.6 | 9.4 | -11% |
| GPU utilisation | 43.7% | 41.3% | -6% |
| Useful utilisation | 30.5% | 32.2% | +6% |
| Queue wait p95 (min) | 528.9 | 437.9 | -17% |
| Stranded GPU-hours | 44.8 | 27.3 | -39% |
| Idle GPUs too small for waiting work | 100.0% | 100.0% | +0% |
| Cost per useful GPU-hour | $5.74 | $5.46 | -5% |

### Model vs cluster: lab-32, lab-32-smoke.jsonl

| Metric | kueue model | kueue cluster | difference |
|---|---|---|---|
| Makespan (h) | 9.5 | 7.7 | -18% |
| GPU utilisation | 34.2% | 50.4% | +47% |
| Useful utilisation | 34.2% | 47.1% | +38% |
| Queue wait p95 (min) | 379.3 | 194.5 | -49% |
| Stranded GPU-hours | 0.0 | 8.0 | - |
| Idle GPUs too small for waiting work | 75.3% | 44.6% | -41% |
| Cost per useful GPU-hour | $5.12 | $3.70 | -28% |

### Model vs cluster: lab-32, lab-32-smoke.jsonl

| Metric | volcano model | volcano cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 12.8 | +84% |
| GPU utilisation | 46.7% | 31.5% | -33% |
| Useful utilisation | 46.7% | 29.5% | -37% |
| Queue wait p95 (min) | 71.4 | 570.3 | +699% |
| Stranded GPU-hours | 0.0 | 8.0 | - |
| Idle GPUs too small for waiting work | 66.2% | 89.6% | +35% |
| Cost per useful GPU-hour | $3.74 | $5.91 | +58% |

### Model vs cluster: lab-32, lab-32-smoke.jsonl

| Metric | kai model | kai cluster | difference |
|---|---|---|---|
| Makespan (h) | 6.9 | 7.7 | +11% |
| GPU utilisation | 46.7% | 51.0% | +9% |
| Useful utilisation | 46.7% | 47.8% | +2% |
| Queue wait p95 (min) | 71.4 | 130.9 | +83% |
| Stranded GPU-hours | 0.0 | 8.0 | - |
| Idle GPUs too small for waiting work | 66.2% | 49.6% | -25% |
| Cost per useful GPU-hour | $3.74 | $3.65 | -3% |

