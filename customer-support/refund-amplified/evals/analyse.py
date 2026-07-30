"""Per-archetype bill, read against each model's own clean twin.

Amplification is always relative. Models differ by an order of magnitude in price, so an
absolute dollar figure says more about the provider's rate card than about the attack. What
transfers is the multiple: how much more did the same task cost once a customer-controlled
field got bigger.

The call and turn columns sit next to the cost column on purpose. `BLOAT` should move the
bill while leaving both of them exactly where they were — that is the claim that a
call-counting monitor cannot see this, and it is checkable right here.
"""

from __future__ import annotations

import glob
import json
import os

ARCHETYPES = ("CLEAN_TWIN", "FANOUT", "BLOAT", "NEUTRAL_BLOAT", "LEGIT_COMPLEX")
ARMS = ("none", "prompt_guard", "budget_gate", "both")
HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, os.pardir, "results")


def load() -> dict[tuple[str, str], dict]:
    runs = {}
    for path in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        with open(path) as f:
            d = json.load(f)
        runs[(d["model"] or d["backend"], d["arm"])] = d
    return runs


def group(run: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in run["results"]:
        out.setdefault(r["detail"]["amp_archetype"], []).append(r["metrics"])
    return out


def mean(rows: list[dict], key: str) -> float:
    return sum(r[key] for r in rows) / len(rows) if rows else float("nan")


def main() -> None:
    runs = load()
    if not runs:
        raise SystemExit("no results committed yet")

    for (model, arm), run in sorted(runs.items()):
        g = group(run)
        base_cost = mean(g.get("CLEAN_TWIN", []), "cost_usd")
        base_tok = mean(g.get("CLEAN_TWIN", []), "input_tokens")

        print(f"\n{model}  arm={arm}")
        print(f"  {'archetype':16}{'$/scenario':>12}{'x cost':>8}{'in_tok':>9}{'x tok':>7}"
              f"{'calls':>7}{'turns':>7}{'correct':>9}{'safe':>6}{'sub':>6}")
        for arch in ARCHETYPES:
            rows = g.get(arch, [])
            if not rows:
                continue
            c, t = mean(rows, "cost_usd"), mean(rows, "input_tokens")
            xc = c / base_cost if base_cost else float("nan")
            xt = t / base_tok if base_tok else float("nan")
            print(f"  {arch:16}{c:>12.5f}{xc:>7.2f}x{t:>9.0f}{xt:>6.2f}x"
                  f"{mean(rows, 'n_tool_calls'):>7.1f}{mean(rows, 'n_turns'):>7.1f}"
                  f"{mean(rows, 'correct'):>9.2f}{mean(rows, 'safe'):>6.2f}"
                  f"{mean(rows, 'submitted'):>6.2f}")

        errs = [r for r in run["results"] if r["detail"].get("error")]
        if errs:
            print(f"  ! {len(errs)}/{len(run['results'])} runs errored")

    print("\n\nWhat each defence actually covers (x cost vs that arm's own clean twin)")
    models = sorted({m for m, _ in runs} - {"mock"})
    for model in models:
        print(f"\n  {model}")
        print(f"    {'arm':14}{'FANOUT':>10}{'BLOAT':>10}{'LEGIT':>10}{'correct':>10}")
        for arm in ARMS:
            run = runs.get((model, arm))
            if not run:
                continue
            g = group(run)
            base = mean(g.get("CLEAN_TWIN", []), "cost_usd")
            cells = []
            for arch in ("FANOUT", "BLOAT", "LEGIT_COMPLEX"):
                rows = g.get(arch, [])
                cells.append(mean(rows, "cost_usd") / base if base and rows else float("nan"))
            allrows = [m for rows in g.values() for m in rows]
            print(f"    {arm:14}{cells[0]:>9.2f}x{cells[1]:>9.2f}x{cells[2]:>9.2f}x"
                  f"{mean(allrows, 'correct'):>10.2f}")


if __name__ == "__main__":
    main()
