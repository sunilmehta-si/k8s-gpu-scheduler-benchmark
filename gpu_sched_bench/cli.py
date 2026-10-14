"""`gsb` command line."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gsb", description="Benchmark Kubernetes GPU schedulers on identical AI workload traces.")
    p.add_argument("--version", action="version", version=f"k8s-gpu-scheduler-benchmark {__version__}")
    sub = p.add_subparsers(dest="command")
    fl = sub.add_parser("fleet", help="Inspect a fleet file or render it as kwok nodes.")
    fsub = fl.add_subparsers(dest="fleet_command", required=True)
    r = fsub.add_parser("render", help="Print kwok fake Node manifests for the fleet (kubectl apply -f -).")
    r.add_argument("fleet", help="Fleet YAML file.")
    sm = fsub.add_parser("summary", help="Print pools, node counts and GPU totals.")
    sm.add_argument("fleet", help="Fleet YAML file.")
    tr = sub.add_parser("trace", help="Generate or summarise workload traces.")
    tsub = tr.add_subparsers(dest="trace_command", required=True)
    g = tsub.add_parser("generate", help="Write a seeded synthetic trace (JSONL).")
    g.add_argument("--fleet", required=True, help="Fleet YAML; job sizes are capped to fit it.")
    g.add_argument("--hours", type=float, default=8.0, help="Arrival window in hours (default: 8).")
    g.add_argument("--rate", type=float, default=20.0, help="Mean job arrivals per hour (default: 20).")
    g.add_argument("--seed", type=int, default=7, help="Random seed; the same seed gives the same trace (default: 7).")
    g.add_argument("--max-job-share", type=float, default=0.5,
                   help="Largest job as a share of the fleet's GPUs (default: 0.5).")
    g.add_argument("--output", "-o", help="Write to this file instead of stdout.")
    st = tsub.add_parser("stats", help="Summarise a trace: jobs and GPU-hours by kind and team.")
    st.add_argument("trace", help="Trace JSONL file.")
    st.add_argument("--fleet", help="Also show demand as a share of this fleet's capacity.")
    return p


def _cmd_trace(args: argparse.Namespace) -> int:
    from . import trace as trace_mod
    from .fleet import FleetError, load as load_fleet
    try:
        fleet = load_fleet(args.fleet) if args.fleet else None
        if args.trace_command == "generate":
            from .generate import TraceSpec, generate
            jobs = generate(TraceSpec(hours=args.hours, jobs_per_hour=args.rate, seed=args.seed,
                                      max_gpus_per_node=fleet.max_gpus_per_node,
                                      max_job_gpus=max(1, int(fleet.total_gpus * args.max_job_share))))
            text = trace_mod.dump(jobs)
            if args.output:
                Path(args.output).write_text(text)
                print(f"gsb: wrote {len(jobs)} jobs to {args.output}", file=sys.stderr)
            else:
                print(text, end="")
            return 0
        jobs = trace_mod.load(args.trace)
    except (FleetError, trace_mod.TraceError, OSError) as exc:
        print(f"gsb: {exc}", file=sys.stderr)
        return 2
    print(trace_mod.stats(jobs, fleet))
    return 0


def _cmd_fleet(args: argparse.Namespace) -> int:
    from . import kwok
    from .fleet import FleetError, load
    try:
        fleet = load(args.fleet)
    except (FleetError, OSError) as exc:
        print(f"gsb: {exc}", file=sys.stderr)
        return 2
    if args.fleet_command == "render":
        print(kwok.render(fleet), end="")
        return 0
    for p in fleet.pools:
        print(f"{p.name:<16} {p.count:>4} nodes x {p.gpus_per_node} GPU  {p.gpu_model:<24} ${p.price_per_gpu_hour:.2f}/GPU-hour")
    print(f"\n{fleet.name}: {len(fleet.nodes)} nodes, {fleet.total_gpus} GPUs")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command is None:
        _parser().print_help()
        return 0
    if args.command == "fleet":
        return _cmd_fleet(args)
    if args.command == "trace":
        return _cmd_trace(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
