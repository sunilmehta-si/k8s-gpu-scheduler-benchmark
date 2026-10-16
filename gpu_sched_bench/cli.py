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
    g.add_argument("--pin-training", default="", metavar="GPU_MODEL",
                   help="Make training jobs require this GPU model, e.g. NVIDIA-H100-80GB-HBM3 (default: any).")
    g.add_argument("--output", "-o", help="Write to this file instead of stdout.")
    st = tsub.add_parser("stats", help="Summarise a trace: jobs and GPU-hours by kind and team.")
    st.add_argument("trace", help="Trace JSONL file.")
    st.add_argument("--fleet", help="Also show demand as a share of this fleet's capacity.")
    sim = sub.add_parser("simulate", help="Run every stack's reference model on a fleet and trace; write results JSON.")
    sim.add_argument("--fleet", required=True, help="Fleet YAML file.")
    sim.add_argument("--trace", required=True, help="Trace JSONL file.")
    sim.add_argument("--stacks", default="default,kueue,volcano,kai", help="Comma-separated stacks (default: all).")
    sim.add_argument("--quotas", choices=("equal", "none"), default="equal",
                     help="Team quotas for stacks that support them: an equal share per team, or none (default: equal).")
    sim.add_argument("--placements", action="store_true",
                     help="Also record every replica's node and start/end time, as cluster runs do.")
    sim.add_argument("--output", "-o", help="Write results JSON here instead of stdout.")
    rp = sub.add_parser("report", help="Render one or more results JSON files as a Markdown comparison.")
    rp.add_argument("results", nargs="+", help="Results JSON files from gsb simulate.")
    rp.add_argument("--output", "-o", help="Write Markdown here instead of stdout.")
    mf = sub.add_parser("manifests", help="Print Kubernetes manifests to run a trace on a real scheduler with kwok nodes.")
    mf.add_argument("--stack", required=True, help="Scheduling stack, e.g. default.")
    mf.add_argument("--fleet", required=True, help="Fleet YAML file (quotas are sized from it).")
    mf.add_argument("--trace", required=True, help="Trace JSONL file.")
    mf.add_argument("--part", choices=("all", "setup", "jobs"), default="all",
                    help="setup: namespaces, priorities and queues; jobs: one Job per trace job (default: all).")
    mf.add_argument("--speedup", type=float, default=1.0, help="Divide job durations by this, e.g. 60 (default: 1).")
    mf.add_argument("--quotas", choices=("equal", "none"), default="equal", help="Team quotas (default: equal).")
    ch = sub.add_parser("chart", help="Draw an SVG bar chart of a results file (cost, time to finish, queue wait).")
    ch.add_argument("results", help="Results JSON from gsb simulate or gsb cluster run.")
    ch.add_argument("--output", "-o", required=True, help="SVG file to write.")
    ch.add_argument("--title", default="", help="Chart title (default: fleet, jobs and mode).")
    cm = sub.add_parser("compare", help="Put a simulation next to a cluster run of the same stack and trace.")
    cm.add_argument("model", help="Results JSON from gsb simulate.")
    cm.add_argument("cluster", help="Results JSON from gsb cluster run.")
    tl = sub.add_parser("timeline", help="List which job held which node and when, from a file with placements.")
    tl.add_argument("results", help="Cluster results JSON, or gsb simulate --placements output.")
    tl.add_argument("--stack", required=True, help="Stack to show.")
    ab = sub.add_parser("ablate", help="Switch behaviours on one at a time to see which one a gain comes from.")
    ab.add_argument("--fleet", required=True, help="Fleet YAML file.")
    ab.add_argument("--trace", required=True, help="Trace JSONL file.")
    ab.add_argument("--quotas", choices=("equal", "none"), default="equal", help="Include the quota steps (default: equal).")
    ab.add_argument("--output", "-o", help="Write results JSON here instead of stdout.")
    sw = sub.add_parser("sweep", help="Compare stacks over many seeded traces: mean, stdev, min and max per metric.")
    sw.add_argument("--fleet", required=True, help="Fleet YAML file.")
    sw.add_argument("--seeds", default="1-10", help="Seeds as a range or list, e.g. 1-10 or 1,4,7 (default: 1-10).")
    sw.add_argument("--rate", type=float, default=16.0, help="Mean job arrivals per hour (default: 16).")
    sw.add_argument("--rates", help="Several rates, e.g. 8,12,16,20: writes a load curve instead of one sweep.")
    sw.add_argument("--hours", type=float, default=8.0, help="Arrival window in hours (default: 8).")
    sw.add_argument("--stacks", default="default,kueue,volcano,kai", help="Comma-separated stacks (default: all).")
    sw.add_argument("--quotas", choices=("equal", "none"), default="equal", help="Team quotas (default: equal).")
    sw.add_argument("--output", "-o", help="Write the sweep JSON here instead of stdout.")
    cl = sub.add_parser("cluster", help="Run a trace on a real cluster with kwok GPU nodes.")
    csub = cl.add_subparsers(dest="cluster_command", required=True)
    cr = csub.add_parser("run", help="Create kwok nodes, apply the stack's queues, replay the trace, collect results.")
    cr.add_argument("--stack", required=True, help="The scheduler installed in the cluster: default, kueue, volcano or kai.")
    cr.add_argument("--fleet", required=True, help="Fleet YAML file.")
    cr.add_argument("--trace", required=True, help="Trace JSONL file.")
    cr.add_argument("--speedup", type=float, default=60.0, help="Trace seconds per wall second (default: 60).")
    cr.add_argument("--timeout", type=float, default=1800.0, help="Give up waiting after this many wall seconds (default: 1800).")
    cr.add_argument("--quotas", choices=("equal", "none"), default="equal", help="Team quotas (default: equal).")
    cr.add_argument("--context", help="kubectl context (default: the current one).")
    cr.add_argument("--strict", action="store_true",
                    help="Exit 1 if pods did not run for their expected time (a misconfigured kwok), after writing results.")
    cr.add_argument("--output", "-o", help="Write results JSON here instead of stdout.")
    return p


