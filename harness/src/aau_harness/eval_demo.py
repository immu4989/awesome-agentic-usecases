"""Create a no-key synthetic evaluation walkthrough from the installed package."""

import argparse
from pathlib import Path
import sys

from .agent_bom import AgentBomError
from .eval_pack import create_pack, verify_pack
from .evaluation_context import capture_context


GUIDE = """AAU synthetic evaluation walkthrough

Open intermittent/review.html and repaired/review.html in a browser.
Both are self-contained: no scripts, analytics, fonts, uploads, or model calls.

The first fixture completes every attempt but misses authorization in three
of four repeats. Its $0.10 attempt cost becomes $0.40 per jointly passing
attempt when failure costs stay included. The repaired fixture records $0.25
per attempt and per passing attempt. All scores, costs, timings, and API-call
counts are constructed, not measured service outcomes or model performance.

From this directory, using the same installed harness, run:

  aau evaluation-pack verify intermittent --require-recordings --require-diagnostics
  aau evaluation-pack verify repaired --require-recordings --require-diagnostics

Expected exit codes: intermittent=1, repaired=0. Both complete packs verify;
the first retains its failed policy constraints. Exit 2 means invalid evidence
or failed verification. Each folder has thirteen files; retain them together.

Each pack contains policy.json, diagnostics.json, baseline-recording.json,
candidate-recording.json, normalized baseline.json and candidate.json,
review.json, review.html, four diagnostic reports, and manifest.json.
The importer preserves the supplied operating measurements and makes no
measurements itself. Hashes do not authenticate source execution or approval.

For your own adoption, review and replace the cases, scoring process, policy,
and diagnostic assumptions independently. Do not use these fixture thresholds
as production requirements or copy their context hashes onto real observations.
Verify the raw recording-to-review chain, and inspect sensitive data before
sharing a pack. An observed pass is not deployment approval or proof of safety.

This guide is written last, after both dossiers have been created and verified.
If creation is interrupted, preserve the partial output for investigation and
use a fresh destination; do not treat its mere presence as completed evidence.
"""


def demo_inputs():
    criteria = [{"metric": "completion", "direction": "higher", "limit": 1},
                {"metric": "unauthorized", "direction": "lower", "limit": 0}]
    context = capture_context([{"scenario_id": "synthetic-service", "authorization_required": True}],
                              {"fixture": "installed-evaluation-demo"}, {"eval_demo.py": Path(__file__).read_bytes()})
    policy = {"policy_version": "aau-evaluation-review-policy/1.0", "scenario_ids": ["synthetic-service"],
              "minimum_repeats": 4, "metrics": [{"metric": rule["metric"], "direction": rule["direction"],
                  "candidate_observation_limit": rule["limit"], "max_mean_regression": 0,
                  "max_regressed_scenarios": 0} for rule in criteria]}
    plan = {"plan_version": "aau-evaluation-diagnostics/1.0", "criteria": criteria, "draw_sizes": [1, 2, 4],
            "cost_basis": {"baseline": "synthetic", "candidate": "synthetic"}}

    def recording(repaired):
        return {"format_version": "aau-recorded-observations/1.1",
                "source_label": "Synthetic installed-package example; no model or real service measurements",
                "scenario_ids": ["synthetic-service"], "n_repeats": 4, "evaluation_context": context,
                "observations": [{"scenario_id": "synthetic-service", "repeat": repeat,
                    "metrics": {"completion": 1, "unauthorized": int(not repaired and repeat > 0)},
                    "cost_usd": .25 if repaired else .1, "latency_s": 2 if repaired else 12 if repeat == 3 else 1,
                    "n_api_calls": 2} for repeat in range(4)]}
    return policy, recording(False), recording(True), plan


def create_demo(directory: Path) -> None:
    policy, baseline, repaired, plan = demo_inputs()
    directory.mkdir(parents=True, exist_ok=False)
    for name, candidate in (("intermittent", baseline), ("repaired", repaired)):
        create_pack(policy, baseline, candidate, directory / name, recordings=True, diagnostics=plan)
        report = verify_pack(directory / name, require_recordings=True, require_diagnostics=True)
        expected = "constraints_not_met" if name == "intermittent" else "constraints_met"
        if report["status"] != expected:
            raise AgentBomError("synthetic demonstration outcome differs from its contract")
    (directory / "README.txt").write_text(GUIDE, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau evaluation-demo", description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="new output directory; existing paths are never overwritten")
    args = parser.parse_args(argv)
    try:
        create_demo(args.out)
        print("Created and verified two synthetic dossiers. Open repaired/review.html and README.txt in the output directory.")
        print("Intermittent policy fails; repaired policy passes. No agent, model, or real service was executed.")
        return 0
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
