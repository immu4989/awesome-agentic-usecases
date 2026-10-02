"""Describe synthetic campaign workload without executing an adapter."""

import math
from collections import Counter

from .agent_bom import AgentBomError, digest, generate_conformance_suite


def plan_authority(bom: dict, runs: int = 1, timeout: float = 10.0,
                   max_invocations: int | None = None) -> dict:
    if type(runs) is not int or not 1 <= runs <= 10:
        raise AgentBomError("workload planning requires 1 to 10 runs")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 300:
        raise AgentBomError("adapter timeout must be finite and greater than 0, up to 300 seconds")
    if max_invocations is not None and (type(max_invocations) is not int or max_invocations < 1):
        raise AgentBomError("max invocations must be a positive integer")
    suite = generate_conformance_suite(bom)
    cases = suite["cases"]
    calls = len(cases) * runs
    within = max_invocations is None or calls <= max_invocations
    return {
        "plan_version": "aau-authority-workload/1.0",
        "bom_sha256": digest(bom), "suite_sha256": digest(suite),
        "runs": runs, "cases_per_run": len(cases), "planned_adapter_invocations": calls,
        "clean_cases_per_run": sum(case["clean_twin"] for case in cases),
        "violation_cases_per_run": sum(not case["clean_twin"] for case in cases),
        "cases_by_shape": dict(sorted(Counter(case["shape"] for case in cases).items())),
        "per_case_timeout_seconds": timeout,
        "summed_case_timeout_allowance_seconds": calls * timeout,
        "max_invocations": max_invocations,
        "status": "within_budget" if within else "over_budget",
        "boundary": "Planning only; no adapter executed. Invocation counts do not bound internal API calls, side effects, costs, or wall-clock duration. Timeout sums exclude overhead and descendant processes.",
    }
