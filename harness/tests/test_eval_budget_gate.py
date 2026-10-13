from copy import deepcopy
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aau_harness.agent_bom import AgentBomError, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_demo import demo_inputs
from aau_harness.eval_import import import_observations
from aau_harness.eval_pack import create_pack, pack_payloads, verify_pack
from aau_harness.eval_csv_review import create_handoff, verify_handoff


ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / ".github/actions/aau-evaluation-review/run.py"


def inputs(outcome="pass"):
    policy, baseline, candidate, diagnostics = demo_inputs()
    budget = {"plan_version": "aau-operating-budget/1.0", "scenario_ids": candidate["scenario_ids"],
              "minimum_repeats": 4, "criteria": diagnostics["criteria"], "cost_basis": "synthetic",
              "limits": {"cost_per_passing_attempt_usd": .3, "p95_latency_s": 2}, "groups": []}
    if outcome in ("policy", "both"):
        candidate = deepcopy(baseline)
        for row in candidate["observations"]:
            row.update(cost_usd=.01, latency_s=1)
    if outcome in ("budget", "both"):
        for row in candidate["observations"]:
            row["latency_s"] = 3
    if outcome == "unknown":
        del candidate["observations"][0]["cost_usd"]
    return policy, baseline, candidate, diagnostics, budget


def csv_source(recording):
    plan = {"plan_version": "aau-csv-observation-import/1.0", "source_label": "synthetic gate fixture",
            "scenario_ids": recording["scenario_ids"], "n_repeats": recording["n_repeats"],
            "evaluation_context": recording["evaluation_context"],
            "columns": {"scenario_id": "case", "repeat": "repeat", "metrics": {"completion": "done", "unauthorized": "unauthorized"},
                        "operating": {"cost_usd": "cost", "latency_s": "seconds", "n_api_calls": "calls"}}}
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["case", "repeat", "done", "unauthorized", "cost", "seconds", "calls"])
    for r in recording["observations"]:
        writer.writerow([r["scenario_id"], r["repeat"], r["metrics"]["completion"], r["metrics"]["unauthorized"],
                         r.get("cost_usd", ""), r.get("latency_s", ""), r.get("n_api_calls", "")])
    return plan, stream.getvalue().encode("utf-8")


@pytest.mark.parametrize("recordings", [False, True])
@pytest.mark.parametrize("outcome,policy_status,budget_status", [
    ("pass", "constraints_met", "constraints_met"),
    ("policy", "constraints_not_met", "constraints_met"),
    ("budget", "constraints_met", "constraints_not_met"),
    ("both", "constraints_not_met", "constraints_not_met"),
    ("unknown", "constraints_met", "constraints_not_verified")])
def test_combined_gate_preserves_both_independent_verdicts(tmp_path, recordings, outcome, policy_status, budget_status):
    policy, baseline, candidate, diagnostics, budget = inputs(outcome)
    if not recordings:
        baseline, candidate = map(import_observations, (baseline, candidate))
    original = deepcopy((policy, baseline, candidate, diagnostics, budget))
    pack = tmp_path / "pack"
    report = create_pack(policy, baseline, candidate, pack, recordings=recordings, diagnostics=diagnostics, operating_budget=budget)
    assert report == verify_pack(pack, require_recordings=recordings, require_diagnostics=True, require_budget=True)
    assert report["policy_status"] == policy_status
    assert report["candidate_budget_status"] == budget_status
    assert report["status"] == ("constraints_met" if outcome == "pass" else
                                "constraints_not_verified" if outcome == "unknown" else "constraints_not_met")
    policy_review = json.loads((pack / "review.json").read_bytes())
    assert policy_review["status"] == policy_status
    assert report["policy_review_sha256"] == digest(policy_review)
    assert report["candidate_sha256"] == digest(json.loads((pack / "candidate.json").read_bytes()))
    assert len(list(pack.iterdir())) == (16 if recordings else 14)
    page = (pack / "review.html").read_text()
    assert "Combined constraints" in page and "Independent verdicts" in page and "--require-budget" in page
    assert ("sixteen" if recordings else "fourteen") in page
    assert main(["evaluation-pack", "verify", str(pack), "--require-budget"]) == int(outcome != "pass")
    assert (policy, baseline, candidate, diagnostics, budget) == original


