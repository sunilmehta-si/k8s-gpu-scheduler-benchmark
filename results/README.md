## mixed-256: 256 GPUs on 64 nodes, 131 jobs (2,192 GPU-hours requested)

> Reference simulation of each stack's documented default behaviour, not a run of the schedulers themselves. See [the methodology](../docs/methodology.md).

| Metric | default | kueue | volcano | kai |
|---|---|---|---|---|
| Jobs finished <sub>higher is better</sub> | 131/131 | 131/131 | 131/131 | 131/131 |
| Deadlocked <sub>lower is better</sub> | no | no | no | no |
| Makespan (h) <sub>lower is better</sub> | 26.0 | 26.9 | **19.9** | **19.9** |
| GPU utilisation <sub>higher is better</sub> | 37.7% | 32.0% | 43.0% | **44.4%** |
| Useful utilisation <sub>higher is better</sub> | 32.9% | 32.0% | 43.0% | **44.4%** |
| Queue wait p50 (min) <sub>lower is better</sub> | 0.0 | 0.0 | 0.0 | 0.0 |
| Queue wait p95 (min) <sub>lower is better</sub> | 698.0 | 595.8 | 182.6 | **122.3** |
| Training wait p95 (min) <sub>lower is better</sub> | 817.1 | 1134.9 | **408.7** | 713.8 |
| Notebook wait p95 (min) <sub>lower is better</sub> | 0.0 | 0.0 | 0.0 | 0.0 |
| Stranded GPU-hours <sub>lower is better</sub> | 318.6 | **0.0** | **0.0** | **0.0** |
| Preempted work (GPU-h) <sub>lower is better</sub> | **0.0** | 11.3 | **0.0** | 72.1 |
| GPU-h idle while work waited <sub>lower is better</sub> | 2,580.2 | 3,978.8 | **1,032.2** | 1,380.5 |
| Idle GPUs too small for waiting work <sub>lower is better</sub> | 100.0% | 93.7% | 93.9% | **85.6%** |
| Partly used nodes (fragmentation) <sub>lower is better</sub> | 8.9% | 9.2% | **3.7%** | **3.7%** |
| Fairness between teams (Jain) <sub>higher is better</sub> | 0.998 | **0.999** | 0.999 | 0.999 |
| Fleet cost until the last job finished <sub>lower is better</sub> | $11,160 | $11,514 | **$8,546** | **$8,546** |
| Cost per useful GPU-hour <sub>lower is better</sub> | $5.09 | $5.25 | **$3.90** | **$3.90** |

**Queue wait p95 by team (min)**

| Team | default | kueue | volcano | kai |
|---|---|---|---|---|
| platform | 668.2 | 917.8 | 287.6 | 434.4 |
| product | 775.4 | 633.9 | 183.5 | 157.2 |
| research | 506.7 | 579.0 | 0.0 | 0.0 |

**GPU cost by team**

| Team | default | kueue | volcano | kai |
|---|---|---|---|---|
| platform | $2,630 | $2,203 | $2,010 | $2,102 |
| product | $2,485 | $2,364 | $1,938 | $2,024 |
| research | $1,011 | $932 | $734 | $734 |

## lab-32: 32 GPUs on 6 nodes, 26 jobs (247 GPU-hours requested)

> Reference simulation of each stack's documented default behaviour, not a run of the schedulers themselves. See [the methodology](../docs/methodology.md).

| Metric | default | kueue | volcano | kai |
|---|---|---|---|---|
| Jobs finished <sub>higher is better</sub> | 26/26 | 26/26 | 26/26 | 26/26 |
| Deadlocked <sub>lower is better</sub> | no | no | no | no |
| Makespan (h) <sub>lower is better</sub> | **10.0** | 15.6 | 12.1 | 15.1 |
| GPU utilisation <sub>higher is better</sub> | **77.7%** | 50.8% | 63.9% | 52.2% |
| Useful utilisation <sub>higher is better</sub> | **77.0%** | 50.8% | 63.9% | 52.2% |
| Queue wait p50 (min) <sub>lower is better</sub> | 0.0 | 0.0 | 0.0 | 0.0 |
| Queue wait p95 (min) <sub>lower is better</sub> | 188.4 | 535.6 | **134.2** | 505.6 |
| Training wait p95 (min) <sub>lower is better</sub> | **188.4** | 627.4 | 212.2 | 627.4 |
| Notebook wait p95 (min) <sub>lower is better</sub> | 30.6 | **0.0** | 30.6 | **0.0** |
| Stranded GPU-hours <sub>lower is better</sub> | 2.4 | **0.0** | **0.0** | **0.0** |
| Preempted work (GPU-h) <sub>lower is better</sub> | **0.0** | 6.5 | **0.0** | 4.8 |
| GPU-h idle while work waited <sub>lower is better</sub> | 36.8 | 192.1 | **29.0** | 171.3 |
| Idle GPUs too small for waiting work <sub>lower is better</sub> | 100.0% | **85.8%** | 88.1% | 89.8% |
| Partly used nodes (fragmentation) <sub>lower is better</sub> | 22.4% | 21.9% | 23.0% | **19.1%** |
| Fairness between teams (Jain) <sub>higher is better</sub> | 0.971 | 0.985 | 0.970 | **0.985** |
| Fleet cost until the last job finished <sub>lower is better</sub> | **$562** | $873 | $677 | $845 |
| Cost per useful GPU-hour <sub>lower is better</sub> | **$2.27** | $3.53 | $2.74 | $3.42 |

**Queue wait p95 by team (min)**

| Team | default | kueue | volcano | kai |
|---|---|---|---|---|
| platform | 0.6 | 0.0 | 0.6 | 0.0 |
| product | 258.3 | 159.8 | 134.2 | 202.7 |
| research | 164.9 | 627.4 | 212.2 | 627.4 |

**GPU cost by team**

| Team | default | kueue | volcano | kai |
|---|---|---|---|---|
| platform | $31 | $37 | $31 | $34 |
| product | $143 | $156 | $137 | $159 |
| research | $306 | $345 | $311 | $336 |
