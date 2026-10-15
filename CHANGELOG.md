# Changelog

## [0.2.0] - 2026-10-15

### Added
- Real-scheduler runs: `gsb cluster run` creates kwok GPU nodes, applies a stack's queues, replays a trace at a
  chosen speed, and collects pod placement and timing into the same results schema (`"mode": "cluster"`).
  `gsb compare` puts a cluster run next to the model.
- A `cluster` workflow that runs the default scheduler, Kueue v0.20.1, Volcano v1.16.0 and KAI Scheduler 0.18.5 on
  kind + kwok v0.8.0 on every push, with install scripts and a self-check that fails runs whose pods did not run
  for their expected time. The first runs and comparisons are committed under `results/cluster/`.
- `gsb sweep` (mean, spread and range over seeded traces, plus cheapest-stack wins), load curves with `--rates`,
  and `gsb ablate`, which switches behaviours on one at a time.
- `gsb chart`: accessible, theme-aware SVG bar charts.
- Priority preemption in the model (cluster-wide for the default scheduler, within a team for Kueue and KAI), and
  jobs that require a GPU model (`gpu_model` in traces, `--pin-training` in the generator).
- A 10-seed sweep of the 256-GPU fleet, charts, a Makefile, a contributing guide and docs/cluster-runs.md.

### Changed
- The README's headline finding: bin-packing, not gang scheduling, drives the savings, and the advantage is about
  19% over ten traces rather than one trace's 23%.
- With priority preemption modelled, the default scheduler no longer finishes the 32-GPU lab trace first.

### Fixed
- kwok's jitter delay is an upper bound, so the `0s` value completed every fake pod instantly; it now equals the
  delay. The runtime check caught this in CI.

[0.2.0]: https://github.com/sunilmehta-si/k8s-gpu-scheduler-benchmark/compare/v0.1.0...v0.2.0

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
