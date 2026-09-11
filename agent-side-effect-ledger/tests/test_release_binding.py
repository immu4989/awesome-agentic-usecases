import argparse
import json
import shutil
import sys
from pathlib import Path

import pytest

from aau_harness.agent_bom import generate_conformance_suite, run_conformance
from aau_release_binding import BindingError, build_pack, validate_plan, verify_pack


ROOT = Path(__file__).parents[1]
REFERENCE = ROOT / "examples" / "reference-release-binding-pack"


def _workspace(tmp_path: Path) -> tuple[Path, argparse.Namespace]:
    workspace = tmp_path / "workspace"
    (workspace / "agent-side-effect-ledger" / "examples").mkdir(parents=True)
    for name in (
        "reference_adapter.py",
        "reference_crash_adapter.py",
        "reference_race_adapter.py",
        "reference-runtime-policy.json",
    ):
        shutil.copyfile(
            ROOT / "examples" / name,
            workspace / "agent-side-effect-ledger" / "examples" / name,
        )
    for name in ("aau_side_effect.py", "aau_crash_lab.py", "aau_race_lab.py"):
        shutil.copyfile(ROOT / name, workspace / "agent-side-effect-ledger" / name)
    release_source = ROOT / "examples" / "release-binding"
    release_target = (
        workspace / "agent-side-effect-ledger" / "examples" / "release-binding"
    )
    release_target.mkdir()
    for name in (
        "agent-capability-bom.json",
        "authority-conformance-suite.json",
        "authority-conformance-receipt.json",
        "binding-plan.json",
        "reference_authority_adapter.py",
    ):
        shutil.copyfile(release_source / name, release_target / name)
    shutil.copytree(ROOT / "examples" / "reference-matrix-pack", workspace / "matrix")
    args = argparse.Namespace(
        workspace=workspace,
        bom=Path(
            "agent-side-effect-ledger/examples/release-binding/agent-capability-bom.json"
        ),
        matrix=Path("matrix"),
        plan=Path("agent-side-effect-ledger/examples/release-binding/binding-plan.json"),
        out=Path("binding-pack"),
    )
    return workspace, args


def _refresh_authority_conformance(
    workspace: Path, args: argparse.Namespace
) -> None:
    bom_path = workspace / args.bom
    root = bom_path.parent
    suite_path = root / "authority-conformance-suite.json"
    receipt_path = root / "authority-conformance-receipt.json"
    adapter_path = root / "reference_authority_adapter.py"
    bom = json.loads(bom_path.read_text())
    suite = generate_conformance_suite(bom)
    receipt = run_conformance(
        bom,
        suite,
        "command",
        f"{sys.executable} {adapter_path}",
        adapter_artifact=adapter_path,
        workspace=workspace,
    )
    suite_path.write_text(json.dumps(suite, indent=2) + "\n")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_reference_release_binding_is_exact_and_reproducible(tmp_path):
    workspace, args = _workspace(tmp_path)
    receipt = build_pack(args)
    assert receipt["status"] == "evidence_bound"
    assert receipt["consequential_relationship_count"] == 1
    assert receipt["fully_bound_consequential_relationship_count"] == 1
    assert receipt["matrix_boundary"] == {
        "tool_id": "notification-service",
        "operation": "send_synthetic_notice",
        "resource_scope": "synthetic-benefit-cases/notices/*",
    }
    expected_authority = {
        "receipt_version": "aau-agent-authority-conformance-receipt/1.2",
        "status": "evidence_passed",
        "adapter_kind": "command",
        "case_count": 8,
        "exact_count": 8,
        "clean_twin_relationship_count": 1,
        "matrix_relationship_clean_twin_exact": True,
        "adapter_path_matches_receipt": True,
        "adapter_bytes_match_receipt": True,
    }
    assert {
        key: receipt["authority_conformance"][key] for key in expected_authority
    } == expected_authority
    assert receipt["findings"] == []
    adapters = receipt["bindings"][0]["adapters"].values()
    assert sum(adapter["runtime_material_count"] for adapter in adapters) == 11
    assert sum(adapter["runtime_only_material_count"] for adapter in adapters) == 3
    assert all(adapter["runtime_materials_match_matrix"] for adapter in adapters)
    assert verify_pack(workspace / "binding-pack") == receipt
    assert _files(workspace / "binding-pack") == _files(REFERENCE)


