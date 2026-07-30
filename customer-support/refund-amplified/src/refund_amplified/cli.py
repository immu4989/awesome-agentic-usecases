"""CLI for the denial-of-wallet A/B.

  refund-amplified eval --arm none        --backend fireworks --repeats 3
  refund-amplified eval --arm prompt_guard --backend fireworks --repeats 3
  refund-amplified eval --arm budget_gate  --backend fireworks --repeats 3

Scenarios are built by amplifying the committed refund scenarios, so every amplified case
has an exact clean twin whose correct answer is already fixed and already measured.
"""

from __future__ import annotations

import argparse
import os
import sys

from refund_resolution_agent.world import load_scenarios

from .amplify import ARCHETYPES, ARMS, build_amplified
from .evaluate import evaluate, save_results

PKG_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
SINGLE = os.path.normpath(os.path.join(PKG_ROOT, "..", "refund-resolution-agent"))
DEFAULT_SCENARIOS = os.path.join(SINGLE, "evals", "scenarios.jsonl")
DEFAULT_RESULTS = os.path.join(PKG_ROOT, "results")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="refund-amplified")
    sub = parser.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eval", help="run one arm against amplified scenarios")
    e.add_argument("--arm", choices=ARMS, default="none")
    e.add_argument("--backend", choices=["mock", "anthropic", "mistral", "groq", "gemini",
                                         "cerebras", "deepseek", "together", "fireworks",
                                         "openrouter"], default="mock")
    e.add_argument("--model", default=None)
    e.add_argument("--repeats", type=int, default=3)
    e.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    e.add_argument("--limit", type=int, default=0, help="cap base scenarios before amplifying")
    e.add_argument("--out", default=DEFAULT_RESULTS)
    args = parser.parse_args(argv)

    base = load_scenarios(args.scenarios)
    if args.limit:
        base = base[: args.limit]
    amplified = build_amplified(base)
    print(f"{len(amplified)} scenarios ({len(base)} base x {len(ARCHETYPES)} archetypes), "
          f"arm={args.arm}")

    agg = evaluate(amplified, backend_kind=args.backend, model=args.model,
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
