"""CLI for the review-record A/B.

  dpa-clause-review-agent eval --arm none        --backend fireworks --repeats 3
  dpa-clause-review-agent eval --arm prompt_guard --backend fireworks --repeats 3
  dpa-clause-review-agent eval --arm record_gate  --backend fireworks --repeats 3
"""

from __future__ import annotations

import argparse
import os
import sys

from .evaluate import evaluate, save_results
from .world import ARMS, generate_dpas, load_dpas, save_dpas

PKG_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_SCENARIOS = os.path.join(PKG_ROOT, "evals", "scenarios.jsonl")
DEFAULT_RESULTS = os.path.join(PKG_ROOT, "results")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="dpa-clause-review-agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="write the request set")
    g.add_argument("--n", type=int, default=28, help="agreements (7 archetypes)")
    g.add_argument("--seed", type=int, default=47)
    g.add_argument("--out", default=DEFAULT_SCENARIOS)

    e = sub.add_parser("eval", help="run one arm")
    e.add_argument("--arm", choices=ARMS, default="none")
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
        dpas = generate_dpas(n_per_archetype=max(1, args.n // 7), seed=args.seed)
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        save_dpas(dpas, args.out)
        print(f"wrote {len(dpas)} dpas -> {args.out}")
        return 0

    dpas = (load_dpas(args.scenarios) if os.path.exists(args.scenarios)
            else generate_dpas())
    if args.limit:
        dpas = dpas[: args.limit]
    print(f"{len(dpas)} dpas, arm={args.arm}")
    agg = evaluate(dpas, backend_kind=args.backend, model=args.model,
                   repeats=args.repeats, arm=args.arm,
                   progress=lambda m: print(f"  {m}"))
    resolved = args.model or ("claude-opus-4-8" if args.backend == "anthropic"
                              else args.backend)
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
