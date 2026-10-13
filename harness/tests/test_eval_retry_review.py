from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from aau_harness.agent_bom import AgentBomError, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_pack import verify_pack
from aau_harness.eval_retries import verify_retry_pack
from aau_harness.eval_retry_review import create_handoff, handoff_payloads, verify_handoff


ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / ".github/actions/aau-evaluation-review/run.py"


def inputs(outcome="repaired"):
    path = ROOT / "harness/examples/evaluation-review/retry_handoff.py"
    spec = importlib.util.spec_from_file_location("retry_handoff_demo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    policy, plan, ledger, diagnostics, budget, candidates = module.demo_inputs()
    candidate = candidates[outcome] if outcome != "unknown" else candidates["repaired"]
    if outcome == "unknown":
        del candidate["tasks"][0]["attempts"][0]["cost_usd"]
    return [policy, plan, ledger, deepcopy(plan), candidate, diagnostics], budget


@pytest.mark.parametrize("outcome,policy_status,budget_status", [
    ("earlier-harm", "constraints_not_met", "constraints_not_met"),
    ("slow-completion", "constraints_met", "constraints_not_met"),
    ("repaired", "constraints_met", "constraints_met"),
    ("unknown", "constraints_met", "constraints_not_verified")])
@pytest.mark.parametrize("gated", [False, True])
def test_complete_handoff_retains_source_chain_and_independent_outcomes(tmp_path, outcome, policy_status, budget_status, gated):
    args, budget = inputs(outcome)
    original = deepcopy(args)
    folder = tmp_path / "handoff"
    report = create_handoff(*args, folder, operating_budget=budget if gated else None)
    assert args == original and report == verify_handoff(folder, require_budget=gated)
    assert len([p for p in folder.rglob("*") if p.is_file()]) == (31 if gated else 28)
    assert json.loads((folder / "review/review.json").read_text())["status"] == policy_status
    if gated:
        assert report["candidate_budget_status"] == budget_status and report["policy_status"] == policy_status
    assert report["status"] == (policy_status if not gated or policy_status != "constraints_met" else budget_status)
    for side in ("baseline", "candidate"):
        verify_retry_pack(folder / side, evaluation_path=folder / f"review/{side}.json")
        assert report["sources"][side]["task_count"] == 2
        assert report["sources"][side]["attempt_count"] == 4
    assert verify_pack(folder / "review", require_recordings=True, require_diagnostics=True,
                       require_budget=gated)["status"] == report["status"]
    assert handoff_payloads(*args, operating_budget=budget if gated else None) == handoff_payloads(
        *args, operating_budget=budget if gated else None)


@pytest.mark.parametrize("member", sorted(handoff_payloads(*inputs()[0], operating_budget=inputs()[1])[1]))
def test_every_member_recomputed_after_outer_manifest_rehash(tmp_path, member):
    args, budget = inputs()
    folder = tmp_path / "handoff"
    create_handoff(*args, folder, operating_budget=budget)
    path = folder / member
    path.write_bytes(path.read_bytes() + b" ")
    if member != "manifest.json":
        manifest = json.loads((folder / "manifest.json").read_text())
        manifest["files"][member] = digest(path.read_bytes())
        (folder / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        verify_handoff(folder)


@pytest.mark.parametrize("replacement", ["baseline", "candidate", "review"])
def test_valid_unrelated_nested_components_cannot_replace_original_chain(tmp_path, replacement):
    args, budget = inputs()
    original, alternate = tmp_path / "original", tmp_path / "alternate"
    create_handoff(*args, original, operating_budget=budget)
    args[1]["source_label"] = "different baseline"
    args[3]["source_label"] = "different candidate"
    create_handoff(*args, alternate, operating_budget=budget)
    for path in (alternate / replacement).iterdir():
        shutil.copyfile(path, original / replacement / path.name)
    if replacement == "review":
        verify_pack(original / "review", require_budget=True)
    else:
        verify_retry_pack(original / replacement)
    manifest = json.loads((original / "manifest.json").read_text())
    for name in manifest["files"]:
        manifest["files"][name] = digest((original / name).read_bytes())
    (original / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match="does not recompute"):
        verify_handoff(original, require_budget=True)


@pytest.mark.parametrize("defect", ["reducers", "missing-diagnostics", "bad-diagnostics", "missing-task", "context"])
def test_invalid_or_noncomparable_inputs_never_create_output(tmp_path, defect):
    args, budget = inputs()
    if defect == "reducers":
        args[3]["metric_reducers"]["unauthorized"] = "last"
        assert args[1]["evaluation_context"] == args[3]["evaluation_context"]
    elif defect == "missing-diagnostics":
        args[5] = None
    elif defect == "bad-diagnostics":
        args[5]["draw_sizes"] = [999]
    elif defect == "missing-task":
        args[4]["tasks"].pop()
    else:
        args[3]["evaluation_context"]["config_sha256"] = "0" * 64
    with pytest.raises(AgentBomError):
        create_handoff(*args, tmp_path / "bad", operating_budget=budget)
    assert not (tmp_path / "bad").exists()


def test_cli_preserves_failures_refuses_downgrades_and_never_overwrites(tmp_path, monkeypatch):
    args, budget = inputs("slow-completion")
    names = ["policy", "baseline-plan", "baseline", "candidate-plan", "candidate", "diagnostics", "budget"]
    for name, value in zip(names, [*args, budget]):
        (tmp_path / f"{name}.json").write_bytes(rendered(value))
    monkeypatch.chdir(tmp_path)
    command = ["retry-review", "create", *[f"{n}.json" for n in names[:5]], "--diagnostics", "diagnostics.json"]
    assert main([*command, "--out", "ungated"]) == 0
    assert main(["retry-review", "verify", "ungated", "--require-budget"]) == 2
    assert main([*command, "--operating-budget", "budget.json", "--out", "gated"]) == 1
    assert main(["retry-review", "verify", "gated", "--require-budget"]) == 1
    assert main([*command, "--out", "ungated"]) == 2
    Path("gated/README.txt").write_text("tampered")
    assert main(["retry-review", "verify", "gated"]) == 2


@pytest.mark.parametrize("defect", ["extra", "missing", "group-symlink", "member-symlink", "oversized", "version"])
def test_exact_pack_layout(tmp_path, defect):
    args, _ = inputs()
    folder = tmp_path / "pack"
    create_handoff(*args, folder)
    if defect == "extra":
        (folder / "candidate/extra").write_text("extra")
    elif defect == "missing":
        (folder / "candidate/ledger.json").unlink()
    elif defect in ("group-symlink", "member-symlink"):
        target = folder / ("candidate" if defect == "group-symlink" else "candidate/ledger.json")
        target.rename(tmp_path / "moved")
        target.symlink_to(tmp_path / "moved", target_is_directory=(tmp_path / "moved").is_dir())
    elif defect == "oversized":
        (folder / "README.txt").write_bytes(b"x" * 2_000_001)
    else:
        (folder / "manifest.json").write_text('{"pack_version":"future"}')
    with pytest.raises(AgentBomError):
        verify_handoff(folder)


def setup_action(tmp_path, outcome="repaired", gated=True):
    args, budget = inputs(outcome)
    workspace = tmp_path / "workspace with spaces"
    workspace.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith("AAU_EVAL_")}
    env.update(GITHUB_WORKSPACE=str(workspace), GITHUB_STEP_SUMMARY=str(tmp_path / "summary.md"),
               AAU_EVAL_INPUT_FORMAT="retries", AAU_EVAL_OUTPUT="retry handoff")
    keys = ["POLICY", "BASELINE_PLAN", "BASELINE", "CANDIDATE_PLAN", "CANDIDATE", "DIAGNOSTICS"]
    if gated:
        keys.append("OPERATING_BUDGET")
        args.append(budget)
    for key, value in zip(keys, args):
        filename = f"{key.lower()}.json"
        raw = rendered(value)
        (workspace / filename).write_bytes(raw)
        env[f"AAU_EVAL_{key}"] = filename
        if key != "CANDIDATE":
            env[f"AAU_EVAL_{key}_SHA256"] = digest(raw)
    return workspace, env


def run_action(env):
    return subprocess.run([sys.executable, str(DRIVER)], env=env, capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("outcome,code", [("repaired", 0), ("earlier-harm", 1), ("slow-completion", 1), ("unknown", 1)])
def test_action_full_chain_and_private_summary(tmp_path, outcome, code):
    workspace, env = setup_action(tmp_path, outcome)
    result = run_action(env)
    assert result.returncode == code, result.stderr
    report = verify_handoff(workspace / "retry handoff", require_budget=True)
    assert (report["status"] == "constraints_met") == (code == 0)
    summary = (tmp_path / "summary.md").read_text()
    assert "all 31 files recomputed" in summary and "Metric reducers match" in summary
    assert "task-0-call-0" not in summary and "unauthorized" not in summary and "0.25" not in summary
    assert run_action(env).returncode == 2


@pytest.mark.parametrize("key", ["POLICY", "BASELINE", "BASELINE_PLAN", "CANDIDATE_PLAN", "DIAGNOSTICS", "OPERATING_BUDGET"])
@pytest.mark.parametrize("defect", ["missing-pin", "byte-drift"])
def test_action_every_approval_is_independent(tmp_path, key, defect):
    workspace, env = setup_action(tmp_path)
    if defect == "missing-pin":
        del env[f"AAU_EVAL_{key}_SHA256"]
    else:
        path = workspace / env[f"AAU_EVAL_{key}"]
        path.write_bytes(path.read_bytes() + b"\n")
    assert run_action(env).returncode == 2
    assert not (workspace / "retry handoff").exists()


@pytest.mark.parametrize("defect", ["missing-context", "different-context", "different-reducer", "no-diagnostics", "annotation"])
def test_action_refuses_context_or_accounting_shortcuts_without_echoing_source(tmp_path, defect):
    workspace, env = setup_action(tmp_path)
    path = workspace / "candidate_plan.json"
    plan = json.loads(path.read_text())
    if defect == "missing-context":
        del plan["evaluation_context"]
    elif defect == "different-context":
        plan["evaluation_context"]["config_sha256"] = "0" * 64
    elif defect == "different-reducer":
        plan["metric_reducers"]["unauthorized"] = "last"
    elif defect == "no-diagnostics":
        del env["AAU_EVAL_DIAGNOSTICS"]
        del env["AAU_EVAL_DIAGNOSTICS_SHA256"]
    path.write_bytes(rendered(plan))
    if defect == "annotation":
        path.write_bytes(b"::error::PRIVATE_RETRY_INPUT")
    env["AAU_EVAL_CANDIDATE_PLAN_SHA256"] = digest(path.read_bytes())
    result = run_action(env)
    assert result.returncode == 2
    assert "PRIVATE_RETRY_INPUT" not in result.stdout + result.stderr
    assert "::error::" not in result.stdout + result.stderr
    assert not (workspace / "retry handoff").exists()


@pytest.mark.parametrize("key", ["BASELINE_PLAN", "CANDIDATE_PLAN", "BASELINE", "CANDIDATE"])
@pytest.mark.parametrize("value", ["../outside", "/tmp/outside", "bad\npath", "alias"])
def test_action_paths_cannot_escape_workspace(tmp_path, key, value):
    workspace, env = setup_action(tmp_path)
    (workspace / "alias").symlink_to(workspace / env[f"AAU_EVAL_{key}"])
    env[f"AAU_EVAL_{key}"] = value
    assert run_action(env).returncode == 2
    assert not (workspace / "retry handoff").exists()
