"""Reference simulator: a discrete-event model of how a scheduling policy places a trace on a fleet.

It models documented scheduling behaviour (gang admission, placement scoring, queueing, quotas,
preemption), not the code of any particular scheduler. Its numbers are a reference for reasoning and
for checking cluster runs, not a substitute for them.
"""
from .engine import JobRecord, Result, simulate
from .policy import Policy

__all__ = ["JobRecord", "Policy", "Result", "simulate"]
