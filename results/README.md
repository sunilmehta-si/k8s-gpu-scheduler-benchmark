## mixed-256: 256 GPUs on 64 nodes, 131 jobs (2,192 GPU-hours requested)

> Reference simulation of each stack's documented default behaviour, not a run of the schedulers themselves. See [the methodology](../docs/methodology.md).

| Metric | default | kueue | volcano | kai |
|---|---|---|---|---|
| Jobs finished <sub>higher is better</sub> | 131/131 | 131/131 | 131/131 | 131/131 |
| Deadlocked <sub>lower is better</sub> | no | no | no | no |
| Makespan (h) <sub>lower is better</sub> | 19.9 | 19.9 | 19.9 | 19.9 |
| GPU utilisation <sub>higher is better</sub> | **44.7%** | 43.3% | 43.0% | 44.4% |
| Useful utilisation <sub>higher is better</sub> | 43.0% | 43.3% | 43.0% | **44.4%** |
| Queue wait p50 (min) <sub>lower is better</sub> | 0.0 | 0.0 | 0.0 | 0.0 |
| Queue wait p95 (min) <sub>lower is better</sub> | 350.4 | 205.6 | 350.4 | **122.3** |
| Training wait p95 (min) <sub>lower is better</sub> | 432.5 | 534.3 | **423.7** | 713.8 |
| Notebook wait p95 (min) <sub>lower is better</sub> | **0.0** | **0.0** | 0.7 | **0.0** |
| Stranded GPU-hours <sub>lower is better</sub> | 91.1 | **0.0** | **0.0** | **0.0** |
| Preempted work (GPU-h) <sub>lower is better</sub> | **0.0** | 19.4 | **0.0** | 72.1 |
| GPU-h idle while work waited <sub>lower is better</sub> | **1,122.1** | 1,253.7 | 1,184.0 | 1,380.5 |
| Idle GPUs too small for waiting work <sub>lower is better</sub> | 100.0% | 92.5% | **81.4%** | 85.6% |
| Partly used nodes (fragmentation) <sub>lower is better</sub> | 13.2% | 14.1% | 3.9% | **3.7%** |
| Fairness between teams (Jain) <sub>higher is better</sub> | 0.999 | **0.999** | 0.998 | 0.999 |
| Fleet cost until the last job finished <sub>lower is better</sub> | $8,546 | $8,546 | $8,546 | $8,546 |
| Cost per useful GPU-hour <sub>lower is better</sub> | $3.90 | $3.90 | $3.90 | $3.90 |

**Queue wait p95 by team (min)**

| Team | default | kueue | volcano | kai |
|---|---|---|---|---|
| platform | 324.6 | 205.6 | 287.6 | 434.4 |
| product | 396.2 | 357.9 | 416.1 | 157.2 |
| research | 163.3 | 0.0 | 111.9 | 0.0 |

**GPU cost by team**

| Team | default | kueue | volcano | kai |
|---|---|---|---|---|
| platform | $2,192 | $2,043 | $2,084 | $2,102 |
| product | $2,065 | $2,050 | $2,066 | $2,024 |
| research | $777 | $785 | $835 | $734 |

## lab-32: 32 GPUs on 6 nodes, 26 jobs (247 GPU-hours requested)

> Reference simulation of each stack's documented default behaviour, not a run of the schedulers themselves. See [the methodology](../docs/methodology.md).

| Metric | default | kueue | volcano | kai |
|---|---|---|---|---|
| Jobs finished <sub>higher is better</sub> | 26/26 | 26/26 | 26/26 | 26/26 |
| Deadlocked <sub>lower is better</sub> | no | no | no | no |
| Makespan (h) <sub>lower is better</sub> | **11.9** | 12.4 | 12.1 | 13.2 |
| GPU utilisation <sub>higher is better</sub> | **65.7%** | 62.6% | 63.9% | 58.8% |
| Useful utilisation <sub>higher is better</sub> | **65.7%** | 62.6% | 63.9% | 58.8% |
| Queue wait p50 (min) <sub>lower is better</sub> | 0.0 | 0.0 | 0.0 | 0.0 |
| Queue wait p95 (min) <sub>lower is better</sub> | 375.3 | 341.9 | **205.9** | 389.8 |
| Training wait p95 (min) <sub>lower is better</sub> | 403.8 | 403.8 | **229.4** | 451.6 |
| Notebook wait p95 (min) <sub>lower is better</sub> | **0.0** | **0.0** | 30.6 | **0.0** |
| Stranded GPU-hours <sub>lower is better</sub> | 0.0 | 0.0 | 0.0 | 0.0 |
| Preempted work (GPU-h) <sub>lower is better</sub> | 3.2 | 0.6 | **0.0** | 0.6 |
| GPU-h idle while work waited <sub>lower is better</sub> | 90.2 | 88.3 | **53.4** | 113.8 |
| Idle GPUs too small for waiting work <sub>lower is better</sub> | 100.0% | **78.8%** | 87.6% | 84.2% |
| Partly used nodes (fragmentation) <sub>lower is better</sub> | 26.9% | 20.6% | 23.7% | **18.2%** |
| Fairness between teams (Jain) <sub>higher is better</sub> | 0.989 | **0.990** | 0.968 | 0.989 |
| Fleet cost until the last job finished <sub>lower is better</sub> | **$667** | $692 | $677 | $737 |
| Cost per useful GPU-hour <sub>lower is better</sub> | **$2.70** | $2.80 | $2.74 | $2.98 |

