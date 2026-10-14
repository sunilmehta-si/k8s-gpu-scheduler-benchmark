"""`gsb` command line."""
from __future__ import annotations

import argparse
import sys

from . import __version__


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gsb", description="Benchmark Kubernetes GPU schedulers on identical AI workload traces.")
    p.add_argument("--version", action="version", version=f"k8s-gpu-scheduler-benchmark {__version__}")
    p.add_subparsers(dest="command")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command is None:
        _parser().print_help()
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
