"""CLI: generate scenarios, run evals.

  exception-triage-agent generate --n 30 --seed 7
  exception-triage-agent eval --backend mock
  exception-triage-agent eval --backend anthropic --model claude-opus-4-8 --repeats 3
"""

from __future__ import annotations

import argparse
import os
import sys

from .evaluate import evaluate, save_results
from .world import generate_scenarios, load_scenarios, save_scenarios

PKG_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_SCENARIOS = os.path.join(PKG_ROOT, "evals", "scenarios.jsonl")
DEFAULT_RESULTS = os.path.join(PKG_ROOT, "results")

# rough per-scenario cost on claude-opus-4-8, from measured smoke runs; used only
# for the pre-run estimate printed before a real-model eval
EST_COST_PER_SCENARIO_USD = 0.15


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="exception-triage-agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate the scenario file (with ground truth)")
    g.add_argument("--n", type=int, default=30)
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--out", default=DEFAULT_SCENARIOS)

    e = sub.add_parser("eval", help="run the eval")
    e.add_argument(
        "--backend",
        choices=["mock", "anthropic", "mistral", "groq", "gemini", "cerebras",
                 "deepseek", "together", "fireworks"],
        default="mock",
        help="mock = deterministic $0 pipeline check; mistral/groq/gemini/cerebras have "
             "free tiers; together/fireworks bill per token (~$0.55 per full eval on 70B)",
    )
    e.add_argument("--model", default=None, help="override the backend's default model")
    e.add_argument("--repeats", type=int, default=3)
    e.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    e.add_argument("--limit", type=int, default=0, help="use only the first N scenarios")
    e.add_argument("--out", default=DEFAULT_RESULTS)

    args = parser.parse_args(argv)

    if args.cmd == "generate":
        scenarios = generate_scenarios(n=args.n, seed=args.seed)
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        save_scenarios(scenarios, args.out)
        print(f"wrote {len(scenarios)} scenarios -> {args.out}")
        return 0

    scenarios = load_scenarios(args.scenarios)
    if args.limit:
        scenarios = scenarios[: args.limit]

    if args.backend == "anthropic":
        est = EST_COST_PER_SCENARIO_USD * len(scenarios) * args.repeats
        print(
            f"real-model eval: {len(scenarios)} scenarios x {args.repeats} repeats on "
            f"{args.model or 'claude-opus-4-8'} — estimated cost ~${est:.2f} "
            "(actual cost is measured and reported)"
        )
    elif args.backend != "mock":
        print(
            f"real-model eval: {len(scenarios)} scenarios x {args.repeats} repeats on "
            f"{args.backend} — token usage is measured and priced at list rate "
            "(free tiers: actual spend $0)"
        )

    agg = evaluate(
        scenarios,
        backend_kind=args.backend,
        model=args.model,
        repeats=args.repeats,
        progress=lambda msg: print(f"  {msg}"),
    )
    resolved_model = args.model or (
        "claude-opus-4-8" if args.backend == "anthropic" else args.backend
    )
    if args.backend not in ("mock", "anthropic") and not args.model:
        from .openai_compat import PROVIDERS

        resolved_model = PROVIDERS[args.backend].default_model
    json_path, md_path = save_results(agg, args.backend, resolved_model, args.out)
    print()
    with open(md_path) as f:
        print(f.read())
    print(f"results -> {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
