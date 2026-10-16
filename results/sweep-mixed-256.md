## mixed-256: 10 seeded traces, 16 jobs/hour for 8 h

> Reference simulation. Each cell is the mean ± standard deviation over 10 traces, with the range in brackets.

| Metric | default | kueue | volcano | kai |
|---|---|---|---|---|
| Makespan (h) <sub>lower is better</sub> | 22.2 ± 9.4 (11.9–46.9) | 21.0 ± 6.9 (11.9–36.4) | **20.2 ± 6.2 (11.9–35.6)** | 20.3 ± 6.3 (11.9–35.8) |
| Useful utilisation <sub>higher is better</sub> | 34.6% ± 9.0% (17.9%–47.3%) | 35.9% ± 8.1% (17.9%–49.2%) | 37.1% ± 9.5% (17.9%–53.4%) | **37.2% ± 8.8% (17.9%–50.3%)** |
| Queue wait p95 (min) <sub>lower is better</sub> | 280 ± 171 (0–616) | 136 ± 119 (0–382) | 113 ± 100 (0–293) | **98 ± 91 (0–281)** |
| Stranded GPU-hours <sub>lower is better</sub> | 134 ± 87 (0–281) | **0 ± 0 (0–0)** | **0 ± 0 (0–0)** | **0 ± 0 (0–0)** |
| Preempted work (GPU-h) <sub>lower is better</sub> | **0 ± 0 (0–0)** | 16 ± 11 (0–32) | **0 ± 0 (0–0)** | 25 ± 22 (0–72) |
| Cost per useful GPU-hour <sub>lower is better</sub> | $5.26 ± $1.70 ($3.54–$9.34) | $5.03 ± $1.56 ($3.44–$9.34) | **$4.91 ± $1.65 ($3.13–$9.34)** | $4.92 ± $1.61 ($3.37–$9.34) |
| Fairness between teams (Jain) <sub>higher is better</sub> | 0.999 ± 0.001 (0.996–1.000) | 0.999 ± 0.001 (0.998–1.000) | 0.999 ± 0.001 (0.997–1.000) | **1.000 ± 0.001 (0.999–1.000)** |
| Cheapest per useful GPU-hour | 6/10 seeds | 6/10 seeds | 8/10 seeds | 8/10 seeds |
