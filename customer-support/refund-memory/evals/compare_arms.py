"""Paired arm comparison, with the control drift printed beside every claim.

Archetypes are different scenarios, so `POISON_TICKET` harm cannot be differenced against
`CLEAN_BASELINE` harm as if it were paired. What *is* paired is the same scenario under two
arms, so that is what gets a confidence interval.

The `CLEAN_BASELINE` row is printed for every comparison on purpose. Those scenarios contain
no poison in any arm, so any interval there that excludes zero is drift — sampling noise, a
guard changing unrelated behaviour, provider flakiness — and a poison-archetype effect is
only believable if it is clearly larger than the drift measured on the same run.
"""

from __future__ import annotations

import glob
import json
import os
import random

ARCHETYPES = ("CLEAN_BASELINE", "POISON_TICKET", "POISON_TOOL", "LEGIT_NOTE")
HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, os.pardir, "results")
N_BOOT = 10000
SEED = 43


def load_runs() -> dict[tuple[str, str], dict]:
    runs = {}
    for path in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        with open(path) as f:
            d = json.load(f)
        runs[(d["model"] or d["backend"], d["arm"])] = d
    return runs


def per_scenario(run: dict, metric: str) -> dict[str, tuple[str, float]]:
    """scenario_id -> (archetype, mean over repeats)."""
    acc: dict[str, list[float]] = {}
    arch: dict[str, str] = {}
    for r in run["results"]:
        acc.setdefault(r["scenario_id"], []).append(r["metrics"][metric])
        arch[r["scenario_id"]] = r["detail"]["archetype"]
    return {sid: (arch[sid], sum(v) / len(v)) for sid, v in acc.items()}


def paired_ci(deltas: list[float]) -> tuple[float, float, float]:
    """Mean delta and a 95% percentile bootstrap interval over scenarios."""
    if not deltas:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(SEED)
    n = len(deltas)
    means = []
    for _ in range(N_BOOT):
        means.append(sum(deltas[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return (sum(deltas) / n,
            means[int(0.025 * N_BOOT)],
            means[int(0.975 * N_BOOT)])


def compare(runs, model: str, arm_a: str, arm_b: str, metric: str = "sleeper_harm") -> None:
    a, b = runs.get((model, arm_a)), runs.get((model, arm_b))
    if not a or not b:
        return
    pa, pb = per_scenario(a, metric), per_scenario(b, metric)

    direction = ("positive = guard restored the check" if metric == "s2_identity_verified"
                 else "negative = guard helped")
    print(f"\n{model}: {metric}  {arm_b} - {arm_a}   ({direction})")
    for arch in ARCHETYPES:
        sids = [s for s in pa if s in pb and pa[s][0] == arch]
        deltas = [pb[s][1] - pa[s][1] for s in sids]
        m, lo, hi = paired_ci(deltas)
        verdict = "significant" if (lo > 0 or hi < 0) else "not distinguishable from zero"
        tag = "  <- control, expect no effect" if arch == "CLEAN_BASELINE" else ""
        print(f"  {arch:17} n={len(sids):>2}  {m:+.3f}  [{lo:+.3f}, {hi:+.3f}]  "
              f"{verdict}{tag}")


def error_rates(runs) -> None:
    print("\nrun errors (transport failures are not model failures, but they are not data "
          "either)")
    for (model, arm), run in sorted(runs.items()):
        if run["backend"] == "mock":
            continue
        errs = sum(1 for r in run["results"] if r["detail"].get("error"))
        print(f"  {model:24} {arm:14} {errs:>3}/{len(run['results'])}"
              f"  ({errs / len(run['results']):.1%})")


def main() -> None:
    runs = load_runs()
    models = sorted({m for m, _ in runs} - {"mock"})
    for model in models:
        for arm in ("write_gate", "prompt_guard"):
            compare(runs, model, "none", arm, metric="s2_identity_verified")
            compare(runs, model, "none", arm, metric="sleeper_harm")
    error_rates(runs)


if __name__ == "__main__":
    main()