def test_binding_holds_when_consequential_authority_omits_approval(tmp_path):
    workspace, args = _workspace(tmp_path)
    bom_path = workspace / args.bom
    bom = json.loads(bom_path.read_text())
    bom["authorities"][0]["human_approval_required"] = False
    bom_path.write_text(json.dumps(bom, indent=2) + "\n")
    _refresh_authority_conformance(workspace, args)
    receipt = build_pack(args)
    assert receipt["status"] == "binding_held"
    assert receipt["fully_bound_consequential_relationship_count"] == 0
    assert [item["code"] for item in receipt["findings"]] == [
        "HUMAN_APPROVAL_NOT_REQUIRED"
    ]
    assert verify_pack(workspace / "binding-pack") == receipt


def test_binding_holds_when_authority_adapter_bytes_differ_from_receipt(tmp_path):
    workspace, args = _workspace(tmp_path)
    adapter = (
        workspace
        / "agent-side-effect-ledger"
        / "examples"
        / "release-binding"
        / "reference_authority_adapter.py"
    )
    adapter.write_text(adapter.read_text() + "\n# substituted after conformance\n")

    receipt = build_pack(args)

    assert receipt["status"] == "binding_held"
    assert receipt["fully_bound_consequential_relationship_count"] == 0
    assert [item["code"] for item in receipt["findings"]] == [
        "AUTHORITY_ADAPTER_BYTES_DIFFER_FROM_RECEIPT"
    ]
    assert not receipt["authority_conformance"]["adapter_bytes_match_receipt"]
    assert verify_pack(workspace / "binding-pack") == receipt


def test_binding_holds_when_bound_authority_adapter_fails_twins(tmp_path):
    workspace, args = _workspace(tmp_path)
    root = (workspace / args.bom).parent
    adapter = root / "reference_authority_adapter.py"
    adapter.write_text(
        "import json,sys\njson.load(sys.stdin)\n"
        "json.dump({'decision':'block','reason_codes':['DENY_ALL']},sys.stdout)\n"
    )
    bom = json.loads((workspace / args.bom).read_text())
    suite = json.loads((root / "authority-conformance-suite.json").read_text())
    failed = run_conformance(
        bom,
        suite,
        "command",
        f"{sys.executable} {adapter}",
        adapter_artifact=adapter,
        workspace=workspace,
    )
    (root / "authority-conformance-receipt.json").write_text(
        json.dumps(failed, indent=2) + "\n"
    )

    receipt = build_pack(args)

    assert receipt["status"] == "binding_held"
    assert receipt["fully_bound_consequential_relationship_count"] == 0
    assert {item["code"] for item in receipt["findings"]} == {
        "AUTHORITY_CONFORMANCE_NOT_PASSING",
        "CONSEQUENTIAL_RELATIONSHIP_AUTHORITY_CLEAN_TWIN_MISSING",
    }
    assert receipt["authority_conformance"]["adapter_bytes_match_receipt"]
    assert not receipt["authority_conformance"][
        "matrix_relationship_clean_twin_exact"
    ]
    assert verify_pack(workspace / "binding-pack") == receipt


def test_binding_holds_when_aabom_relationship_is_not_fully_stressed(tmp_path):
    workspace, args = _workspace(tmp_path)
    bom_path = workspace / args.bom
    bom = json.loads(bom_path.read_text())
    bom["tools"][0]["operations"].append("send_other_notice")
    bom["tools"][0]["operation_scope_bindings"].append(
        {
            "operation": "send_other_notice",
            "resource_scopes": ["synthetic-benefit-cases/notices/*"],
        }
    )
    bom["authorities"][0]["operations"].append("send_other_notice")
    bom["authorities"][0]["operation_scope_bindings"].append(
        {
            "tool_id": "notification-service",
            "operation": "send_other_notice",
            "resource_scopes": ["synthetic-benefit-cases/notices/*"],
        }
    )
    bom_path.write_text(json.dumps(bom, indent=2) + "\n")
    _refresh_authority_conformance(workspace, args)
    receipt = build_pack(args)
    assert receipt["status"] == "binding_held"
    assert receipt["consequential_relationship_count"] == 2
    assert receipt["fully_bound_consequential_relationship_count"] == 1
    assert {item["code"] for item in receipt["findings"]} == {
        "CONSEQUENTIAL_RELATIONSHIP_NOT_FULLY_STRESSED",
        "CONSEQUENTIAL_RELATIONSHIP_NOT_IN_PLAN",
    }


