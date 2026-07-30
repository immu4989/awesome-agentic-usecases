"""CLI for the escalation A/B.

  incident-remediation-agent eval --arm none    --backend fireworks --repeats 3
  incident-remediation-agent eval --arm general --backend fireworks --repeats 3
  incident-remediation-agent eval --arm named   --backend fireworks --repeats 3
  incident-remediation-agent eval --arm scoped  --backend fireworks --repeats 3
"""

from __future__ import annotations

import argparse
import os
import sys

from .evaluate import evaluate, save_results
from .world import ARMS, generate_incidents, load_incidents, save_incidents

PKG_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_SCENARIOS = os.path.join(PKG_ROOT, "evals", "scenarios.jsonl")
DEFAULT_RESULTS = os.path.join(PKG_ROOT, "results")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="incident-remediation-agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="write the incident set")
    g.add_argument("--n", type=int, default=24, help="incidents (must divide by 6 types)")
    g.add_argument("--seed", type=int, default=61)
    g.add_argument("--out", default=DEFAULT_SCENARIOS)

    e = sub.add_parser("eval", help="run one policy arm")
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
        incs = generate_incidents(n_per_type=max(1, args.n // 6), seed=args.seed)
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        save_incidents(incs, args.out)
        print(f"wrote {len(incs)} scenarios "
              f"({len(incs) // 4} incidents x 4 conditions) -> {args.out}")
        return 0

    incs = (load_incidents(args.scenarios) if os.path.exists(args.scenarios)
            else generate_incidents())
    if args.limit:
        incs = incs[: args.limit]
    print(f"{len(incs)} scenarios, arm={args.arm}")
    agg = evaluate(incs, backend_kind=args.backend, model=args.model,
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
