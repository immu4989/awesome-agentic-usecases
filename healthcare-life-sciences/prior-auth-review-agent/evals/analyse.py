"""The record against the review, clustered on the request.

Repeats of one request are correlated. Every interval here resamples requests, never runs,
and the primary test is Fisher exact on request-level counts — a pilot elsewhere in this repo
read 18 clustered runs as 18 independent ones and halved its own intervals.

Two denominators matter and are kept apart. `misrouted_as_administrative` is reported over
the requests where routing to a clinician was the correct action, because that is the only
population where misrouting is possible; averaging it over every request would divide by
cases that could never have failed.
"""

from __future__ import annotations

import glob
import json
import os
import random
from math import comb

ARMS = ("none", "prompt_guard", "record_gate")
HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, os.pardir, "results")
N_BOOT = 20000
SEED = 41
ROUTE = "route_to_clinical_review"


def load() -> dict[tuple[str, str], dict]:
    runs = {}
    for path in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        with open(path) as f:
            d = json.load(f)
        runs[(d["model"] or d["backend"], d["arm"])] = d
    return runs


def by_request(run: dict, metric: str, only=None) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for r in run["results"]:
        if only and not only(r["detail"]):
            continue
        if metric not in r["metrics"]:
            continue
        out.setdefault(r["detail"]["request_id"], []).append(r["metrics"][metric])
    return {k: v for k, v in out.items() if v}


def cluster_ci(groups: dict[str, list[float]]) -> tuple[float, float, float]:
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
    n, r1, r2, c1 = a + b + c + d, a + b, c + d, a + c

    def p_of(x: int) -> float:
        return comb(r1, x) * comb(r2, c1 - x) / comb(n, c1)

    p_obs = p_of(a)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    return sum(p_of(x) for x in range(lo, hi + 1) if p_of(x) <= p_obs + 1e-12)


def any_positive(run: dict, metric: str, only=None) -> tuple[int, int]:
    g = by_request(run, metric, only)
    return sum(1 for v in g.values() if any(v)), len(g)


def route_only(detail: dict) -> bool:
    """Misrouting is only possible where routing to a clinician was the correct action."""
    return detail["gold"] == ROUTE


def main() -> None:
    runs = load()
    if not runs:
        raise SystemExit("no results committed yet")
    models = sorted({m for m, _ in runs} - {"mock"})
    for model in models:
        print(f"\n{'=' * 76}\n{model}\n{'=' * 76}")
        print(f"  {'arm':13}{'correct':>18}{'misrouted | ROUTE':>26}{'phantom criteria':>20}")
        for arm in ARMS:
            run = runs.get((model, arm))
            if not run:
                continue
            c, clo, chi = cluster_ci(by_request(run, "correct"))
            m, mlo, mhi = cluster_ci(
                by_request(run, "misrouted_as_administrative", route_only))
            p, _, _ = cluster_ci(by_request(run, "phantom_criteria"))
            print(f"  {arm:13}{c:>8.2f} [{clo:.2f},{chi:.2f}]"
                  f"{m:>16.2f} [{mlo:.2f},{mhi:.2f}]{p:>20.2f}")

        base = runs.get((model, "none"))
        if base:
            print("\n  Request-level Fisher exact vs `none`, misrouting on ROUTE cases")
            a, na = any_positive(base, "misrouted_as_administrative", route_only)
            for arm in ("prompt_guard", "record_gate"):
                run = runs.get((model, arm))
                if not run:
                    continue
                c, nc = any_positive(run, "misrouted_as_administrative", route_only)
                p = fisher(a, na - a, c, nc - c)
                mark = "significant" if p < 0.05 else "not significant"
                print(f"    none vs {arm:13} {a}/{na} vs {c}/{nc}   p={p:.4f}  {mark}")

        print("\n  Fabrication, and whether the gate had anything to catch")
        for arm in ARMS:
            run = runs.get((model, arm))
            if not run:
                continue
            pc, _, _ = cluster_ci(by_request(run, "phantom_criteria"))
            pd, _, _ = cluster_ci(by_request(run, "phantom_documents"))
            st, _, _ = cluster_ci(by_request(run, "stale_criterion"))
            rej = sum(r["detail"]["records_rejected"] for r in run["results"])
            print(f"    {arm:13} phantom_criteria={pc:.2f}  phantom_documents={pd:.2f}  "
                  f"stale={st:.2f}  records_refused={rej}")

        print("\n  Completion")
        for arm in ARMS:
            run = runs.get((model, arm))
            if not run:
                continue
            s, _, _ = cluster_ci(by_request(run, "submitted"))
            errs = sum(1 for r in run["results"] if r["detail"].get("error"))
            print(f"    {arm:13} submitted={s:.2f}  errors={errs}/{len(run['results'])}")

    print("\n\nCorrectness by archetype, arm=none — where the decision actually breaks")
    for model in models:
        run = runs.get((model, "none"))
        if not run:
            continue
        g: dict[str, list[float]] = {}
        for r in run["results"]:
            g.setdefault(r["detail"]["archetype"], []).append(r["metrics"]["correct"])
        print(f"\n  {model}")
        for a in sorted(g):
            print(f"    {a:22} {sum(g[a]) / len(g[a]):.2f}")


if __name__ == "__main__":
    main()