def test_binding_does_not_infer_authority_from_separate_operation_and_scope_lists(
    tmp_path,
):
    workspace, args = _workspace(tmp_path)
    bom_path = workspace / args.bom
    bom = json.loads(bom_path.read_text())
    second_scope = "synthetic-benefit-cases/notices/restricted/*"
    bom["tools"][0]["resource_scopes"].append(second_scope)
    bom["tools"][0]["operation_scope_bindings"][0]["resource_scopes"].append(
        second_scope
    )
    bom_path.write_text(json.dumps(bom, indent=2) + "\n")
    _refresh_authority_conformance(workspace, args)
    plan_path = workspace / args.plan
    plan = json.loads(plan_path.read_text())
    plan["bindings"][0]["resource_scope"] = second_scope
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")

    receipt = build_pack(args)

    assert receipt["status"] == "binding_held"
    assert receipt["bindings"][0]["authority_ids"] == []
    assert {
        "CONSEQUENTIAL_RELATIONSHIP_AUTHORITY_MISSING",
        "CONSEQUENTIAL_RELATIONSHIP_NOT_FULLY_STRESSED",
        "CONSEQUENTIAL_RELATIONSHIP_NOT_IN_PLAN",
        "MATRIX_BOUNDARY_NOT_IN_PLAN",
    } <= {item["code"] for item in receipt["findings"]}


def test_binding_holds_when_aabom_does_not_hash_exact_matrix_manifest(tmp_path):
    workspace, args = _workspace(tmp_path)
    bom_path = workspace / args.bom
    bom = json.loads(bom_path.read_text())
    bom["evidence"][0]["sha256"] = "0" * 64
    bom_path.write_text(json.dumps(bom, indent=2) + "\n")
    _refresh_authority_conformance(workspace, args)
    receipt = build_pack(args)
    assert receipt["status"] == "binding_held"
    assert receipt["fully_bound_consequential_relationship_count"] == 0
    assert [item["code"] for item in receipt["findings"]] == [
        "AABOM_MATRIX_EVIDENCE_NOT_BOUND"
    ]


def test_binding_holds_when_release_adapter_bytes_differ_from_matrix(tmp_path):
    workspace, args = _workspace(tmp_path)
    adapter = (
        workspace
        / "agent-side-effect-ledger"
        / "examples"
        / "reference_race_adapter.py"
    )
    adapter.write_bytes(adapter.read_bytes() + b"\n# release substitution\n")
    receipt = build_pack(args)
    assert receipt["status"] == "binding_held"
    assert receipt["fully_bound_consequential_relationship_count"] == 0
    assert [item["code"] for item in receipt["findings"]] == [
        "ADAPTER_BYTES_DIFFER_FROM_MATRIX",
        "ADAPTER_MATERIALS_DIFFER_FROM_MATRIX",
        "RUNTIME_MATERIALS_DIFFER_FROM_MATRIX",
    ]
    binding = receipt["bindings"][0]
    assert not binding["all_adapters_match_matrix"]
    assert not binding["adapters"]["race"]["matches_matrix"]
    assert binding["adapters"]["semantic"]["matches_matrix"]
    assert binding["adapters"]["crash"]["matches_matrix"]
    assert verify_pack(workspace / "binding-pack") == receipt


def test_binding_holds_when_imported_local_material_differs_from_matrix(tmp_path):
    workspace, args = _workspace(tmp_path)
    imported = workspace / "agent-side-effect-ledger" / "aau_race_lab.py"
    imported.write_bytes(imported.read_bytes() + b"\n# release substitution\n")

    receipt = build_pack(args)

    assert receipt["status"] == "binding_held"
    assert receipt["fully_bound_consequential_relationship_count"] == 0
    assert [item["code"] for item in receipt["findings"]] == [
        "ADAPTER_MATERIALS_DIFFER_FROM_MATRIX",
        "RUNTIME_MATERIALS_DIFFER_FROM_MATRIX",
    ]
    race = receipt["bindings"][0]["adapters"]["race"]
    assert race["sha256"] == race["matrix_sha256"]
    assert not race["material_set_matches_matrix"]
    assert not race["matches_matrix"]
    assert verify_pack(workspace / "binding-pack") == receipt


