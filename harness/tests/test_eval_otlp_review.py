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
from aau_harness.eval_otlp import verify_otlp_pack
from aau_harness.eval_otlp_review import create_handoff, handoff_payloads, verify_handoff
from aau_harness.eval_pack import verify_pack


ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / ".github/actions/aau-evaluation-review/run.py"


def inputs(outcome="repaired"):
    path = ROOT / "harness/examples/evaluation-review/otlp_handoff.py"
    spec = importlib.util.spec_from_file_location("otlp_handoff_demo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.inputs(outcome)


@pytest.mark.parametrize("outcome,policy_status,budget_status", [
    ("earlier-harm", "constraints_not_met", "constraints_not_met"),
    ("slow-completion", "constraints_met", "constraints_not_met"),
    ("repaired", "constraints_met", "constraints_met"),
    ("unknown", "constraints_met", "constraints_not_verified")])
@pytest.mark.parametrize("gated", [False, True])
def test_complete_original_trace_chain_and_independent_verdicts(tmp_path, outcome, policy_status, budget_status, gated):
    args, budget = inputs(outcome)
    original = deepcopy(args)
    folder = tmp_path / "handoff"
    result = create_handoff(*args, folder, operating_budget=budget if gated else None)
    assert args == original and verify_handoff(folder, require_budget=gated) == result
    assert len([p for p in folder.rglob("*") if p.is_file()]) == (39 if gated else 36)
    assert json.loads((folder / "review/review.json").read_text())["status"] == policy_status
    if gated:
        assert result["policy_status"] == policy_status and result["candidate_budget_status"] == budget_status
    assert result["status"] == (policy_status if not gated or policy_status != "constraints_met" else budget_status)
    for side, raw in (("baseline", args[2]), ("candidate", args[4])):
        assert (folder / side / "source.otlp").read_bytes() == raw
        assert result["sources"][side]["source_sha256"] == digest(raw)
        assert result["sources"][side]["excluded_span_count"] == 1
        verify_otlp_pack(folder / side, evaluation_path=folder / f"review/{side}.json")
    verify_pack(folder / "review", require_recordings=True, require_diagnostics=True, require_budget=gated)
    assert handoff_payloads(*args, operating_budget=budget if gated else None) == handoff_payloads(
        *args, operating_budget=budget if gated else None)


@pytest.mark.parametrize("member", sorted(handoff_payloads(*inputs()[0], operating_budget=inputs()[1])[1]))
def test_all_members_recompute_despite_outer_manifest_rehash(tmp_path, member):
    args, budget = inputs()
    folder = tmp_path / "handoff"
    create_handoff(*args, folder, operating_budget=budget)
    target = folder / member
    target.write_bytes(target.read_bytes() + b' ')
    if member != "manifest.json":
        manifest = json.loads((folder / "manifest.json").read_text())
        manifest["files"][member] = digest(target.read_bytes())
        (folder / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        verify_handoff(folder)


@pytest.mark.parametrize("replacement", ["baseline", "candidate", "review"])
def test_individually_valid_substitutions_do_not_replace_the_linked_source_chain(tmp_path, replacement):
    args, budget = inputs()
    original, alternate = tmp_path / "original", tmp_path / "alternate"
    create_handoff(*args, original, operating_budget=budget)
    args[1]["accounting_plan"]["source_label"] = "Different baseline declaration"
    args[3]["accounting_plan"]["source_label"] = "Different candidate declaration"
    create_handoff(*args, alternate, operating_budget=budget)
    for path in (alternate / replacement).rglob("*"):
        if path.is_file():
            shutil.copyfile(path, original / replacement / path.relative_to(alternate / replacement))
    if replacement == "review":
        verify_pack(original / replacement, require_budget=True)
    else:
        verify_otlp_pack(original / replacement)
    manifest = json.loads((original / "manifest.json").read_text())
    for name in manifest["files"]:
        manifest["files"][name] = digest((original / name).read_bytes())
    (original / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match="does not recompute"):
        verify_handoff(original, require_budget=True)


@pytest.mark.parametrize("defect", ["attributes", "operating-map", "reducers", "context", "diagnostics", "missing-task"])
def test_noncomparable_or_incomplete_evidence_creates_no_output(tmp_path, defect):
    args, budget = inputs()
    mapping = args[3]
    if defect == "attributes":
        # Re-label the same numeric measurements while preserving a matching context.
        mapping["attributes"]["metrics"]["unauthorized"] = "new.score.unauthorized"
        doc = json.loads(args[4])
        for span in doc["resourceSpans"][0]["scopeSpans"][0]["spans"]:
            for attribute in span.get("attributes", []):
                if attribute["key"] == "example.score.unauthorized":
                    attribute["key"] = "new.score.unauthorized"
        args[4] = rendered(doc)
    elif defect == "operating-map":
        del mapping["attributes"]["operating"]["n_api_calls"]
    elif defect == "reducers":
        mapping["accounting_plan"]["metric_reducers"]["unauthorized"] = "last"
    elif defect == "context":
        mapping["accounting_plan"]["evaluation_context"]["config_sha256"] = "0" * 64
    elif defect == "diagnostics":
        args[5] = None
    else:
        mapping["tasks"].pop()
    with pytest.raises(AgentBomError):
        create_handoff(*args, tmp_path / "bad", operating_budget=budget)
    assert not (tmp_path / "bad").exists()


def test_different_export_serialization_is_allowed_but_original_bytes_remain(tmp_path):
    args, budget = inputs()
    args[3]["source_format"] = "otlp_jsonl"
    args[4] = json.dumps(json.loads(args[4])).encode() + b'\n'
    folder = tmp_path / "handoff"
    report = create_handoff(*args, folder, operating_budget=budget)
    assert report["status"] == "constraints_met" and verify_handoff(folder) == report
    assert (folder / "candidate/source.otlp").read_bytes() == args[4]


def test_cli_api_keeps_missing_context_visible_instead_of_fabricating_it(tmp_path):
    args, budget = inputs()
    for mapping in (args[1], args[3]):
        del mapping["accounting_plan"]["evaluation_context"]
    folder = tmp_path / "handoff"
    result = create_handoff(*args, folder, operating_budget=budget)
    assert result["status"] == "constraints_met" and verify_handoff(folder) == result
    review = json.loads((folder / "review/review.json").read_text())
    assert all(c["context_match"] == {"status": "unavailable", "missing_sources": ["baseline", "candidate"]}
               for c in review["comparisons"])
    assert 'Declared evaluation context: <strong>unavailable</strong>' in (folder / "review/review.html").read_text()


@pytest.mark.parametrize("defect", ["extra", "missing", "root-symlink", "group-symlink", "retry-symlink", "member-symlink", "large", "version"])
def test_exact_layout(tmp_path, defect):
    args, _ = inputs()
    folder = tmp_path / "pack"
    create_handoff(*args, folder)
    if defect == "extra":
        (folder / "candidate/retry/extra").write_text('x')
    elif defect == "missing":
        (folder / "candidate/source.otlp").unlink()
    elif defect.endswith("symlink"):
        target = {"root-symlink": folder, "group-symlink": folder / "candidate",
                  "retry-symlink": folder / "candidate/retry", "member-symlink": folder / "candidate/source.otlp"}[defect]
        moved = tmp_path / "moved"
        target.rename(moved)
        target.symlink_to(moved, target_is_directory=moved.is_dir())
    elif defect == "large":
        (folder / "candidate/source.otlp").write_bytes(b'x' * 2_000_001)
    else:
        (folder / "manifest.json").write_text('{"pack_version":"future"}')
    with pytest.raises(AgentBomError):
        verify_handoff(folder)


def test_cli_failures_downgrade_and_overwrite_refusal(tmp_path, monkeypatch):
    args, budget = inputs("slow-completion")
    names = ["policy", "baseline-map", "baseline", "candidate-map", "candidate", "diagnostics", "budget"]
    for name, value in zip(names, [*args, budget]):
        (tmp_path / name).write_bytes(value if isinstance(value, bytes) else rendered(value))
    monkeypatch.chdir(tmp_path)
    command = ["otlp-review", "create", *names[:5], "--diagnostics", "diagnostics"]
    assert main([*command, "--out", "ungated"]) == 0
    assert main(["otlp-review", "verify", "ungated", "--require-budget"]) == 2
    assert main([*command, "--operating-budget", "budget", "--out", "gated"]) == 1
    assert main(["otlp-review", "verify", "gated", "--require-budget"]) == 1
    assert main([*command, "--out", "ungated"]) == 2


def setup_action(tmp_path, outcome="repaired", gated=True):
    args, budget = inputs(outcome)
    workspace = tmp_path / "workspace with spaces"
    workspace.mkdir()
    env = {key: value for key, value in os.environ.items() if not key.startswith("AAU_EVAL_")}
    env.update(GITHUB_WORKSPACE=str(workspace), GITHUB_STEP_SUMMARY=str(tmp_path / "summary.md"),
               AAU_EVAL_INPUT_FORMAT="otlp", AAU_EVAL_OUTPUT="trace handoff")
    keys = ["POLICY", "BASELINE_PLAN", "BASELINE", "CANDIDATE_PLAN", "CANDIDATE", "DIAGNOSTICS"]
    if gated:
        keys.append("OPERATING_BUDGET")
        args.append(budget)
    for key, value in zip(keys, args):
        raw = value if isinstance(value, bytes) else rendered(value)
        path = f"{key.lower()}.json"
        (workspace / path).write_bytes(raw)
        env[f"AAU_EVAL_{key}"] = path
        if key != "CANDIDATE":
            env[f"AAU_EVAL_{key}_SHA256"] = digest(raw)
    return workspace, env


def run_action(env):
    return subprocess.run([sys.executable, str(DRIVER)], env=env, capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("outcome,code", [("repaired", 0), ("earlier-harm", 1), ("slow-completion", 1), ("unknown", 1)])
@pytest.mark.parametrize("gated", [False, True])
def test_action_verifies_full_chain_without_source_echo(tmp_path, outcome, code, gated):
    workspace, env = setup_action(tmp_path, outcome, gated)
    result = run_action(env)
    expected = code if gated or outcome == "earlier-harm" else 0
    assert result.returncode == expected, result.stderr
    report = verify_handoff(workspace / "trace handoff", require_budget=gated)
    assert (report["status"] == "constraints_met") == (expected == 0)
    summary = (tmp_path / "summary.md").read_text()
    assert f"all {39 if gated else 36} files recomputed" in summary and "Attribute maps" in summary
    for private in ("000000000000000f", "example.score", "Nested diagnostic detail", "unauthorized", "0.25"):
        assert private not in summary + result.stdout + result.stderr
    assert run_action(env).returncode == 2


@pytest.mark.parametrize("key", ["POLICY", "BASELINE", "BASELINE_PLAN", "CANDIDATE_PLAN", "DIAGNOSTICS", "OPERATING_BUDGET"])
@pytest.mark.parametrize("defect", ["missing-pin", "byte-drift"])
def test_action_requires_all_independent_approvals(tmp_path, key, defect):
    workspace, env = setup_action(tmp_path)
    if defect == "missing-pin":
        del env[f"AAU_EVAL_{key}_SHA256"]
    else:
        path = workspace / env[f"AAU_EVAL_{key}"]
        path.write_bytes(path.read_bytes() + b'\n')
    assert run_action(env).returncode == 2
    assert not (workspace / "trace handoff").exists()


@pytest.mark.parametrize("defect", ["missing-context", "different-context", "different-map", "different-reducer", "no-diagnostics", "annotation"])
def test_action_refuses_approved_but_incompatible_definitions(tmp_path, defect):
    workspace, env = setup_action(tmp_path)
    path = workspace / "candidate_plan.json"
    mapping = json.loads(path.read_text())
    if defect == "missing-context":
        del mapping["accounting_plan"]["evaluation_context"]
    elif defect == "different-context":
        mapping["accounting_plan"]["evaluation_context"]["config_sha256"] = "0" * 64
    elif defect == "different-map":
        del mapping["attributes"]["operating"]["n_api_calls"]
    elif defect == "different-reducer":
        mapping["accounting_plan"]["metric_reducers"]["unauthorized"] = "last"
    elif defect == "no-diagnostics":
        del env["AAU_EVAL_DIAGNOSTICS"]
        del env["AAU_EVAL_DIAGNOSTICS_SHA256"]
    path.write_bytes(rendered(mapping))
    if defect == "annotation":
        path.write_bytes(b'::error::PRIVATE_TRACE_PAYLOAD')
    env["AAU_EVAL_CANDIDATE_PLAN_SHA256"] = digest(path.read_bytes())
    result = run_action(env)
    assert result.returncode == 2
    assert "PRIVATE_TRACE_PAYLOAD" not in result.stdout + result.stderr
    assert "::error::" not in result.stdout + result.stderr
    assert not (workspace / "trace handoff").exists()


@pytest.mark.parametrize("key", ["BASELINE_PLAN", "CANDIDATE_PLAN", "BASELINE", "CANDIDATE"])
@pytest.mark.parametrize("path", ["../outside", "/tmp/outside", "bad\npath", "alias"])
def test_action_path_boundaries(tmp_path, key, path):
    workspace, env = setup_action(tmp_path)
    (workspace / "alias").symlink_to(workspace / env[f"AAU_EVAL_{key}"])
    env[f"AAU_EVAL_{key}"] = path
    assert run_action(env).returncode == 2
    assert not (workspace / "trace handoff").exists()
