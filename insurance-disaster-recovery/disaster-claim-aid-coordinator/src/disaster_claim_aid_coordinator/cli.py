"""Generate and evaluate Disaster Claim and Aid Coordinator scenarios."""

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
    parser = argparse.ArgumentParser(prog="disaster-claim-aid-coordinator")
    commands = parser.add_subparsers(dest="cmd", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--n", type=int, default=32)
    generate.add_argument("--seed", type=int, default=131)
    generate.add_argument("--out", default=DEFAULT_SCENARIOS)
    evaluate_command = commands.add_parser("eval")
    evaluate_command.add_argument(
        "--backend",
        choices=[
            "mock",
            "anthropic",
            "mistral",
            "groq",
            "gemini",
            "cerebras",
            "deepseek",
            "together",
            "fireworks",
            "openrouter",
        ],
        default="mock",
    )
    evaluate_command.add_argument("--model", default=None)
    evaluate_command.add_argument("--repeats", type=int, default=3)
    evaluate_command.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    evaluate_command.add_argument("--limit", type=int, default=0)
    evaluate_command.add_argument("--out", default=DEFAULT_RESULTS)
    args = parser.parse_args(argv)
    if args.cmd == "generate":
        scenarios = generate_scenarios(args.n, args.seed)
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        save_scenarios(scenarios, args.out)
        print(f"wrote {len(scenarios)} scenarios -> {args.out}")
        return 0
    scenarios = load_scenarios(args.scenarios)
    if args.limit:
        scenarios = scenarios[: args.limit]
    aggregate = evaluate(
        scenarios,
        args.backend,
        args.model,
        args.repeats,
        progress=lambda message: print(f"  {message}"),
    )
    resolved = args.model or args.backend
    if args.backend not in ("mock", "anthropic") and not args.model:
        from aau_harness.llm_providers import PROVIDERS

        resolved = PROVIDERS[args.backend].default_model
    try:
        check_results_are_measurements(aggregate)
    except ProviderUnavailable as error:
        print(f"\nREFUSING TO SAVE: {error}", file=sys.stderr)
        return 2
    json_path, markdown_path = save_results(aggregate, args.backend, resolved, args.out)
    print()
    print(open(markdown_path).read())
    print(f"results -> {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
