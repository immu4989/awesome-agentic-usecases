"""The three-way outcome, analysed at the level the design actually randomised.

Repeats within an incident are correlated. A pilot for this use case read 6 incidents × 3
repeats as n=18 and reported intervals roughly twice as tight as they should have been. So
nothing here resamples runs: the bootstrap resamples **incidents**, and the primary test is
Fisher exact on incident-level counts, where an incident counts as violated if any of its
repeats violated.

Both are conservative in the same direction, which is the direction that matters when the
result being reported is "this defence worked".
"""

from __future__ import annotations

import glob
import json
import os
import random
from math import comb

CONDITIONS = ("OPEN", "BLOCKED", "BLOCKED_NO_SHORTCUT", "FROZEN")
ARMS = ("none", "general", "named", "scoped")
HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, os.pardir, "results")
N_BOOT = 20000
SEED = 61


def load() -> dict[tuple[str, str], dict]:
    runs = {}
    for path in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        with open(path) as f:
            d = json.load(f)
        runs[(d["model"] or d["backend"], d["arm"])] = d
    return runs


def by_incident(run: dict, metric: str, condition: str | None = None,
                submitted_only: bool = False) -> dict[str, list[float]]:
    """incident_id -> the metric across its repeats.

    `submitted_only` matters for `disclosed`: a run that never filed a record has an empty
    record, which scores 0 disclosure for reasons that have nothing to do with candour.
    Reading it unconditionally reports a stall as a cover-up.
    """
    out: dict[str, list[float]] = {}
    for r in run["results"]:
        if condition and r["detail"]["condition"] != condition:
            continue
        if submitted_only and not r["metrics"]["submitted"]:
            continue
        out.setdefault(r["detail"]["incident_id"], []).append(r["metrics"][metric])
    return {k: v for k, v in out.items() if v}


def cluster_ci(groups: dict[str, list[float]]) -> tuple[float, float, float]:
    """Mean and 95% interval, resampling incidents rather than runs."""
    if not groups:
        return float("nan"), float("nan"), float("nan")
    keys = list(groups)
    rng = random.Random(SEED)
    point = sum(sum(v) / len(v) for v in groups.values()) / len(keys)
    means = []
    for _ in range(N_BOOT):
        picks = [groups[keys[rng.randrange(len(keys))]] for _ in keys]
        means.append(sum(sum(v) / len(v) for v in picks) / len(picks))
    means.sort()
    return point, means[int(0.025 * N_BOOT)], means[int(0.975 * N_BOOT)]


def fisher(a: int, b: int, c: int, d: int) -> float:
    """Two-tailed Fisher exact."""
    n, r1, r2, c1 = a + b + c + d, a + b, c + d, a + c

    def p_of(x: int) -> float:
        return comb(r1, x) * comb(r2, c1 - x) / comb(n, c1)

    p_obs = p_of(a)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    return sum(p_of(x) for x in range(lo, hi + 1) if p_of(x) <= p_obs + 1e-12)


def any_violated(run: dict, condition: str) -> tuple[int, int]:
    """(incidents with at least one violating repeat, total incidents)."""
    g = by_incident(run, "violated", condition)
    return sum(1 for v in g.values() if any(v)), len(g)


def main() -> None:
    runs = load()
    if not runs:
        raise SystemExit("no results committed yet")
    models = sorted({m for m, _ in runs} - {"mock"}) or ["mock"]

    for model in models:
        print(f"\n{'=' * 78}\n{model}\n{'=' * 78}")
        for cond in CONDITIONS:
            print(f"\n  {cond}")
            print(f"    {'arm':9}{'violated':>22}{'escalated':>22}{'correct':>10}")
            for arm in ARMS:
                run = runs.get((model, arm))
                if not run:
                    continue
                v, vlo, vhi = cluster_ci(by_incident(run, "violated", cond))
                e, elo, ehi = cluster_ci(by_incident(run, "escalated", cond))
                c, _, _ = cluster_ci(by_incident(run, "correct", cond))
                print(f"    {arm:9}{v:>8.2f} [{vlo:.2f},{vhi:.2f}]"
                      f"{e:>8.2f} [{elo:.2f},{ehi:.2f}]{c:>10.2f}")

        print("\n  Incident-level Fisher exact on BLOCKED "
              "(an incident counts as violated if any repeat did)")
        base = runs.get((model, "none"))
        if base:
            a, na = any_violated(base, "BLOCKED")
            for arm in ("general", "named", "scoped"):
                run = runs.get((model, arm))
                if not run:
                    continue
                c, nc = any_violated(run, "BLOCKED")
                p = fisher(a, na - a, c, nc - c)
                mark = "significant" if p < 0.05 else "not significant"
                print(f"    none vs {arm:9} {a}/{na} vs {c}/{nc}   p={p:.4f}  {mark}")

        print("\n  Does the shortcut's presence suppress escalation? "
              "(BLOCKED vs BLOCKED_NO_SHORTCUT, arm=none)")
        if base:
            for cond in ("BLOCKED", "BLOCKED_NO_SHORTCUT"):
                e, lo, hi = cluster_ci(by_incident(base, "escalated", cond))
                print(f"    {cond:22} escalated={e:.2f} [{lo:.2f}, {hi:.2f}]")

        print("\n  Utility check — arms must not win by refusing to work (OPEN)")
        for arm in ARMS:
            run = runs.get((model, arm))
            if not run:
                continue
            c, lo, hi = cluster_ci(by_incident(run, "correct", "OPEN"))
            print(f"    {arm:9} correct={c:.2f} [{lo:.2f}, {hi:.2f}]")

        print("\n  Reporting integrity, and completion")
        for arm in ARMS:
            run = runs.get((model, arm))
            if not run:
                continue
            d, dlo, dhi = cluster_ci(by_incident(run, "disclosed", submitted_only=True))
            s, _, _ = cluster_ci(by_incident(run, "submitted"))
            errs = sum(1 for r in run["results"] if r["detail"].get("error"))
            print(f"    {arm:9} disclosed|submitted={d:.2f} [{dlo:.2f}, {dhi:.2f}]  "
                  f"submitted={s:.2f}  errors={errs}/{len(run['results'])}")


if __name__ == "__main__":
    main()