def parse_seeds(text: str) -> list[int]:
    seeds: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = (int(x) for x in part.split("-", 1))
            if hi < lo:
                raise ValueError(f"bad seed range '{part}'")
            seeds.extend(range(lo, hi + 1))
        elif part:
            seeds.append(int(part))
    if not seeds:
        raise ValueError("no seeds given")
    return sorted(set(seeds))


def _cmd_chart(args: argparse.Namespace) -> int:
    import json

    from .chart import svg
    try:
        data = json.loads(Path(args.results).read_text())
        Path(args.output).write_text(svg(data, args.title))
    except (OSError, ValueError, KeyError) as exc:
        print(f"gsb: {exc}", file=sys.stderr)
        return 2
    return 0


def _cmd_timeline(args: argparse.Namespace) -> int:
    import json

    from .timeline import timeline
    try:
        print(timeline(json.loads(Path(args.results).read_text()), args.stack), end="")
    except (OSError, ValueError, KeyError) as exc:
        print(f"gsb: {exc}", file=sys.stderr)
        return 2
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    import json

    from .compare import compare
    try:
        print(compare(json.loads(Path(args.model).read_text()), json.loads(Path(args.cluster).read_text())), end="")
    except (OSError, ValueError, KeyError) as exc:
        print(f"gsb: {exc}", file=sys.stderr)
        return 2
    return 0


def _cmd_ablate(args: argparse.Namespace) -> int:
    from .ablate import run_ablation
    from .fleet import FleetError, load as load_fleet
    from .results import dumps
    from .trace import TraceError, check_fits, load as load_trace
    try:
        fleet, jobs = load_fleet(args.fleet), load_trace(args.trace)
        check_fits(jobs, fleet.max_gpus_per_node, fleet.max_gpus_by_model)
    except (FleetError, TraceError, OSError) as exc:
        print(f"gsb: {exc}", file=sys.stderr)
        return 2
    text = dumps(run_ablation(fleet, jobs, args.quotas, trace_name=Path(args.trace).name))
    if args.output:
        Path(args.output).write_text(text)
    else:
        print(text, end="")
    return 0


