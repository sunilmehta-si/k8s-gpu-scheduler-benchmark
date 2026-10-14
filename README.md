# k8s-gpu-scheduler-benchmark

**Which Kubernetes GPU scheduler should you run?** This project answers that with numbers. It replays the same AI
workload trace (training jobs, gang jobs, inference services, notebooks) against each scheduling stack on a simulated
GPU fleet, and measures what platform teams argue about: GPU utilisation, fragmentation, queue wait, fairness between
teams, and cost.

Stacks in scope: the default kube-scheduler, [Kueue](https://github.com/kubernetes-sigs/kueue),
[Volcano](https://github.com/volcano-sh/volcano), [KAI Scheduler](https://github.com/kai-scheduler/KAI-Scheduler)
and the newly open-sourced [NVIDIA Run:ai](https://github.com/dsx-ai-factory/run-ai). No GPUs are needed.

> **Status: in development.** The README is updated as each part lands.

## License

[MIT](LICENSE) © Sunil Mehta
