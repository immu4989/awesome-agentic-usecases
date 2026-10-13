"""Three synthetic retry dossiers: earlier harm, slow eventual completion, and repaired observations."""

import argparse
from copy import deepcopy
import json
from pathlib import Path

from aau_harness.eval_retry_review import create_handoff, verify_handoff
from aau_harness.evaluation_context import capture_context


def demo_inputs():
    root = Path(__file__).resolve().parent
    plan = json.loads((root / "retry-plan.json").read_text())
    ledger = json.loads((root / "retry-ledger.json").read_text())
    # These policy/diagnostic fixtures share the same two metric definitions and service census.
    policy = json.loads((root / "csv-review-policy.json").read_text())
    diagnostics = json.loads((root / "csv-review-diagnostics.json").read_text())
    plan["evaluation_context"] = capture_context(
        [{"scenario_id": "service", "fixture": "sequential retry example"}],
        {"unit": "logical_task", "reducers": plan["metric_reducers"], "scope": plan["attempt_scope"]},
        {"synthetic_fixture.py": Path(__file__).read_bytes()})
    budget = {"plan_version": "aau-operating-budget/1.0", "scenario_ids": ["service"], "minimum_repeats": 2,
              "criteria": diagnostics["criteria"], "cost_basis": "synthetic", "groups": [],
              "limits": {"p95_latency_s": 3, "cost_per_passing_attempt_usd": .25}}
    candidates = {"earlier-harm": deepcopy(ledger), "slow-completion": deepcopy(ledger), "repaired": deepcopy(ledger)}
    for name in ("slow-completion", "repaired"):
        candidates[name]["tasks"][0]["attempts"][0]["metrics"]["unauthorized"] = 0
    candidates["repaired"]["tasks"][0]["elapsed_s"] = 3
    return policy, plan, ledger, diagnostics, budget, candidates


def build_demo(directory):
    policy, plan, ledger, diagnostics, budget, candidates = demo_inputs()
    directory.mkdir(parents=True, exist_ok=False)
    for name, candidate in candidates.items():
        create_handoff(policy, plan, ledger, plan, candidate, diagnostics, directory / name, operating_budget=budget)
        result = verify_handoff(directory / name, require_budget=True)
        if result["status"] != ("constraints_met" if name == "repaired" else "constraints_not_met"):
            raise ValueError("synthetic retry handoff differs from its expected outcome")
    print("Three synthetic retry handoffs verified. No production performance or agent repair was measured.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    build_demo(parser.parse_args().out)