**Queue wait p95 by team (min)**

| Team | default | kueue | volcano | kai |
|---|---|---|---|---|
| platform | 0.0 | 0.0 | 0.6 | 0.0 |
| product | 375.3 | 101.6 | 229.4 | 154.8 |
| research | 403.8 | 403.8 | 205.9 | 451.6 |

**GPU cost by team**

| Team | default | kueue | volcano | kai |
|---|---|---|---|---|
| platform | $31 | $31 | $31 | $34 |
| product | $162 | $163 | $137 | $162 |
| research | $319 | $312 | $311 | $312 |

## dc-1024: 1024 GPUs on 256 nodes, 611 jobs (8,810 GPU-hours requested)

> Reference simulation of each stack's documented default behaviour, not a run of the schedulers themselves. See [the methodology](../docs/methodology.md).

| Metric | default | kueue | volcano | kai |
|---|---|---|---|---|
| Jobs finished <sub>higher is better</sub> | 611/611 | 611/611 | 611/611 | 611/611 |
| Deadlocked <sub>lower is better</sub> | no | no | no | no |
| Makespan (h) <sub>lower is better</sub> | 23.5 | 23.5 | 23.5 | 23.5 |
| GPU utilisation <sub>higher is better</sub> | **37.2%** | 36.7% | 36.7% | 36.7% |
| Useful utilisation <sub>higher is better</sub> | 36.7% | 36.7% | 36.7% | **36.7%** |
| Queue wait p50 (min) <sub>lower is better</sub> | 0.0 | 0.0 | 0.0 | 0.0 |
| Queue wait p95 (min) <sub>lower is better</sub> | 168.4 | 123.7 | 183.5 | **88.1** |
| Training wait p95 (min) <sub>lower is better</sub> | 204.0 | 173.7 | 232.5 | **164.9** |
| Notebook wait p95 (min) <sub>lower is better</sub> | **0.0** | **0.0** | 0.7 | **0.0** |
| Stranded GPU-hours <sub>lower is better</sub> | 129.7 | **0.0** | **0.0** | **0.0** |
| Preempted work (GPU-h) <sub>lower is better</sub> | **0.0** | 1.6 | **0.0** | 5.7 |
| GPU-h idle while work waited <sub>lower is better</sub> | 3,277.4 | 3,844.0 | 4,850.3 | **3,252.7** |
| Idle GPUs too small for waiting work <sub>lower is better</sub> | 100.0% | 98.5% | **92.7%** | 98.0% |
| Partly used nodes (fragmentation) <sub>lower is better</sub> | 11.8% | 12.2% | 3.3% | **1.9%** |
| Fairness between teams (Jain) <sub>higher is better</sub> | 1.000 | 1.000 | 1.000 | 1.000 |
| Fleet cost until the last job finished <sub>lower is better</sub> | $40,246 | $40,246 | $40,246 | $40,246 |
| Cost per useful GPU-hour <sub>lower is better</sub> | $4.57 | $4.57 | $4.57 | $4.57 |

**Queue wait p95 by team (min)**

| Team | default | kueue | volcano | kai |
|---|---|---|---|---|
| platform | 166.5 | 136.1 | 184.2 | 102.2 |
| product | 166.7 | 125.8 | 181.9 | 86.0 |
| research | 169.5 | 78.2 | 162.4 | 77.9 |

**GPU cost by team**

| Team | default | kueue | volcano | kai |
|---|---|---|---|---|
| platform | $6,520 | $6,438 | $6,706 | $6,336 |
| product | $5,875 | $5,785 | $6,130 | $5,642 |
| research | $6,039 | $6,020 | $6,363 | $5,841 |
