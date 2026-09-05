import argparse
import json
import shlex
import shutil
import sys
from pathlib import Path

import pytest

from aau_side_effect_matrix import MatrixError, PACK_FILES, run_pack, verify_pack


ROOT = Path(__file__).parents[1]
REFERENCE_PACK = ROOT / "examples" / "reference-matrix-pack"


def _command(path: Path) -> str:
    return shlex.join([sys.executable, str(path)])


def _workspace(tmp_path: Path) -> tuple[Path, argparse.Namespace]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    sources = {
        "semantic.json": ROOT / "examples" / "reference-suite.json",
        "crash.json": ROOT / "examples" / "crash-suite.json",
        "race.json": ROOT / "examples" / "race-suite.json",
    }
    for name, source in sources.items():
        shutil.copyfile(source, workspace / name)
    adapter_root = workspace / "agent-side-effect-ledger" / "examples"
    adapter_root.mkdir(parents=True)
    adapters = {
        "reference_adapter.py": ROOT / "examples" / "reference_adapter.py",
        "reference_crash_adapter.py": ROOT / "examples" / "reference_crash_adapter.py",
        "reference_race_adapter.py": ROOT / "examples" / "reference_race_adapter.py",
    }
    for name, source in adapters.items():
        shutil.copyfile(source, adapter_root / name)
    shutil.copyfile(
        ROOT / "examples" / "reference-runtime-policy.json",
        adapter_root / "reference-runtime-policy.json",
    )
    for name in ("aau_side_effect.py", "aau_crash_lab.py", "aau_race_lab.py"):
        shutil.copyfile(ROOT / name, workspace / "agent-side-effect-ledger" / name)
    semantic_adapter = adapter_root / "reference_adapter.py"
    crash_adapter = adapter_root / "reference_crash_adapter.py"
    race_adapter = adapter_root / "reference_race_adapter.py"
    args = argparse.Namespace(
        workspace=workspace,
        out=Path("pack"),
        semantic_suite=Path("semantic.json"),
        semantic_adapter_command=_command(semantic_adapter),
        semantic_adapter_artifact=semantic_adapter.relative_to(workspace),
        crash_suite=Path("crash.json"),
        crash_adapter_command=_command(crash_adapter),
        crash_adapter_artifact=crash_adapter.relative_to(workspace),
        race_suite=Path("race.json"),
        race_adapter_command=_command(race_adapter),
        race_adapter_artifact=race_adapter.relative_to(workspace),
        timeout=15.0,
    )
    return workspace, args


def test_reference_matrix_is_exact_self_contained_and_reproducible(tmp_path):
    workspace, args = _workspace(tmp_path)
    matrix = run_pack(args)
    assert matrix["status"] == "evidence_passed"
    assert matrix["aggregate"] == {
        "case_count": 36,
        "checked_outcome_count": 72,
        "exact_count": 72,
        "unsafe_count": 0,
        "availability_loss_count": 0,
        "unresolved_count": 3,
    }
    assert matrix["coverage_binding"] == {
        "tool_id": "notification-service",
        "operation": "send_synthetic_notice",
        "resource_scope": "synthetic-benefit-cases/notices/*",
        "semantic_boundary_present": True,
        "crash_race_same_boundary": True,
        "semantic_declared_relationship_count": 2,
        "semantic_exercised_relationship_count": 2,
        "fully_stressed_relationship_count": 1,
    }
    assert [item["component_id"] for item in matrix["adapter_artifacts"]] == [
        "semantics",
        "crash_recovery",
        "concurrency",
    ]
    assert [item["command_argv_index"] for item in matrix["adapter_artifacts"]] == [
        1,
        1,
        1,
    ]
    assert {item["launch_mode"] for item in matrix["adapter_artifacts"]} == {
        "supported_interpreter_target"
    }
    assert {
        item["material_capture_mode"] for item in matrix["adapter_artifacts"]
    } == {"static_local_python_imports"}
    assert sum(item["material_count"] for item in matrix["adapter_artifacts"]) == 8
    assert sum(
        item["unresolved_import_count"] for item in matrix["adapter_artifacts"]
    ) == 42
    assert all(
        len(item["material_set_sha256"]) == 64
        for item in matrix["adapter_artifacts"]
    )
    assert {
        item["runtime_capture_mode"] for item in matrix["adapter_artifacts"]
    } == {"cpython_audit_workspace_reads"}
    assert sum(
        item["runtime_session_count"] for item in matrix["adapter_artifacts"]
    ) == 109
    assert sum(
        item["runtime_material_count"] for item in matrix["adapter_artifacts"]
    ) == 11
    assert sum(
        item["runtime_only_material_count"] for item in matrix["adapter_artifacts"]
    ) == 3
    assert sum(
        item["unobserved_static_material_count"]
        for item in matrix["adapter_artifacts"]
    ) == 0
    assert all(
        len(item["runtime_observation_sha256"]) == 64
        for item in matrix["adapter_artifacts"]
    )
    assert verify_pack(workspace / "pack") == matrix
    assert {path.name for path in (workspace / "pack").iterdir()} == PACK_FILES
    for name in PACK_FILES:
        assert (workspace / "pack" / name).read_bytes() == (REFERENCE_PACK / name).read_bytes()


