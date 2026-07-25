"""CLI: run one arm against the baseline's committed scenarios.

  exception-triage-drift eval --arm clean          --backend mock
  exception-triage-drift eval --arm drift          --backend mistral --repeats 3
  exception-triage-drift eval --arm prompt_guard   --backend mistral --repeats 3
  exception-triage-drift eval --arm freshness_gate --backend mistral --repeats 3
"""

from __future__ import annotations

import argparse
import os
import sys

from aau_harness import ProviderUnavailable, check_results_are_measurements
from exception_triage_agent.world import load_scenarios

from .drift import ARMS
from .evaluate import evaluate, save_results

PKG_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
BASE = os.path.normpath(os.path.join(PKG_ROOT, "..", "exception-triage-agent"))
DEFAULT_SCENARIOS = os.path.join(BASE, "evals", "scenarios.jsonl")
DEFAULT_RESULTS = os.path.join(PKG_ROOT, "results")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="exception-triage-drift")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eval", help="run one reliability arm")
    e.add_argument("--arm", choices=ARMS, default="drift")
    e.add_argument("--backend", choices=["mock", "anthropic", "mistral", "groq", "gemini",
                                         "cerebras", "deepseek", "together", "fireworks", "openrouter"],
                   default="mock")
    e.add_argument("--model", default=None)
    e.add_argument("--repeats", type=int, default=3)
    e.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    e.add_argument("--limit", type=int, default=0)
    e.add_argument("--out", default=DEFAULT_RESULTS)
    args = p.parse_args(argv)

    scenarios = load_scenarios(args.scenarios)
    if args.limit:
        scenarios = scenarios[: args.limit]
    print(f"{len(scenarios)} scenarios (baseline set), arm={args.arm}")

    agg = evaluate(scenarios, backend_kind=args.backend, model=args.model,
                   repeats=args.repeats, arm=args.arm,
                   progress=lambda m: print(f"  {m}"))
    resolved = args.model or ("claude-opus-4-8" if args.backend == "anthropic" else args.backend)
    if args.backend not in ("mock", "anthropic") and not args.model:
        from aau_harness.llm_providers import PROVIDERS
        resolved = PROVIDERS[args.backend].default_model
    try:
        check_results_are_measurements(agg)
    except ProviderUnavailable as e:
        print(f"\nREFUSING TO SAVE: {e}", file=sys.stderr)
        return 2
    json_path, md_path = save_results(agg, args.backend, resolved, args.out, args.arm)
    print()
    print(open(md_path).read())
    print(f"results -> {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
