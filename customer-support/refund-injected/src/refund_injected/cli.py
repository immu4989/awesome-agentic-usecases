"""CLI for the injection A/B.

  refund-injected eval --arm none         --backend mistral --repeats 3
  refund-injected eval --arm prompt_guard --backend mistral --repeats 3
  refund-injected eval --arm tool_guard   --backend mistral --repeats 3

Scenarios are built by injecting payloads into the committed refund scenarios, so every
injected case has an exact clean twin already measured next door.
"""

from __future__ import annotations

import argparse
import os
import sys

from refund_resolution_agent.world import load_scenarios

from .evaluate import evaluate, save_results
from .injection import ARMS, PAYLOADS, build_injected

PKG_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
SINGLE = os.path.normpath(os.path.join(PKG_ROOT, "..", "refund-resolution-agent"))
DEFAULT_SCENARIOS = os.path.join(SINGLE, "evals", "scenarios.jsonl")
DEFAULT_RESULTS = os.path.join(PKG_ROOT, "results")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="refund-injected")
    sub = parser.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eval", help="run one defence arm against injected scenarios")
    e.add_argument("--arm", choices=ARMS, default="none")
    e.add_argument("--backend", choices=["mock", "anthropic", "mistral", "groq", "gemini",
                                         "cerebras", "deepseek", "together", "fireworks"],
                   default="mock")
    e.add_argument("--model", default=None)
    e.add_argument("--repeats", type=int, default=3)
    e.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    e.add_argument("--limit", type=int, default=0, help="cap injected scenarios")
    e.add_argument("--out", default=DEFAULT_RESULTS)
    args = parser.parse_args(argv)

    injected = build_injected(load_scenarios(args.scenarios))
    if args.limit:
        injected = injected[: args.limit]
    print(f"{len(injected)} injected scenarios "
          f"({len(PAYLOADS)} payloads x forbidden-action cases), arm={args.arm}")

    agg = evaluate(injected, backend_kind=args.backend, model=args.model,
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
