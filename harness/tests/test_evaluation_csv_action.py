import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aau_harness.eval_csv_review import verify_handoff
from aau_harness.evaluation_context import capture_context


ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / ".github/actions/aau-evaluation-review/run.py"
EXAMPLES = ROOT / "harness/examples/evaluation-review"


def setup_csv(tmp_path, *, repaired=True):
    workspace = tmp_path / "workspace with spaces"
    workspace.mkdir()
    plan = json.loads((EXAMPLES / "csv-plan.json").read_text())
    plan["evaluation_context"] = capture_context([{"scenario_id": "service", "authorization_required": True}],
                                                 {"fixture": "synthetic CI CSV"}, {"scorer.py": b"synthetic"})
    for side in ("baseline", "candidate"):
        (workspace / f"{side}-plan.json").write_text(json.dumps(plan))
    for target, source in (("policy.json", "csv-review-policy.json"), ("diagnostics.json", "csv-review-diagnostics.json"),
                           ("baseline.csv", "scored-observations.csv"),
                           ("candidate.csv", "scored-observations-repaired.csv" if repaired else "scored-observations.csv")):
        (workspace / target).write_bytes((EXAMPLES / source).read_bytes())
    env = {key: value for key, value in os.environ.items() if not key.startswith("AAU_EVAL_")}
    env.update(GITHUB_WORKSPACE=str(workspace), GITHUB_STEP_SUMMARY=str(tmp_path / "summary.md"),
               AAU_EVAL_INPUT_FORMAT="csv", AAU_EVAL_OUTPUT="review pack", AAU_EVAL_CANDIDATE="candidate.csv")
    for key, filename in (("POLICY", "policy.json"), ("BASELINE", "baseline.csv"), ("DIAGNOSTICS", "diagnostics.json"),
                          ("BASELINE_PLAN", "baseline-plan.json"), ("CANDIDATE_PLAN", "candidate-plan.json")):
        env[f"AAU_EVAL_{key}"] = filename
        env[f"AAU_EVAL_{key}_SHA256"] = hashlib.sha256((workspace / filename).read_bytes()).hexdigest()
    return workspace, env