def test_matrix_refuses_to_overwrite_an_existing_pack(tmp_path):
    _workspace_path, args = _workspace(tmp_path)
    run_pack(args)
    with pytest.raises(MatrixError, match="overwrite"):
        run_pack(args)


def test_matrix_rejects_output_escape(tmp_path):
    _workspace_path, args = _workspace(tmp_path)
    args.out = Path("../escaped")
    with pytest.raises(MatrixError, match="inside the workspace"):
        run_pack(args)


def test_matrix_rejects_mismatched_exact_relationship_coverage(tmp_path):
    workspace, args = _workspace(tmp_path)
    race = json.loads((workspace / "race.json").read_text())
    race["profile"]["operation_id"] = "different_operation"
    (workspace / "race.json").write_text(json.dumps(race))
    with pytest.raises(MatrixError, match="same tool_id, operation, and resource_scope"):
        run_pack(args)


def test_matrix_rejects_resource_scope_substitution(tmp_path):
    workspace, args = _workspace(tmp_path)
    race = json.loads((workspace / "race.json").read_text())
    race["profile"]["resource_scope"] = "synthetic-benefit-cases/payments/*"
    (workspace / "race.json").write_text(json.dumps(race))
    with pytest.raises(MatrixError, match="same tool_id, operation, and resource_scope"):
        run_pack(args)


def test_matrix_requires_command_to_reference_declared_artifact(tmp_path):
    _workspace_path, args = _workspace(tmp_path)
    args.semantic_adapter_artifact = Path(
        "agent-side-effect-ledger/examples/reference_crash_adapter.py"
    )
    with pytest.raises(MatrixError, match="must reference its declared artifact"):
        run_pack(args)


def test_matrix_rejects_declared_artifact_as_decoy_trailing_argument(tmp_path):
    workspace, args = _workspace(tmp_path)
    semantic = workspace / "agent-side-effect-ledger/examples/reference_adapter.py"
    decoy = workspace / "agent-side-effect-ledger/examples/reference_crash_adapter.py"
    args.semantic_adapter_command = shlex.join(
        [sys.executable, str(semantic), str(decoy)]
    )
    args.semantic_adapter_artifact = decoy.relative_to(workspace)
    with pytest.raises(MatrixError, match=r"must be argv\[0\] or the argv\[1\]"):
        run_pack(args)


def test_matrix_rejects_argv_one_artifact_behind_unknown_launcher(tmp_path):
    workspace, args = _workspace(tmp_path)
    artifact = workspace / "agent-side-effect-ledger/examples/reference_adapter.py"
    args.semantic_adapter_command = shlex.join(["echo", str(artifact)])
    with pytest.raises(MatrixError, match="requires a supported script interpreter"):
        run_pack(args)


def test_matrix_executes_workspace_artifact_not_same_named_cwd_file(tmp_path):
    workspace, args = _workspace(tmp_path)
    declared = workspace / "agent-side-effect-ledger/examples/reference_adapter.py"
    declared.write_text(
        "import json, sys\n"
        "r=json.load(sys.stdin)\n"
        "rows=[{'event_id':e['event_id'],'outcome':'committed','reason_codes':[]} "
        "for e in r['case']['events']]\n"
        "json.dump({'case_id':r['case']['case_id'],'results':rows},sys.stdout)\n"
    )
    args.semantic_adapter_command = (
        "python3 agent-side-effect-ledger/examples/reference_adapter.py"
    )
    matrix = run_pack(args)
    assert matrix["status"] == "evidence_failed"
    assert matrix["aggregate"]["unsafe_count"] > 0