@pytest.mark.parametrize("outcome", ["pass", "policy", "budget", "both", "unknown"])
def test_csv_source_chain_retains_combined_gate_and_cli_outcome(tmp_path, outcome):
    policy, baseline, candidate, diagnostics, budget = inputs(outcome)
    bp, bc = csv_source(baseline)
    cp, cc = csv_source(candidate)
    report = create_handoff(policy, bp, bc, cp, cc, diagnostics, tmp_path / "pack", operating_budget=budget)
    assert report == verify_handoff(tmp_path / "pack", require_budget=True)
    assert report["report_version"] == "aau-csv-evaluation-handoff/1.1"
    assert len([p for p in (tmp_path / "pack").rglob("*") if p.is_file()]) == 31
    assert (tmp_path / "pack/candidate/source.csv").read_bytes() == cc
    assert "31 files" in (tmp_path / "pack/README.txt").read_text()
    assert report["review_sha256"] == digest(json.loads((tmp_path / "pack/review/review.json").read_bytes()))
    assert report["gate_sha256"] == digest(json.loads((tmp_path / "pack/review/gate.json").read_bytes()))
    assert main(["csv-review", "verify", str(tmp_path / "pack"), "--require-budget"]) == int(outcome != "pass")


@pytest.mark.parametrize("name", sorted(pack_payloads(*inputs()[:3], recordings=True,
                         diagnostics=inputs()[3], operating_budget=inputs()[4])[1]))
