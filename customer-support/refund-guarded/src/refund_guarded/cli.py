"""CLI for the interventions A/B.

  refund-guarded eval --variant enforced --backend mistral --repeats 3
  refund-guarded eval --variant commit   --backend fireworks --repeats 3

Scenarios come from refund-resolution-agent by design, so every variant is measured
on the same cases as the committed baseline.
"""

from __future__ import annotations

import argparse
import os
import sys

from refund_resolution_agent.world import load_scenarios

from .evaluate import VARIANTS, evaluate, save_results

PKG_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
SINGLE = os.path.normpath(os.path.join(PKG_ROOT, "..", "refund-resolution-agent"))
DEFAULT_SCENARIOS = os.path.join(SINGLE, "evals", "scenarios.jsonl")
DEFAULT_RESULTS = os.path.join(PKG_ROOT, "results")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="refund-guarded")
    sub = parser.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eval", help="run an intervention variant")
    e.add_argument("--variant", choices=VARIANTS, default="enforced")
    e.add_argument("--backend", choices=["mock", "anthropic", "mistral", "groq", "gemini",
                                         "cerebras", "deepseek", "together", "fireworks"],
                   default="mock")
    e.add_argument("--model", default=None)
    e.add_argument("--repeats", type=int, default=3)
    e.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    e.add_argument("--limit", type=int, default=0)
    e.add_argument("--out", default=DEFAULT_RESULTS)
    args = parser.parse_args(argv)

    scenarios = load_scenarios(args.scenarios)
    if args.limit:
        scenarios = scenarios[: args.limit]
    agg = evaluate(scenarios, backend_kind=args.backend, model=args.model,
                   repeats=args.repeats, variant=args.variant,
                   progress=lambda m: print(f"  {m}"))
    resolved = args.model or ("claude-opus-4-8" if args.backend == "anthropic" else args.backend)
    if args.backend not in ("mock", "anthropic") and not args.model:
        from aau_harness.llm_providers import PROVIDERS
        resolved = PROVIDERS[args.backend].default_model
    json_path, md_path = save_results(agg, args.backend, resolved, args.out, args.variant)
    print()
    with open(md_path) as f:
        print(f.read())
    print(f"results -> {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
