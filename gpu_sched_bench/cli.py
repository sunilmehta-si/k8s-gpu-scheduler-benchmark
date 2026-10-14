"""`gsb` command line."""
from __future__ import annotations

import argparse
import sys

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
    return p


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
    return 0


if __name__ == "__main__":
    sys.exit(main())