def test_matrix_rejects_adapter_artifact_changed_during_run(tmp_path):
    workspace, args = _workspace(tmp_path)
    mutating = workspace / "mutating_adapter.py"
    mutating.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        "p=Path(__file__)\n"
        "p.write_text(p.read_text()+'# changed\\n')\n"
        "r=json.load(sys.stdin)\n"
        "rows=[{'event_id':e['event_id'],'outcome':'committed','reason_codes':[]} "
        "for e in r['case']['events']]\n"
        "json.dump({'case_id':r['case']['case_id'],'results':rows},sys.stdout)\n"
    )
    args.semantic_adapter_command = _command(mutating)
    args.semantic_adapter_artifact = Path("mutating_adapter.py")
    with pytest.raises(MatrixError, match="runtime material changed"):
        run_pack(args)


def test_matrix_rejects_imported_material_changed_during_run(tmp_path):
    workspace, args = _workspace(tmp_path)
    helper = workspace / "mutating_helper.py"
    helper.write_text(
        "from pathlib import Path\n"
        "p=Path(__file__)\n"
        "p.write_text(p.read_text()+'# changed\\n')\n"
    )
    adapter = workspace / "mutating_material_adapter.py"
    adapter.write_text(
        "import json, sys\n"
        "import mutating_helper\n"
        "r=json.load(sys.stdin)\n"
        "rows=[{'event_id':e['event_id'],'outcome':'committed','reason_codes':[]} "
        "for e in r['case']['events']]\n"
        "json.dump({'case_id':r['case']['case_id'],'results':rows},sys.stdout)\n"
    )
    args.semantic_adapter_command = _command(adapter)
    args.semantic_adapter_artifact = adapter.relative_to(workspace)

    with pytest.raises(MatrixError, match="runtime material changed"):
        run_pack(args)


def test_matrix_rejects_obvious_dynamic_code_loading(tmp_path):
    workspace, args = _workspace(tmp_path)
    adapter = workspace / "dynamic_adapter.py"
    adapter.write_text("import importlib\nimportlib.import_module('hidden')\n")
    args.semantic_adapter_command = _command(adapter)
    args.semantic_adapter_artifact = adapter.relative_to(workspace)

    with pytest.raises(MatrixError, match="dynamic code loading"):
        run_pack(args)


def test_matrix_rejects_empty_adapter_artifact(tmp_path):
    workspace, args = _workspace(tmp_path)
    artifact = workspace / args.semantic_adapter_artifact
    artifact.write_bytes(b"")
    with pytest.raises(MatrixError, match="must contain 1 to"):
        run_pack(args)


def test_matrix_rejects_boundary_absent_from_semantic_suite(tmp_path):
    workspace, args = _workspace(tmp_path)
    semantic = json.loads((workspace / "semantic.json").read_text())
    semantic["profile"]["tools"] = semantic["profile"]["tools"][:1]
    (workspace / "semantic.json").write_text(json.dumps(semantic))
    with pytest.raises(MatrixError, match="must exist in the semantic suite"):
        run_pack(args)


def test_matrix_rejects_declared_relationship_without_legitimate_semantic_event(
    tmp_path,
):
    workspace, args = _workspace(tmp_path)
    semantic = json.loads((workspace / "semantic.json").read_text())
    notification_prepare = next(
        event
        for case in semantic["cases"]
        for event in case["events"]
        if event["kind"] == "prepare"
        and event["content"]["tool_id"] == "notification-service"
    )
    notification_prepare["expected"] = {
        "outcome": "blocked",
        "reason_codes": ["TOOL_NOT_ALLOWED"],
    }
    (workspace / "semantic.json").write_text(json.dumps(semantic))

    with pytest.raises(MatrixError, match="legitimate prepared semantic event"):
        run_pack(args)


