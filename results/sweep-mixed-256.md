## mixed-256: 10 seeded traces, 16 jobs/hour for 8 h

> Reference simulation. Each cell is the mean ± standard deviation over 10 traces, with the range in brackets.

| Metric | default | kueue | volcano | kai |
|---|---|---|---|---|
| Makespan (h) <sub>lower is better</sub> | 26.2 ± 11.3 (14.7–54.6) | 24.2 ± 7.0 (12.8–37.0) | **20.2 ± 6.2 (11.9–35.6)** | 20.3 ± 6.3 (11.9–35.8) |
| Useful utilisation <sub>higher is better</sub> | 29.4% ± 7.0% (17.9%–39.4%) | 30.3% ± 4.7% (17.9%–34.6%) | 37.1% ± 9.5% (17.9%–53.4%) | **37.2% ± 8.8% (17.9%–50.3%)** |
| Queue wait p95 (min) <sub>lower is better</sub> | 598 ± 268 (176–1080) | 478 ± 293 (14–1018) | 113 ± 100 (0–293) | **98 ± 91 (0–281)** |
| Stranded GPU-hours <sub>lower is better</sub> | 270 ± 112 (71–431) | **0 ± 0 (0–0)** | **0 ± 0 (0–0)** | **0 ± 0 (0–0)** |
| Preempted work (GPU-h) <sub>lower is better</sub> | **0 ± 0 (0–0)** | 5 ± 7 (0–20) | **0 ± 0 (0–0)** | 25 ± 22 (0–72) |
| Cost per useful GPU-hour <sub>lower is better</sub> | $6.08 ± $1.64 ($4.25–$9.34) | $5.73 ± $1.26 ($4.84–$9.34) | **$4.91 ± $1.65 ($3.13–$9.34)** | $4.92 ± $1.61 ($3.37–$9.34) |
| Fairness between teams (Jain) <sub>higher is better</sub> | 0.998 ± 0.003 (0.990–1.000) | 0.999 ± 0.002 (0.992–1.000) | 0.999 ± 0.001 (0.997–1.000) | **1.000 ± 0.001 (0.999–1.000)** |
| Cheapest per useful GPU-hour | 2/10 seeds | 1/10 seeds | 8/10 seeds | 8/10 seeds |
