from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_matrix import create_matrix, matrix_payloads, verify_matrix


DEMO = Path(__file__).resolve().parents[1] / "examples/evaluation-review/matrix.py"
spec = importlib.util.spec_from_file_location("matrix_example", DEMO)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def test_matrix_retains_failures_and_tradeoffs_without_imputation_or_ranking(tmp_path):
    args = demo.matrix_inputs()
    original = deepcopy(args)
    report = create_matrix(*args, tmp_path / "pack")
    assert args == original
    assert report == verify_matrix(tmp_path / "pack")
    assert len(list((tmp_path / "pack").iterdir())) == 21
    rows = {row["candidate_id"]: row for row in report["candidates"]}
    assert rows["cheap-unsafe"]["exclusion_reasons"] == ["policy_constraints_not_met"]
    assert rows["unknown-cost"]["exclusion_reasons"] == ["incomplete_cost_coverage"]
    assert rows["unknown-cost"]["overall"]["cost"]["total_per_passing_attempt_usd"] is None
    assert report["operating_groups"] == [{"cost_basis": "synthetic",
        "eligible_candidates": ["balanced", "dominated", "fast"],
        "nondominated_recorded_candidates": ["balanced", "fast"]}]
    pair = next(row for row in report["pairwise_comparisons"] if row["left"] == "balanced" and row["right"] == "fast")
    assert pair["relationship"] == "recorded_tradeoff"
    assert matrix_payloads(*args) == matrix_payloads(*args)


def test_different_cost_bases_remain_separate_and_unknown_basis_is_excluded():
    plan, policy, baseline, candidates = demo.matrix_inputs()
    plan["cost_basis"]["balanced"] = "charge"
    plan["cost_basis"]["fast"] = "estimate"
    plan["cost_basis"]["dominated"] = "unknown"
    report = matrix_payloads(plan, policy, baseline, candidates)[0]
    assert {g["cost_basis"]: g["nondominated_recorded_candidates"] for g in report["operating_groups"]} == {
        "charge": ["balanced"], "estimate": ["fast"], "synthetic": []}
    pairs = report["pairwise_comparisons"]
    assert next(r for r in pairs if r["left"] == "balanced" and r["right"] == "fast")["reason"] == "different_declared_cost_bases"


def test_equal_points_remain_tied_not_alphabetically_selected():
    plan, policy, baseline, candidates = demo.matrix_inputs()
    candidates["fast"] = deepcopy(candidates["balanced"])
    report = matrix_payloads(plan, policy, baseline, candidates)[0]
    assert report["operating_groups"][0]["nondominated_recorded_candidates"] == ["balanced", "fast"]
    assert next(r for r in report["pairwise_comparisons"] if r["left"] == "balanced" and r["right"] == "fast")["relationship"] == "equal_recorded_axes"


def test_missing_latency_and_no_joint_success_are_not_eligible():
    plan, policy, baseline, candidates = demo.matrix_inputs()
    del candidates["balanced"]["results"][0]["latency_s"]
    plan["criteria"][0]["limit"] = 2
    report = matrix_payloads(plan, policy, baseline, candidates)[0]
    balanced = report["candidates"][0]
    assert balanced["policy_status"] == "constraints_met"
    assert balanced["exclusion_reasons"] == ["incomplete_latency_coverage", "no_jointly_passing_attempts"]
    assert all(not g["eligible_candidates"] for g in report["operating_groups"])


def test_cohort_failure_cannot_be_compensated_by_operating_cost():
    plan, policy, baseline, candidates = demo.matrix_inputs()
    policy.update(policy_version="aau-evaluation-review-policy/1.1", cohorts=[{
        "cohort_id": "stricter", "scenario_ids": policy["scenario_ids"],
        "metrics": [{**policy["metrics"][0], "candidate_observation_limit": 2}]}])
    report = matrix_payloads(plan, policy, baseline, candidates)[0]
    assert all(r["policy_status"] == "constraints_not_met" for r in report["candidates"])
    assert not report["operating_groups"][0]["eligible_candidates"]
    assert any("cohort_id" in failure for failure in report["candidates"][0]["failed_constraints"])


