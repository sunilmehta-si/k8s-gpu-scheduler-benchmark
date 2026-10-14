# Changelog

## [0.1.0] - 2026-10-14

### Added
- Fleets of GPU node pools (prices, labels, taints) and their rendering as kwok fake nodes.
- JSONL workload traces and a seeded generator with a training, fine-tune, inference and notebook mix; two sample traces.
- A discrete-event reference simulator: pod-by-pod or gang placement, spread or bin-packing, strict or best-effort
  queueing, team quotas with borrowing and reclaim, checkpoint-aware preemption, stranded-GPU and deadlock detection.
- Presets that model the default kube-scheduler, Kueue, Volcano and KAI Scheduler.
- Metrics: utilisation and useful utilisation, makespan, queue-wait percentiles, stranded and preempted GPU-hours,
  fragmentation, fairness between teams, and cost per team, model and useful GPU-hour.
- `gsb simulate` (deterministic results JSON) and `gsb report` (Markdown comparison).
- `gsb manifests` for the default scheduler, Kueue, Volcano and KAI Scheduler, against kwok nodes.
- Committed results for both sample fleets, checked in CI.

[0.1.0]: https://github.com/sunilmehta-si/k8s-gpu-scheduler-benchmark/releases/tag/v0.1.0
