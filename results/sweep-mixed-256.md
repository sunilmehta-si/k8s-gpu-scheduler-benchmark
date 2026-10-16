## mixed-256: 10 seeded traces, 16 jobs/hour for 8 h

> Reference simulation. Each cell is the mean ± standard deviation over 10 traces, with the range in brackets.

| Metric | default | kueue | volcano | kai |
|---|---|---|---|---|
| Makespan (h) <sub>lower is better</sub> | 22.5 ± 9.2 (11.9–46.3) | 21.3 ± 6.5 (11.9–35.6) | 21.3 ± 6.4 (11.9–36.9) | **20.3 ± 6.3 (11.9–35.8)** |
| Useful utilisation <sub>higher is better</sub> | 34.0% ± 8.3% (17.9%–43.4%) | 34.9% ± 6.8% (17.9%–43.2%) | 34.8% ± 7.5% (17.9%–47.1%) | **37.2% ± 8.8% (17.9%–50.3%)** |
| Queue wait p95 (min) <sub>lower is better</sub> | 285 ± 187 (0–572) | 103 ± 106 (0–357) | 172 ± 153 (0–460) | **98 ± 91 (0–281)** |
| Stranded GPU-hours <sub>lower is better</sub> | 135 ± 91 (0–297) | **0 ± 0 (0–0)** | **0 ± 0 (0–0)** | **0 ± 0 (0–0)** |
| Preempted work (GPU-h) <sub>lower is better</sub> | **0 ± 0 (0–0)** | 10 ± 9 (0–27) | **0 ± 0 (0–0)** | 25 ± 22 (0–72) |
| Cost per useful GPU-hour <sub>lower is better</sub> | $5.31 ± $1.64 ($3.86–$9.34) | $5.11 ± $1.49 ($3.90–$9.34) | $5.12 ± $1.53 ($3.56–$9.34) | **$4.92 ± $1.61 ($3.37–$9.34)** |
| Fairness between teams (Jain) <sub>higher is better</sub> | 0.999 ± 0.001 (0.996–1.000) | **1.000 ± 0.001 (0.998–1.000)** | 0.999 ± 0.001 (0.997–1.000) | **1.000 ± 0.001 (0.999–1.000)** |
| Cheapest per useful GPU-hour | 6/10 seeds | 7/10 seeds | 6/10 seeds | 8/10 seeds |