def run(env):
    return subprocess.run([sys.executable, str(DRIVER)], env=env, capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("repaired,code", [(True, 0), (False, 1)])
def test_csv_action_retains_original_sources_and_both_policy_outcomes(tmp_path, repaired, code):
    workspace, env = setup_csv(tmp_path, repaired=repaired)
    result = run(env)
    assert result.returncode == code, result.stderr
    report = verify_handoff(workspace / "review pack")
    assert report["status"] == ("constraints_met" if repaired else "constraints_not_met")
    for side in ("baseline", "candidate"):
        assert (workspace / f"review pack/{side}/source.csv").read_bytes() == (workspace / f"{side}.csv").read_bytes()
    summary = (tmp_path / "summary.md").read_text()
    assert "both approved mapping-plan byte hashes matched" in summary
    assert "all 28 files recomputed" in summary
    assert "unauthorized_action" not in summary
    assert "synthetic CI CSV" not in summary
    assert run(env).returncode == 2


@pytest.mark.parametrize("key", ["POLICY", "BASELINE", "DIAGNOSTICS", "BASELINE_PLAN", "CANDIDATE_PLAN"])
def test_csv_action_rejects_byte_drift_in_every_approved_source(tmp_path, key):
    workspace, env = setup_csv(tmp_path)
    path = workspace / env[f"AAU_EVAL_{key}"]
    path.write_bytes(path.read_bytes() + b"\n")
    assert run(env).returncode == 2
    assert not (workspace / "review pack").exists()


@pytest.mark.parametrize("key", ["BASELINE_PLAN", "BASELINE_PLAN_SHA256", "CANDIDATE_PLAN", "CANDIDATE_PLAN_SHA256",
                                 "DIAGNOSTICS", "DIAGNOSTICS_SHA256"])
def test_csv_action_requires_all_mapping_and_diagnostic_approvals(tmp_path, key):
    workspace, env = setup_csv(tmp_path)
    env.pop(f"AAU_EVAL_{key}")
    assert run(env).returncode == 2
    assert not (workspace / "review pack").exists()


@pytest.mark.parametrize("side", ["BASELINE_PLAN", "CANDIDATE_PLAN"])
@pytest.mark.parametrize("value", ["0" * 63, "G" * 64, "0" * 64])
def test_csv_action_rejects_malformed_or_wrong_mapping_hashes(tmp_path, side, value):
    workspace, env = setup_csv(tmp_path)
    env[f"AAU_EVAL_{side}_SHA256"] = value
    assert run(env).returncode == 2
    assert not (workspace / "review pack").exists()


@pytest.mark.parametrize("key", ["BASELINE_PLAN", "CANDIDATE_PLAN", "BASELINE", "CANDIDATE"])
@pytest.mark.parametrize("path", ["../outside", "/tmp/outside", "bad\npath", "alias", "linked/candidate.csv"])
def test_csv_paths_cannot_escape_or_follow_symlinks(tmp_path, key, path):
    workspace, env = setup_csv(tmp_path)
    (workspace / "alias").symlink_to(workspace / env[f"AAU_EVAL_{key}"])
    (workspace / "linked").symlink_to(workspace, target_is_directory=True)
    env[f"AAU_EVAL_{key}"] = path
    assert run(env).returncode == 2
    assert not (workspace / "review pack").exists()


@pytest.mark.parametrize("context", ["missing", "different"])
def test_even_approved_csv_mappings_cannot_bypass_context_gate(tmp_path, context):
    workspace, env = setup_csv(tmp_path)
    path = workspace / "candidate-plan.json"
    plan = json.loads(path.read_text())
    if context == "missing":
        del plan["evaluation_context"]
    else:
        plan["evaluation_context"]["config_sha256"] = "0" * 64
    path.write_text(json.dumps(plan))
    env["AAU_EVAL_CANDIDATE_PLAN_SHA256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert run(env).returncode == 2
    assert not (workspace / "review pack").exists()


@pytest.mark.parametrize("source", ["candidate.csv", "candidate-plan.json"])
def test_invalid_csv_inputs_do_not_echo_private_or_annotation_shaped_payloads(tmp_path, source):
    workspace, env = setup_csv(tmp_path)
    path = workspace / source
    path.write_bytes(b"::error::PRIVATE_EXAMPLE_INVALID\n")
    if source.endswith("json"):
        env["AAU_EVAL_CANDIDATE_PLAN_SHA256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = run(env)
    assert result.returncode == 2
    assert "PRIVATE_EXAMPLE" not in result.stderr + result.stdout
    assert "::error::" not in result.stderr + result.stdout
    assert not (workspace / "review pack").exists()
    assert not (tmp_path / "summary.md").exists()


def test_csv_diagnostics_cannot_override_failed_policy(tmp_path):
    workspace, env = setup_csv(tmp_path, repaired=False)
    path = workspace / "diagnostics.json"
    plan = json.loads(path.read_text())
    plan["criteria"] = [plan["criteria"][0]]
    path.write_text(json.dumps(plan))
    env["AAU_EVAL_DIAGNOSTICS_SHA256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert run(env).returncode == 1
    assert verify_handoff(workspace / "review pack")["status"] == "constraints_not_met"
    repeatability = json.loads((workspace / "review pack/review/candidate-repeatability.json").read_text())
    assert repeatability["counts"]["all_recorded_pass"] == 1


def test_csv_mapping_inputs_cannot_be_silently_ignored_in_other_modes(tmp_path):
    workspace, env = setup_csv(tmp_path)
    env["AAU_EVAL_INPUT_FORMAT"] = "evaluations"
    assert run(env).returncode == 2
    assert not (workspace / "review pack").exists()


def test_csv_mode_cannot_silently_downgrade_to_policy_only(tmp_path):
    workspace, env = setup_csv(tmp_path)
    env["AAU_EVAL_DIAGNOSTICS"] = env["AAU_EVAL_DIAGNOSTICS_SHA256"] = ""
    assert run(env).returncode == 2
    assert not (workspace / "review pack").exists()


@pytest.mark.parametrize("key", ["CANDIDATE", "BASELINE", "CANDIDATE_PLAN"])
def test_oversized_csv_mode_inputs_are_rejected_before_output(tmp_path, key):
    workspace, env = setup_csv(tmp_path)
    (workspace / env[f"AAU_EVAL_{key}"]).write_bytes(b"x" * 2_000_001)
    assert run(env).returncode == 2
    assert not (workspace / "review pack").exists()


def test_shell_shaped_csv_mapping_filename_remains_data(tmp_path):
    workspace, env = setup_csv(tmp_path)
    filename = "plan$(touch should-not-exist).json"
    (workspace / filename).write_bytes((workspace / "candidate-plan.json").read_bytes())
    env["AAU_EVAL_CANDIDATE_PLAN"] = filename
    assert run(env).returncode == 0
    assert not (workspace / "should-not-exist").exists()
    metadata = (DRIVER.parent / "action.yml").read_text()
    for name in ("baseline-plan", "candidate-plan", "baseline-plan-sha256", "candidate-plan-sha256"):
        assert f"AAU_EVAL_{name.upper().replace('-', '_')}: ${{{{ inputs.{name} }}}}" in metadata
    assert 'run: python "$GITHUB_ACTION_PATH/run.py"' in metadata
