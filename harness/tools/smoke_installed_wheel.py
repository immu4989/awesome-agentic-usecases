#!/usr/bin/env python3
"""Test a trusted local wheel outside the checkout in a fresh, no-index Python 3.11+ venv."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def smoke(wheel: Path) -> None:
    if sys.version_info < (3, 11):
        raise ValueError("this no-dependency wheel smoke requires Python 3.11+; it is not the minimum-version test")
    wheel = wheel.resolve(strict=True)
    if not wheel.is_file() or not wheel.name.startswith("aau_harness-") or wheel.suffix != ".whl":
        raise ValueError("provide one locally built aau_harness wheel")
    with tempfile.TemporaryDirectory(prefix="aau-installed-wheel-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        binary = environment / ("Scripts" if os.name == "nt" else "bin")
        python = binary / ("python.exe" if os.name == "nt" else "python")
        cli = binary / ("aau.exe" if os.name == "nt" else "aau")
        env = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "PYTHONHOME")}
        env["PYTHONNOUSERSITE"] = "1"

        def run(args, expected=0):
            result = subprocess.run([str(value) for value in args], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=60)
            if result.returncode != expected:
                raise RuntimeError(f"installed-wheel command returned {result.returncode}, expected {expected}: "
                                   + result.stdout + result.stderr)
            return result.stdout

        run([python, "-I", "-m", "pip", "--isolated", "install", "--no-index", "--no-deps", "--disable-pip-version-check", wheel])
        location = Path(run([python, "-I", "-c", "import aau_harness; print(aau_harness.__file__)"]).strip()).resolve()
        if environment.resolve() not in location.parents:
            raise RuntimeError("import resolved outside the isolated installation")
        run([cli, "runtime-info", "--out", "runtime.json"])
        run([cli, "runtime-info", "--verify", "runtime.json"])
        identity = json.loads((root / "runtime.json").read_text())
        if "runtime_info.py" not in identity["source_files"] or str(root) in json.dumps(identity):
            raise RuntimeError("installed source receipt is incomplete or exposes local paths")
        run([cli, "evaluation-demo", "--out", "demo"])
        run([cli, "evaluation-demo", "--out", "demo"], expected=2)
        for name, code in (("intermittent", 1), ("repaired", 0)):
            run([cli, "evaluation-pack", "verify", f"demo/{name}", "--require-recordings", "--require-diagnostics"], code)
        repaired = root / "demo/repaired"
        matrix_plan = {"plan_version": "aau-candidate-matrix/1.0", "candidate_ids": ["intermittent", "repaired"],
                       "criteria": json.loads((repaired / "diagnostics.json").read_text())["criteria"],
                       "cost_basis": {"intermittent": "synthetic", "repaired": "synthetic"}}
        (root / "matrix-plan.json").write_text(json.dumps(matrix_plan))
        run([cli, "candidate-matrix", "create", "matrix-plan.json", repaired / "policy.json", repaired / "baseline.json",
             "--candidate", "intermittent=demo/intermittent/candidate.json",
             "--candidate", "repaired=demo/repaired/candidate.json", "--out", "matrix"])
        run([cli, "candidate-matrix", "verify", "matrix"])
        matrix = json.loads((root / "matrix/matrix.json").read_text())
        if matrix["operating_groups"][0]["eligible_candidates"] != ["repaired"]:
            raise RuntimeError("installed matrix allowed failed policy to enter operating comparisons")
        budget = {"plan_version": "aau-operating-budget/1.0",
                  "scenario_ids": json.loads((repaired / "policy.json").read_text())["scenario_ids"],
                  "minimum_repeats": 4, "criteria": matrix_plan["criteria"], "cost_basis": "synthetic",
                  "limits": {"p95_latency_s": 2, "cost_per_passing_attempt_usd": .25}, "groups": []}
        (root / "budget.json").write_text(json.dumps(budget))
        for name, code in (("intermittent", 1), ("repaired", 0)):
            args = [cli, "operating-budget", "budget.json", f"demo/{name}/candidate.json", "--cost-basis", "synthetic"]
            run([*args, "--out", f"{name}-budget.json"], code)
            run([*args, "--verify", f"{name}-budget.json"], code)
        matrix_plan.update(plan_version="aau-candidate-matrix/1.1", operating_budget=budget)
        (root / "budget-matrix-plan.json").write_text(json.dumps(matrix_plan))
        run([cli, "candidate-matrix", "create", "budget-matrix-plan.json", repaired / "policy.json", repaired / "baseline.json",
             "--candidate", "intermittent=demo/intermittent/candidate.json",
             "--candidate", "repaired=demo/repaired/candidate.json", "--out", "budget-matrix"])
        run([cli, "candidate-matrix", "verify", "budget-matrix"])
        budget_matrix = json.loads((root / "budget-matrix/matrix.json").read_text())
        if [r["budget_status"] for r in budget_matrix["candidates"]] != ["constraints_not_met", "constraints_met"]:
            raise RuntimeError("installed matrix omitted recorded operating budget checks")
        for name, code in (("intermittent", 1), ("repaired", 0)):
            source_pack = root / f"demo/{name}"
            run([cli, "evaluation-pack", "from-recordings", source_pack / "policy.json", source_pack / "baseline-recording.json",
                 source_pack / "candidate-recording.json", "--diagnostics", source_pack / "diagnostics.json",
                 "--operating-budget", "budget.json", "--out", f"gated-{name}"], code)
            run([cli, "evaluation-pack", "verify", f"gated-{name}", "--require-recordings", "--require-budget"], code)
        run([cli, "evaluation-pack", "verify", repaired, "--require-budget"], expected=2)
        budget["limits"]["p95_latency_s"] = 1
        (root / "strict-budget.json").write_text(json.dumps(budget))
        run([cli, "evaluation-pack", "create", repaired / "policy.json", repaired / "baseline.json", repaired / "candidate.json",
             "--diagnostics", repaired / "diagnostics.json", "--operating-budget", "strict-budget.json", "--out", "budget-only-failure"], 1)
        run([cli, "evaluation-pack", "verify", "budget-only-failure", "--require-budget"], 1)
        if json.loads((root / "budget-only-failure/review.json").read_text())["status"] != "constraints_met":
            raise RuntimeError("combined budget gate changed the independent policy verdict")
        baseline, candidate = repaired / "baseline-recording.json", repaired / "candidate-recording.json"
        run([cli, "compare-eval-contexts", baseline, candidate, "--input-format", "recordings", "--out", "context.json"])
        run([cli, "compare-eval-contexts", baseline, candidate, "--input-format", "recordings", "--verify", "context.json"])
        run([cli, "import-eval", candidate, "--out", "imported.json"])
        run([cli, "import-eval", candidate, "--verify", "imported.json"])
        # These tiny fixtures are created outside the checkout, not loaded from repository examples.
        csv_plan = {"plan_version": "aau-csv-observation-import/1.0", "source_label": "synthetic wheel smoke",
                    "scenario_ids": ["case"], "n_repeats": 1,
                    "columns": {"scenario_id": "case", "repeat": "repeat", "metrics": {"completion": "score"},
                                "operating": {"cost_usd": "usd"}}}
        (root / "csv-plan.json").write_text(json.dumps(csv_plan))
        (root / "source.csv").write_bytes(b"case,repeat,score,usd\ncase,0,1,0.1\n")
        run([cli, "csv-eval", "create", "csv-plan.json", "source.csv", "--out", "converted"])
        run([cli, "csv-eval", "verify", "converted", "--evaluation", "converted/evaluation.json"])
        policy = {"policy_version": "aau-evaluation-review-policy/1.0", "scenario_ids": ["case"],
                  "minimum_repeats": 1, "metrics": [{"metric": "completion", "direction": "higher",
                  "candidate_observation_limit": 1, "max_mean_regression": 0, "max_regressed_scenarios": 0}]}
        diagnostics = {"plan_version": "aau-evaluation-diagnostics/1.0",
                       "criteria": [{"metric": "completion", "direction": "higher", "limit": 1}],
                       "draw_sizes": [1], "cost_basis": {"baseline": "synthetic", "candidate": "synthetic"}}
        (root / "csv-policy.json").write_text(json.dumps(policy))
        (root / "csv-diagnostics.json").write_text(json.dumps(diagnostics))
        (root / "failed.csv").write_bytes(b"case,repeat,score,usd\ncase,0,0,0.1\n")
        for filename, code in (("source.csv", 0), ("failed.csv", 1)):
            destination = "handoff-" + filename
            run([cli, "csv-review", "create", "csv-policy.json", "csv-plan.json", "source.csv",
                 "csv-plan.json", filename, "--diagnostics", "csv-diagnostics.json", "--out", destination], code)
            run([cli, "csv-review", "verify", destination], code)
        csv_budget = {"plan_version": "aau-operating-budget/1.0", "scenario_ids": ["case"], "minimum_repeats": 1,
                      "criteria": diagnostics["criteria"], "cost_basis": "synthetic",
                      "limits": {"cost_per_passing_attempt_usd": .2}, "groups": []}
        (root / "csv-budget.json").write_text(json.dumps(csv_budget))
        run([cli, "csv-review", "create", "csv-policy.json", "csv-plan.json", "source.csv", "csv-plan.json", "source.csv",
             "--diagnostics", "csv-diagnostics.json", "--operating-budget", "csv-budget.json", "--out", "gated-csv"])
        run([cli, "csv-review", "verify", "gated-csv", "--require-budget"])
        run([cli, "csv-review", "verify", "handoff-source.csv", "--require-budget"], 2)
        (root / "handoff-source.csv/candidate/source.csv").write_bytes(b"case,repeat,score,usd\ncase,0,0,0.1\n")
        run([cli, "csv-review", "verify", "handoff-source.csv"], expected=2)
        report_path = repaired / "candidate-operations.json"
        report = json.loads(report_path.read_text())
        report["overall"]["cost"]["total_usd"] = 999
        report_path.write_text(json.dumps(report))
        run([cli, "evaluation-pack", "verify", repaired, "--require-recordings", "--require-diagnostics"], expected=2)
    print("Installed wheel verified outside checkout: demo, policy and operating budget outcomes, candidate matrices, recording and CSV import, CSV review handoff, context review, overwrite refusal, and tamper rejection.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    try:
        smoke(args.wheel)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
