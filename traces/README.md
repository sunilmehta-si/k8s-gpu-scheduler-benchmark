# Sample traces

Generated with `gsb trace generate`; `tests/test_trace_cli.py` regenerates them and fails if they drift.

| File | Fleet | Command | Jobs | Demand |
|---|---|---|---|---|
| `lab-32-8h.jsonl` | `fleets/lab-32.yaml` | `gsb trace generate --fleet fleets/lab-32.yaml --hours 8 --rate 2.5 --seed 7` | 26 | 105% of capacity |
| `mixed-256-8h.jsonl` | `fleets/mixed-256.yaml` | `gsb trace generate --fleet fleets/mixed-256.yaml --hours 8 --rate 16 --seed 7` | 131 | 107% of capacity |
| `lab-32-smoke.jsonl` | `fleets/lab-32.yaml` | `gsb trace generate --fleet fleets/lab-32.yaml --hours 1 --rate 10 --seed 13` | 12 | short; used by the CI cluster runs |

Both load their fleet slightly beyond capacity on purpose: schedulers only differ when there is contention.