def test_binding_holds_runtime_policy_substitution_with_source_unchanged(tmp_path):
    workspace, args = _workspace(tmp_path)
    policy = (
        workspace
        / "agent-side-effect-ledger"
        / "examples"
        / "reference-runtime-policy.json"
    )
    policy.write_text(
        '{"policy_id":"substituted","environment":"public_synthetic",'
        '"live_targets_allowed":false}\n'
    )

    receipt = build_pack(args)

    assert receipt["status"] == "binding_held"
    assert receipt["fully_bound_consequential_relationship_count"] == 0
    assert [item["code"] for item in receipt["findings"]] == [
        "RUNTIME_MATERIALS_DIFFER_FROM_MATRIX",
        "RUNTIME_MATERIALS_DIFFER_FROM_MATRIX",
        "RUNTIME_MATERIALS_DIFFER_FROM_MATRIX",
    ]
    for adapter in receipt["bindings"][0]["adapters"].values():
        assert adapter["sha256"] == adapter["matrix_sha256"]
        assert adapter["material_set_matches_matrix"]
        assert not adapter["runtime_materials_match_matrix"]
        assert not adapter["matches_matrix"]
    assert verify_pack(workspace / "binding-pack") == receipt


def test_one_executable_may_implement_all_three_adapter_roles(tmp_path):
    workspace, args = _workspace(tmp_path)
    plan_path = workspace / args.plan
    plan = json.loads(plan_path.read_text())
    shared = plan["bindings"][0]["semantic_adapter"]
    plan["bindings"][0]["crash_adapter"] = shared
    plan["bindings"][0]["race_adapter"] = shared
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    validate_plan(plan)


def test_binding_rejects_plan_release_mismatch_and_output_escape(tmp_path):
    workspace, args = _workspace(tmp_path)
    plan_path = workspace / args.plan
    plan = json.loads(plan_path.read_text())
    plan["release_id"] = "different-release"
    plan_path.write_text(json.dumps(plan))
    with pytest.raises(BindingError, match="release_id does not match"):
        build_pack(args)

    _workspace_two, args_two = _workspace(tmp_path / "second")
    args_two.out = Path("../escaped")
    with pytest.raises(BindingError, match="remain inside"):
        build_pack(args_two)


def test_binding_rejects_overwrite_tampering_and_extra_files(tmp_path):
    workspace, args = _workspace(tmp_path)
    build_pack(args)
    with pytest.raises(BindingError, match="overwrite"):
        build_pack(args)

    adapter = workspace / "binding-pack" / "adapters" / "001-race.artifact"
    adapter.write_bytes(adapter.read_bytes() + b"\n# changed\n")
    with pytest.raises(BindingError, match="receipt does not recompute"):
        verify_pack(workspace / "binding-pack")

    workspace_two, args_two = _workspace(tmp_path / "second")
    build_pack(args_two)
    (workspace_two / "binding-pack" / "unexpected.txt").write_text("unexpected")
    with pytest.raises(BindingError, match="missing or extra"):
        verify_pack(workspace_two / "binding-pack")

    workspace_three, args_three = _workspace(tmp_path / "third")
    build_pack(args_three)
    (workspace_three / "binding-pack" / "empty-extra").mkdir()
    with pytest.raises(BindingError, match="missing or extra directories"):
        verify_pack(workspace_three / "binding-pack")


def test_reference_pack_is_self_contained(tmp_path):
    copied = tmp_path / "moved"
    shutil.copytree(REFERENCE, copied)
    receipt = verify_pack(copied)
    assert receipt["status"] == "evidence_bound"
    assert receipt["claim_boundary"]["source_paths_are_declarations_not_provenance"]


def test_release_binding_action_preserves_valid_hold_diagnostics():
    action = (
        ROOT.parent
        / ".github"
        / "actions"
        / "aau-side-effect-release-binding"
        / "action.yml"
    ).read_text()
    assert "set +e" in action
    assert 'cat "$AAU_BINDING_OUTPUT/README.md"' in action
    assert 'exit "$binding_status"' in action
    assert "github.event" not in action
    assert "AAU_BINDING_BOM" in action
    assert "AAU_BINDING_MATRIX" in action
    assert "AAU_BINDING_PLAN" in action
