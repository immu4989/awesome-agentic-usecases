"""CLI: generate scenarios, run one defence arm.

  trifecta-exfil-agent generate --n 30 --seed 37
  trifecta-exfil-agent eval --arm none        --backend mistral --repeats 3
  trifecta-exfil-agent eval --arm prompt_guard --backend mistral --repeats 3
  trifecta-exfil-agent eval --arm taint_gate   --backend mistral --repeats 3
"""

from __future__ import annotations

import argparse
import os
import sys

from .evaluate import evaluate, save_results
from .world import ARMS, generate_scenarios, load_scenarios, save_scenarios

PKG_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_SCENARIOS = os.path.join(PKG_ROOT, "evals", "scenarios.jsonl")
DEFAULT_RESULTS = os.path.join(PKG_ROOT, "results")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="trifecta-exfil-agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate the scenario file (with ground truth)")
    g.add_argument("--n", type=int, default=30)
    g.add_argument("--seed", type=int, default=37)
    g.add_argument("--out", default=DEFAULT_SCENARIOS)

    e = sub.add_parser("eval", help="run one defence arm against the scenarios")
    e.add_argument("--arm", choices=ARMS, default="none")
    e.add_argument("--backend",
                   choices=["mock", "anthropic", "mistral", "groq", "gemini", "cerebras",
                            "deepseek", "together", "fireworks"],
                   default="mock")
    e.add_argument("--model", default=None)
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
    print(f"{len(scenarios)} scenarios, arm={args.arm}")
    if args.backend not in ("mock", "anthropic"):
        print(f"real-model eval on {args.backend} — token usage measured, free tiers spend $0")

    agg = evaluate(scenarios, backend_kind=args.backend, model=args.model,
                   repeats=args.repeats, arm=args.arm,
                   progress=lambda m: print(f"  {m}"))
    resolved = args.model or ("claude-opus-4-8" if args.backend == "anthropic" else args.backend)
    if args.backend not in ("mock", "anthropic") and not args.model:
        from aau_harness.llm_providers import PROVIDERS
        resolved = PROVIDERS[args.backend].default_model
    json_path, md_path = save_results(agg, args.backend, resolved, args.out, args.arm)
    print()
    with open(md_path) as f:
        print(f.read())
    print(f"results -> {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