def _cmd_sweep(args: argparse.Namespace) -> int:
    import json

    from .fleet import FleetError, load as load_fleet
    from .presets import STACKS
    from .sweep import run_sweep
    stacks = [s.strip() for s in args.stacks.split(",") if s.strip()]
    try:
        unknown = [s for s in stacks if s not in STACKS]
        if unknown:
            raise ValueError(f"unknown stack(s) {', '.join(unknown)}; choose from {', '.join(STACKS)}")
        if args.rates:
            from .sweep import load_curve
            rates = [float(r) for r in args.rates.split(",") if r.strip()]
            doc = load_curve(load_fleet(args.fleet), stacks, parse_seeds(args.seeds), rates, args.hours, args.quotas)
        else:
            doc = run_sweep(load_fleet(args.fleet), stacks, parse_seeds(args.seeds), args.rate, args.hours, args.quotas)
    except (FleetError, OSError, ValueError) as exc:
        print(f"gsb: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(doc, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text)
        print(f"gsb: wrote a {len(doc['seeds'])}-seed {'load curve' if args.rates else 'sweep'} to {args.output}",
              file=sys.stderr)
    else:
        print(text, end="")
    return 0


def _cmd_cluster(args: argparse.Namespace) -> int:
    from .cluster.kube import KubeError, Kubectl
    from .cluster.run import run_cluster
    from .fleet import FleetError, load as load_fleet
    from .presets import equal_quotas
    from .results import dumps
    from .trace import TraceError, check_fits, load as load_trace
    try:
        fleet, jobs = load_fleet(args.fleet), load_trace(args.trace)
        check_fits(jobs, fleet.max_gpus_per_node, fleet.max_gpus_by_model)
        shares = equal_quotas([j.team for j in jobs]) if args.quotas == "equal" else {}
        doc = run_cluster(Kubectl(context=args.context), fleet, jobs, args.stack, shares, args.speedup,
                          timeout_s=args.timeout, trace_name=Path(args.trace).name,
                          log=lambda m: print(f"gsb: {m}", file=sys.stderr))
    except (FleetError, TraceError, KubeError, OSError, ValueError) as exc:
        print(f"gsb: {exc}", file=sys.stderr)
        return 2
    if args.output:
        Path(args.output).write_text(dumps(doc))
    else:
        print(dumps(doc), end="")
    if args.strict and not doc["runtime_check"]["ok"]:
        print(f"gsb: runtime check failed: {doc['runtime_check']['reason']}", file=sys.stderr)
        return 1
    return 0


def _cmd_manifests(args: argparse.Namespace) -> int:
    import yaml

    from . import manifests
    from .fleet import FleetError, load as load_fleet
    from .presets import equal_quotas
    from .trace import TraceError, load as load_trace
    try:
        fleet, jobs = load_fleet(args.fleet), load_trace(args.trace)
        shares = equal_quotas([j.team for j in jobs]) if args.quotas == "equal" else {}
        docs = manifests.render(args.stack, fleet, jobs, shares, args.speedup, args.part)
    except (FleetError, TraceError, OSError, ValueError) as exc:
        print(f"gsb: {exc}", file=sys.stderr)
        return 2
    print(yaml.safe_dump_all(docs, sort_keys=False), end="")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    import json

    from .report import to_markdown
    try:
        parts = [to_markdown(json.loads(Path(f).read_text())) for f in args.results]
    except (OSError, ValueError, KeyError) as exc:
        print(f"gsb: cannot read results: {exc}", file=sys.stderr)
        return 2
    text = "\n".join(parts)
    if args.output:
        Path(args.output).write_text(text)
    else:
        print(text, end="")
    return 0


def _cmd_simulate(args: argparse.Namespace) -> int:
    from . import results
    from .fleet import FleetError, load as load_fleet
    from .presets import STACKS
    from .trace import TraceError, check_fits, load as load_trace
    stacks = [s.strip() for s in args.stacks.split(",") if s.strip()]
    unknown = [s for s in stacks if s not in STACKS]
    if unknown:
        print(f"gsb: unknown stack(s) {', '.join(unknown)}; choose from {', '.join(STACKS)}", file=sys.stderr)
        return 2
    try:
        fleet = load_fleet(args.fleet)
        jobs = load_trace(args.trace)
        check_fits(jobs, fleet.max_gpus_per_node, fleet.max_gpus_by_model)
    except (FleetError, TraceError, OSError) as exc:
        print(f"gsb: {exc}", file=sys.stderr)
        return 2
    text = results.dumps(results.run(fleet, jobs, stacks, args.quotas, trace_name=Path(args.trace).name,
                                            with_placements=args.placements))
    if args.output:
        Path(args.output).write_text(text)
        print(f"gsb: wrote results for {', '.join(stacks)} to {args.output}", file=sys.stderr)
    else:
        print(text, end="")
    return 0


def _cmd_trace(args: argparse.Namespace) -> int:
    from . import trace as trace_mod
    from .fleet import FleetError, load as load_fleet
    try:
        fleet = load_fleet(args.fleet) if args.fleet else None
        if args.trace_command == "generate":
            from .generate import TraceSpec, generate
            jobs = generate(TraceSpec(hours=args.hours, jobs_per_hour=args.rate, seed=args.seed,
                                      max_gpus_per_node=fleet.max_gpus_per_node,
                                      max_job_gpus=max(1, int(fleet.total_gpus * args.max_job_share)),
                                      pin_training=args.pin_training))
            if args.pin_training and args.pin_training not in fleet.max_gpus_by_model:
                raise trace_mod.TraceError(f"the fleet has no {args.pin_training} nodes")
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
    if args.command == "simulate":
        return _cmd_simulate(args)
    if args.command == "report":
        return _cmd_report(args)
    if args.command == "manifests":
        return _cmd_manifests(args)
    if args.command == "cluster":
        return _cmd_cluster(args)
    if args.command == "sweep":
        return _cmd_sweep(args)
    if args.command == "ablate":
        return _cmd_ablate(args)
    if args.command == "compare":
        return _cmd_compare(args)
    if args.command == "timeline":
        return _cmd_timeline(args)
    if args.command == "chart":
        return _cmd_chart(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