def test_every_gated_pack_member_recomputed_even_if_rehashed(tmp_path, name):
    policy, baseline, candidate, diagnostics, budget = inputs()
    pack = tmp_path / "pack"
    create_pack(policy, baseline, candidate, pack, recordings=True, diagnostics=diagnostics, operating_budget=budget)
    (pack / name).write_bytes((pack / name).read_bytes() + b" ")
    if name != "manifest.json":
        manifest = json.loads((pack / "manifest.json").read_bytes())
        manifest["files"][name] = digest((pack / name).read_bytes())
        (pack / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        verify_pack(pack, require_budget=True)


def test_require_budget_rejects_valid_downgrade_and_missing_diagnostics_before_creation(tmp_path):
    policy, baseline, candidate, diagnostics, budget = inputs()
    create_pack(policy, baseline, candidate, tmp_path / "legacy", recordings=True, diagnostics=diagnostics)
    with pytest.raises(AgentBomError, match="budget gate required"):
        verify_pack(tmp_path / "legacy", require_budget=True)
    bp, bc = csv_source(baseline)
    cp, cc = csv_source(candidate)
    create_handoff(policy, bp, bc, cp, cc, diagnostics, tmp_path / "csv")
    with pytest.raises(AgentBomError, match="budget gate required"):
        verify_handoff(tmp_path / "csv", require_budget=True)
    with pytest.raises(AgentBomError, match="diagnostic plan"):
        create_pack(policy, baseline, candidate, tmp_path / "invalid", recordings=True, operating_budget=budget)
    assert not (tmp_path / "invalid").exists()
    budget["criteria"] = [{"metric": "completion", "direction": "higher", "limit": 0}]
    with pytest.raises(AgentBomError, match="same joint-pass"):
        create_pack(policy, baseline, candidate, tmp_path / "invalid", recordings=True,
                    diagnostics=diagnostics, operating_budget=budget)
    assert not (tmp_path / "invalid").exists()


def action_inputs(tmp_path, input_format="evaluations", outcome="pass"):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    policy, baseline, candidate, diagnostics, budget = inputs(outcome)
    env = {key: value for key, value in os.environ.items() if not key.startswith("AAU_EVAL_")}
    env.update(GITHUB_WORKSPACE=str(workspace), GITHUB_STEP_SUMMARY=str(tmp_path / "summary.md"),
               AAU_EVAL_INPUT_FORMAT=input_format, AAU_EVAL_OUTPUT="pack", AAU_EVAL_CANDIDATE="candidate")
    values = {"POLICY": policy, "DIAGNOSTICS": diagnostics, "OPERATING_BUDGET": budget}
    if input_format == "csv":
        bp, baseline = csv_source(baseline)
        cp, candidate = csv_source(candidate)
        values.update(BASELINE_PLAN=bp, CANDIDATE_PLAN=cp)
    elif input_format == "evaluations":
        baseline, candidate = map(import_observations, (baseline, candidate))
    for key, value in {**values, "BASELINE": baseline}.items():
        name = key.lower()
        payload = value if isinstance(value, bytes) else rendered(value)
        (workspace / name).write_bytes(payload)
        env[f"AAU_EVAL_{key}"] = name
        env[f"AAU_EVAL_{key}_SHA256"] = digest(payload)
    (workspace / "candidate").write_bytes(candidate if isinstance(candidate, bytes) else rendered(candidate))
    return workspace, env


def run_action(env):
    return subprocess.run([sys.executable, str(DRIVER)], env=env, capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("input_format", ["evaluations", "recordings", "csv"])
@pytest.mark.parametrize("outcome", ["pass", "policy", "budget", "both", "unknown"])
def test_action_gates_both_verdicts_in_all_input_formats(tmp_path, input_format, outcome):
    workspace, env = action_inputs(tmp_path, input_format, outcome)
    result = run_action(env)
    assert result.returncode == int(outcome != "pass"), result.stderr
    report = (verify_handoff(workspace / "pack", require_budget=True) if input_format == "csv" else
              verify_pack(workspace / "pack", require_budget=True))
    summary = (tmp_path / "summary.md").read_text()
    assert f"Result: **{report['status']}**" in summary
    assert "Both policy and budget must be met" in summary
    assert "synthetic-service" not in summary and "unauthorized" not in summary
    assert "p95_latency_s" not in summary and "cost_per_passing_attempt_usd" not in summary
    assert run_action(env).returncode == 2


@pytest.mark.parametrize("defect", ["no-hash", "no-path", "wrong-hash", "malformed-hash", "byte-drift", "no-diagnostics",
    "absolute", "escape", "control", "symlink", "ancestor-symlink", "oversized", "criteria-mismatch"])
def test_budget_approval_and_paths_fail_before_output_without_raw_diagnostic_leak(tmp_path, defect):
    workspace, env = action_inputs(tmp_path)
    path = workspace / "operating_budget"
    if defect == "no-hash":
        env.pop("AAU_EVAL_OPERATING_BUDGET_SHA256")
    elif defect == "no-path":
        env.pop("AAU_EVAL_OPERATING_BUDGET")
    elif defect == "wrong-hash":
        env["AAU_EVAL_OPERATING_BUDGET_SHA256"] = "0" * 64
    elif defect == "malformed-hash":
        env["AAU_EVAL_OPERATING_BUDGET_SHA256"] = "G" * 64
    elif defect == "byte-drift":
        path.write_bytes(path.read_bytes() + b"\n")
    elif defect == "no-diagnostics":
        env.pop("AAU_EVAL_DIAGNOSTICS")
        env.pop("AAU_EVAL_DIAGNOSTICS_SHA256")
    elif defect in ("absolute", "escape", "control"):
        env["AAU_EVAL_OPERATING_BUDGET"] = {"absolute": "/tmp/private", "escape": "../private", "control": "::error::private\n"}[defect]
    elif defect == "symlink":
        (workspace / "alias").symlink_to(path)
        env["AAU_EVAL_OPERATING_BUDGET"] = "alias"
    elif defect == "ancestor-symlink":
        (workspace / "alias").symlink_to(workspace, target_is_directory=True)
        env["AAU_EVAL_OPERATING_BUDGET"] = "alias/operating_budget"
    elif defect == "oversized":
        path.write_bytes(b" " * 2_000_001)
    elif defect == "criteria-mismatch":
        value = json.loads(path.read_bytes())
        value["criteria"][0]["limit"] = 0
        path.write_bytes(rendered(value))
        env["AAU_EVAL_OPERATING_BUDGET_SHA256"] = digest(path.read_bytes())
    result = run_action(env)
    assert result.returncode == 2
    assert not (workspace / "pack").exists()
    assert "private" not in result.stderr and "::error::" not in result.stderr


def test_budget_gate_html_escapes_declared_group_labels(tmp_path):
    policy, baseline, candidate, diagnostics, budget = inputs()
    budget["groups"] = [{"group_id": '<script>alert("x")</script>', "scenario_ids": budget["scenario_ids"],
                         "limits": {"p95_latency_s": 2}}]
    create_pack(policy, baseline, candidate, tmp_path / "pack", recordings=True, diagnostics=diagnostics, operating_budget=budget)
    page = (tmp_path / "pack/review.html").read_text()
    assert '<script>' not in page and '&lt;script&gt;' in page


@pytest.mark.parametrize("member", ["review/operating-budget.json", "review/candidate-budget.json", "review/gate.json",
                                    "review/review.html", "handoff.json", "README.txt"])
def test_csv_gate_members_recompute_after_outer_manifest_rehash(tmp_path, member):
    policy, baseline, candidate, diagnostics, budget = inputs()
    bp, bc = csv_source(baseline)
    cp, cc = csv_source(candidate)
    pack = tmp_path / "pack"
    create_handoff(policy, bp, bc, cp, cc, diagnostics, pack, operating_budget=budget)
    (pack / member).write_bytes((pack / member).read_bytes() + b" ")
    manifest = json.loads((pack / "manifest.json").read_bytes())
    manifest["files"][member] = digest((pack / member).read_bytes())
    (pack / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        verify_handoff(pack, require_budget=True)


@pytest.mark.parametrize("basis", ["unknown", "estimate"])
def test_approved_but_incompatible_cost_basis_cannot_pass_action(tmp_path, basis):
    workspace, env = action_inputs(tmp_path)
    path = workspace / "diagnostics"
    diagnostics = json.loads(path.read_bytes())
    diagnostics["cost_basis"]["candidate"] = basis
    path.write_bytes(rendered(diagnostics))
    env["AAU_EVAL_DIAGNOSTICS_SHA256"] = digest(path.read_bytes())
    assert run_action(env).returncode == 1
    report = verify_pack(workspace / "pack", require_budget=True)
    assert report["status"] == "constraints_not_verified"
    assert report["policy_status"] == "constraints_met"


def test_valid_but_unrelated_gated_review_cannot_replace_csv_review(tmp_path):
    policy, baseline, candidate, diagnostics, budget = inputs()
    bp, bc = csv_source(baseline)
    cp, cc = csv_source(candidate)
    original, alternate = tmp_path / "original", tmp_path / "alternate"
    create_handoff(policy, bp, bc, cp, cc, diagnostics, original, operating_budget=budget)
    cp["source_label"] = "different source claim, identical scored outcomes"
    create_handoff(policy, bp, bc, cp, cc, diagnostics, alternate, operating_budget=budget)
    for source in (alternate / "review").iterdir():
        (original / "review" / source.name).write_bytes(source.read_bytes())
    assert verify_pack(original / "review", require_budget=True)["status"] == "constraints_met"
    manifest = json.loads((original / "manifest.json").read_bytes())
    for name in manifest["files"]:
        manifest["files"][name] = digest((original / name).read_bytes())
    (original / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match="does not recompute"):
        verify_handoff(original, require_budget=True)
