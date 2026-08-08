"""CLI: generate scenarios, run evals.

  vendor-payment-review-agent generate --n 30 --seed 71
  vendor-payment-review-agent eval --backend mock
  vendor-payment-review-agent eval --backend openrouter --repeats 3
"""

from __future__ import annotations

import argparse
import os
import sys

from aau_harness import ProviderUnavailable, check_results_are_measurements

from .evaluate import evaluate, save_results
from .world import generate_scenarios, load_scenarios, save_scenarios

PKG_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_SCENARIOS = os.path.join(PKG_ROOT, "evals", "scenarios.jsonl")
DEFAULT_RESULTS = os.path.join(PKG_ROOT, "results")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="vendor-payment-review-agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate the scenario file (with ground truth)")
    g.add_argument("--n", type=int, default=28)
    g.add_argument("--seed", type=int, default=71)
    g.add_argument("--out", default=DEFAULT_SCENARIOS)

    e = sub.add_parser("eval", help="run the eval")
    e.add_argument("--backend", choices=["mock", "anthropic", "mistral", "groq", "gemini",
                                         "cerebras", "deepseek", "together", "fireworks",
                                         "openrouter"], default="mock")
    e.add_argument("--model", default=None)
    e.add_argument("--repeats", type=int, default=3)
    e.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    e.add_argument("--limit", type=int, default=0)
    e.add_argument("--out", default=DEFAULT_RESULTS)

    args = p.parse_args(argv)

    if args.cmd == "generate":
        scenarios = generate_scenarios(n=args.n, seed=args.seed)
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        save_scenarios(scenarios, args.out)
        print(f"wrote {len(scenarios)} scenarios -> {args.out}")
        return 0

    scenarios = load_scenarios(args.scenarios)
    if args.limit:
        scenarios = scenarios[: args.limit]
    agg = evaluate(scenarios, backend_kind=args.backend, model=args.model,
                   repeats=args.repeats, progress=lambda m: print(f"  {m}"))
    resolved = args.model or args.backend
    if args.backend not in ("mock", "anthropic") and not args.model:
        from aau_harness.llm_providers import PROVIDERS
        resolved = PROVIDERS[args.backend].default_model
    try:
        check_results_are_measurements(agg)
    except ProviderUnavailable as exc:
        print(f"\nREFUSING TO SAVE: {exc}", file=sys.stderr)
        return 2
    json_path, md_path = save_results(agg, args.backend, resolved, args.out)
    print()
    print(open(md_path).read())
    print(f"results -> {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
