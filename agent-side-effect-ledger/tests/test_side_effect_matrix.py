import argparse
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
    args = argparse.Namespace(
        workspace=workspace,
        out=Path("pack"),
        semantic_suite=Path("semantic.json"),
        semantic_adapter_command=_command(ROOT / "examples" / "reference_adapter.py"),
        crash_suite=Path("crash.json"),
        crash_adapter_command=_command(ROOT / "examples" / "reference_crash_adapter.py"),
        race_suite=Path("race.json"),
        race_adapter_command=_command(ROOT / "examples" / "reference_race_adapter.py"),
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
    matrix = run_pack(args)
    assert matrix["status"] == "evidence_failed"
    assert matrix["aggregate"]["unsafe_count"] > 0
    assert verify_pack(workspace / "pack") == matrix


def test_composite_action_preserves_diagnostics_and_avoids_context_interpolation():
    action = (ROOT.parent / ".github" / "actions" / "aau-side-effect-safety" / "action.yml").read_text()
    assert "set +e" in action
    assert 'cat "$AAU_MATRIX_OUTPUT/SUMMARY.md"' in action
    assert 'exit "$matrix_status"' in action
    assert "github.event" not in action
    assert "semantic_adapter_command" in action
    assert "crash_adapter_command" in action
    assert "race_adapter_command" in action