def test_matrix_rejects_tampered_or_extra_pack_files(tmp_path):
    workspace, args = _workspace(tmp_path)
    run_pack(args)
    pack = workspace / "pack"
    receipt = pack / "race-receipt.json"
    receipt.write_text(receipt.read_text().replace('"duplicate_effect_count": 0', '"duplicate_effect_count": 1', 1))
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_pack(pack)

    workspace_two, args_two = _workspace(tmp_path / "second")
    run_pack(args_two)
    (workspace_two / "pack" / "unexpected.txt").write_text("unexpected")
    with pytest.raises(MatrixError, match="missing, extra"):
        verify_pack(workspace_two / "pack")


def test_valid_evidence_failure_pack_remains_verifiable(tmp_path):
    workspace, args = _workspace(tmp_path)
    unsafe = workspace / "unsafe_semantic.py"
    unsafe.write_text(
        "import json, sys\n"
        "r=json.load(sys.stdin)\n"
        "rows=[{'event_id':e['event_id'],'outcome':'committed','reason_codes':[]} "
        "for e in r['case']['events']]\n"
        "json.dump({'case_id':r['case']['case_id'],'results':rows},sys.stdout)\n"
    )
    args.semantic_adapter_command = _command(unsafe)
    args.semantic_adapter_artifact = unsafe
    matrix = run_pack(args)
    assert matrix["status"] == "evidence_failed"
    assert matrix["aggregate"]["unsafe_count"] > 0
    assert verify_pack(workspace / "pack") == matrix


def test_matrix_rejects_runtime_observer_substitution(tmp_path):
    workspace, args = _workspace(tmp_path)
    run_pack(args)
    observer = workspace / "pack/runtime-observer.artifact"
    observer.write_bytes(observer.read_bytes() + b"\n# substituted\n")
    with pytest.raises(MatrixError, match="packed observer bytes"):
        verify_pack(workspace / "pack")


def test_composite_action_preserves_diagnostics_and_avoids_context_interpolation():
    action = (ROOT.parent / ".github" / "actions" / "aau-side-effect-safety" / "action.yml").read_text()
    assert "set +e" in action
    assert 'cat "$AAU_MATRIX_OUTPUT/SUMMARY.md"' in action
    assert 'exit "$matrix_status"' in action
    assert "github.event" not in action
    assert "semantic_adapter_command" in action
    assert "semantic_adapter_artifact" in action
    assert "crash_adapter_command" in action
    assert "crash_adapter_artifact" in action
    assert "race_adapter_command" in action
    assert "race_adapter_artifact" in action


def test_matrix_observes_runtime_only_workspace_input_without_embedding_bytes(
    tmp_path,
):
    workspace, args = _workspace(tmp_path)
    config = workspace / "synthetic-policy.txt"
    config.write_text("public-synthetic-policy\n")
    adapter = workspace / "agent-side-effect-ledger/examples/reference_adapter.py"
    adapter.write_text(
        adapter.read_text().replace(
            "from __future__ import annotations\n",
            "from __future__ import annotations\n\n"
            "from pathlib import Path\n"
            f"Path({str(config)!r}).read_text()\n",
        )
    )
    matrix = run_pack(args)
    semantic = matrix["adapter_artifacts"][0]
    assert semantic["runtime_material_count"] == 4
    assert semantic["runtime_only_material_count"] == 2
    observation = json.loads(
        (workspace / "pack/semantic-adapter.observation.json").read_text()
    )
    assert "synthetic-policy.txt" in observation["runtime_only_paths"]
    runtime_row = next(
        row for row in observation["materials"] if row["path"] == "synthetic-policy.txt"
    )
    assert set(runtime_row) == {"path", "size_bytes", "sha256", "event_kinds"}


def test_matrix_rejects_workspace_write_observed_during_run(tmp_path):
    workspace, args = _workspace(tmp_path)
    adapter = workspace / "agent-side-effect-ledger/examples/reference_adapter.py"
    output = workspace / "unexpected-output.txt"
    adapter.write_text(
        adapter.read_text().replace(
            "from __future__ import annotations\n",
            "from __future__ import annotations\n\n"
            "from pathlib import Path\n"
            f"Path({str(output)!r}).write_text('not allowed')\n",
        )
    )
    with pytest.raises(MatrixError, match="workspace_write_attempt"):
        run_pack(args)
