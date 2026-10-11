import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / ".github/actions/aau-evaluation-review/run.py"


def setup(tmp_path, candidate="legitimate", demo="demo.py"):
    script = ROOT / "harness/examples/evaluation-review" / demo
    spec = importlib.util.spec_from_file_location("action_eval_demo", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    workspace = tmp_path / "workspace with spaces"
    module.build_demo(workspace)
    return workspace, dict(os.environ, GITHUB_WORKSPACE=str(workspace),
                          AAU_EVAL_POLICY="policy.json", AAU_EVAL_BASELINE="baseline.json",
                          AAU_EVAL_CANDIDATE=f"{candidate}.json", AAU_EVAL_OUTPUT="review pack",
                          AAU_EVAL_POLICY_SHA256=hashlib.sha256((workspace / "policy.json").read_bytes()).hexdigest(),
                          AAU_EVAL_BASELINE_SHA256=hashlib.sha256((workspace / "baseline.json").read_bytes()).hexdigest(),
                          GITHUB_STEP_SUMMARY=str(tmp_path / "summary.md"))


def run(env):
    return subprocess.run([sys.executable, str(DRIVER)], env=env, capture_output=True, text=True)


@pytest.mark.parametrize("candidate,code", [("legitimate", 0), ("unsafe", 1)])
def test_action_runs_offline_and_preserves_both_review_outcomes(tmp_path, candidate, code):
    workspace, env = setup(tmp_path, candidate)
    result = run(env)
    assert result.returncode == code, result.stderr
    report = json.loads((workspace / "review pack/review.json").read_text())
    assert report["status"] == ("constraints_met" if code == 0 else "constraints_not_met")
    summary = (tmp_path / "summary.md").read_text()
    assert report["status"] in summary
    assert "needs-authorization" not in summary
    assert "inspect before uploading" in summary
    assert run(env).returncode == 2


@pytest.mark.parametrize("candidate,code", [("regressed", 1), ("repaired", 0)])
def test_action_enforces_cohort_policy_and_exports_verifiable_pack(tmp_path, candidate, code):
    from aau_harness.eval_pack import verify_pack

    workspace, env = setup(tmp_path, candidate, demo="cohorts.py")
    result = run(env)
    assert result.returncode == code, result.stderr
    report = verify_pack(workspace / "review pack")
    assert report["report_version"] == "aau-evaluation-policy-review/1.1"
    assert report["status"] == ("constraints_met" if code == 0 else "constraints_not_met")
    assert {group["cohort_id"] for group in report["cohort_reviews"]} == {"routine", "assisted"}
    if code:
        assert all(check["passed"] for check in report["metric_checks"][0]["checks"])
        assert {failure["cohort_id"] for failure in report["failed_constraints"]} == {"assisted"}


@pytest.mark.parametrize("include_context,code", [(True, 0), (False, 2)])
def test_imported_observations_require_explicit_context_in_action(tmp_path, include_context, code):
    from aau_harness.eval_import import import_observations

    workspace, env = setup(tmp_path)
    for name in ("baseline", "legitimate"):
        path = workspace / f"{name}.json"
        original = json.loads(path.read_text())
        source = {"format_version": "aau-recorded-observations/1.0", "source_label": "synthetic import",
                  "scenario_ids": sorted({row["scenario_id"] for row in original["results"]}),
                  "n_repeats": original["n_repeats"],
                  "observations": [{key: row[key] for key in ("scenario_id", "repeat", "metrics")}
                                   for row in original["results"]]}
        if include_context:
            source["evaluation_context"] = original["evaluation_context"]
        path.write_text(json.dumps(import_observations(source)))
    env["AAU_EVAL_BASELINE_SHA256"] = hashlib.sha256((workspace / "baseline.json").read_bytes()).hexdigest()
    result = run(env)
    assert result.returncode == code, result.stderr
    assert (workspace / "review pack").exists() == include_context


@pytest.mark.parametrize("source", ["policy", "baseline"])
def test_approved_source_byte_change_refused_before_output(tmp_path, source):
    workspace, env = setup(tmp_path)
    path = workspace / f"{source}.json"
    path.write_bytes(path.read_bytes() + b"\n")
    assert run(env).returncode == 2
    assert not (workspace / "review pack").exists()


@pytest.mark.parametrize("invalid", ["", "0" * 63, "g" * 64, "0" * 64])
def test_missing_malformed_or_wrong_approval_hash_refused(tmp_path, invalid):
    workspace, env = setup(tmp_path)
    env["AAU_EVAL_POLICY_SHA256"] = invalid
    assert run(env).returncode == 2
    assert not (workspace / "review pack").exists()


@pytest.mark.parametrize("path", ["../outside", "/tmp/outside", ".", "", "bad\npath"])
def test_output_cannot_escape_workspace_or_replace_root(tmp_path, path):
    workspace, env = setup(tmp_path)
    original = {item.name for item in workspace.iterdir()}
    env["AAU_EVAL_OUTPUT"] = path
    assert run(env).returncode == 2
    assert {item.name for item in workspace.iterdir()} == original


@pytest.mark.parametrize("mode", ["missing", "different"])
def test_missing_or_conflicting_context_cannot_satisfy_action(tmp_path, mode):
    workspace, env = setup(tmp_path)
    path = workspace / "legitimate.json"
    value = json.loads(path.read_text())
    if mode == "missing":
        del value["evaluation_context"]
    else:
        value["evaluation_context"]["config_sha256"] = "0" * 64
    path.write_text(json.dumps(value))
    assert run(env).returncode == 2
    assert not (workspace / "review pack").exists()


def test_symlink_inputs_and_parent_paths_are_refused(tmp_path):
    workspace, env = setup(tmp_path)
    (workspace / "alias.json").symlink_to(workspace / "legitimate.json")
    env["AAU_EVAL_CANDIDATE"] = "alias.json"
    assert run(env).returncode == 2
    env["AAU_EVAL_CANDIDATE"] = "legitimate.json"
    (workspace / "linked").symlink_to(workspace, target_is_directory=True)
    env["AAU_EVAL_OUTPUT"] = "linked/review"
    assert run(env).returncode == 2


def test_shell_looking_filename_is_data_not_an_executable_command(tmp_path):
    workspace, env = setup(tmp_path)
    filename = "candidate$(touch should-not-exist).json"
    (workspace / filename).write_bytes((workspace / "legitimate.json").read_bytes())
    env["AAU_EVAL_CANDIDATE"] = filename
    assert run(env).returncode == 0
    assert not (workspace / "should-not-exist").exists()
    metadata = (DRIVER.parent / "action.yml").read_text()
    assert 'run: python "$GITHUB_ACTION_PATH/run.py"' in metadata
    assert "run: ${{" not in metadata


def test_invalid_source_does_not_echo_payload_to_action_logs(tmp_path):
    workspace, env = setup(tmp_path)
    (workspace / "legitimate.json").write_text('{"payload": "SENSITIVE_EXAMPLE", invalid}')
    result = run(env)
    assert result.returncode == 2
    assert "SENSITIVE_EXAMPLE" not in result.stdout + result.stderr
