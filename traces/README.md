# Sample traces

Generated with `gsb trace generate`; `tests/test_trace_cli.py` regenerates them and fails if they drift.

| File | Fleet | Command | Jobs | Demand |
|---|---|---|---|---|
| `lab-32-8h.jsonl` | `fleets/lab-32.yaml` | `gsb trace generate --fleet fleets/lab-32.yaml --hours 8 --rate 2.5 --seed 7` | 26 | 105% of capacity |
| `mixed-256-8h.jsonl` | `fleets/mixed-256.yaml` | `gsb trace generate --fleet fleets/mixed-256.yaml --hours 8 --rate 16 --seed 7` | 131 | 107% of capacity |
| `dc-1024-8h.jsonl` | `fleets/dc-1024.yaml` | `gsb trace generate --fleet fleets/dc-1024.yaml --hours 8 --rate 72 --seed 7` | 611 | 108% of capacity |
| `lab-32-smoke.jsonl` | `fleets/lab-32.yaml` | `gsb trace generate --fleet fleets/lab-32.yaml --hours 1 --rate 10 --seed 13` | 12 | short; used by the CI cluster runs |

The three 8-hour traces load their fleet slightly beyond capacity on purpose: schedulers only differ when there is
contention. The arrival rate scales with the fleet (16 jobs/hour for 256 GPUs, 72 for 1,024) to keep the demand share
comparable.