@pytest.mark.parametrize("defect", ["missing-context", "context-drift", "repeats", "duplicate-id", "missing-candidate",
                                    "extra-candidate", "extra-plan", "invalid-basis", "invalid-criteria"])
def test_incomparable_or_invalid_inputs_fail_before_output(tmp_path, defect):
    plan, policy, baseline, candidates = demo.matrix_inputs()
    if defect == "missing-context":
        del candidates["balanced"]["evaluation_context"]
    elif defect == "context-drift":
        candidates["balanced"]["evaluation_context"]["config_sha256"] = "0" * 64
    elif defect == "repeats":
        candidates["balanced"]["n_repeats"] = 3
        candidates["balanced"]["results"] = candidates["balanced"]["results"][:3]
    elif defect == "duplicate-id":
        plan["candidate_ids"][1] = plan["candidate_ids"][0]
    elif defect == "missing-candidate":
        del candidates["fast"]
    elif defect == "extra-candidate":
        candidates["extra"] = candidates["fast"]
    elif defect == "extra-plan":
        plan["weight_safety"] = 0
    elif defect == "invalid-basis":
        plan["cost_basis"]["fast"] = "verified-cheap"
    else:
        plan["criteria"] = []
    with pytest.raises(AgentBomError):
        create_matrix(plan, policy, baseline, candidates, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("name", sorted(matrix_payloads(*demo.matrix_inputs())[1]))
def test_every_source_and_derived_file_is_recomputed_even_if_rehashed(tmp_path, name):
    pack = tmp_path / "pack"
    create_matrix(*demo.matrix_inputs(), pack)
    path = pack / name
    path.write_bytes(path.read_bytes() + b" ")
    if name != "manifest.json":
        manifest = json.loads((pack / "manifest.json").read_text())
        manifest["files"][name] = digest(path.read_bytes())
        (pack / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        verify_matrix(pack)


@pytest.mark.parametrize("defect", ["missing", "extra", "symlink", "oversized"])
def test_invalid_pack_members_fail(tmp_path, defect):
    pack = tmp_path / "pack"
    create_matrix(*demo.matrix_inputs(), pack)
    if defect == "missing":
        (pack / "matrix.json").unlink()
    elif defect == "extra":
        (pack / "extra").write_text("x")
    elif defect == "oversized":
        (pack / "matrix.json").write_bytes(b"x" * 2_000_001)
    else:
        (pack / "matrix.json").rename(tmp_path / "target")
        (pack / "matrix.json").symlink_to(tmp_path / "target")
    with pytest.raises(AgentBomError):
        verify_matrix(pack)


def test_labels_are_escaped_and_never_used_as_filesystem_paths(tmp_path):
    plan, policy, baseline, candidates = demo.matrix_inputs()
    label = '../../<script>alert("x")</script>'
    candidates[label] = candidates.pop("balanced")
    plan["candidate_ids"][plan["candidate_ids"].index("balanced")] = label
    plan["cost_basis"][label] = plan["cost_basis"].pop("balanced")
    create_matrix(plan, policy, baseline, candidates, tmp_path / "pack")
    html = (tmp_path / "pack/matrix.html").read_text()
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert all(path.is_file() for path in (tmp_path / "pack").iterdir())
    assert "default-src &#39;none&#39;" in html


def test_complete_demo_and_cli_outside_checkout(tmp_path, monkeypatch):
    demo.build_demo(tmp_path / "demo")
    monkeypatch.chdir(tmp_path)
    assert main(["candidate-matrix", "verify", "demo/matrix"]) == 0
    args = ["candidate-matrix", "create", "demo/plan.json", "demo/policy.json", "demo/baseline.json"]
    for name in demo.matrix_inputs()[3]:
        args += ["--candidate", f"{name}=demo/{name}.json"]
    args += ["--out", "created"]
    assert main(args) == 0  # This is descriptive evidence, not a policy-pass gate.
    assert main(args) == 2
    assert main(["candidate-matrix", "verify", "created"]) == 0
