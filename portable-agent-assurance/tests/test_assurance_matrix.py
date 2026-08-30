from __future__ import annotations

import importlib.util
import shutil
import sys
from argparse import Namespace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("assurance_matrix", ROOT / "assurance_matrix.py")
assert SPEC and SPEC.loader
MATRIX = importlib.util.module_from_spec(SPEC)
sys.path.insert(0, str(ROOT))
SPEC.loader.exec_module(MATRIX)


def arguments(workspace: Path, output: Path) -> Namespace:
    examples = workspace / "examples"
    examples.mkdir(exist_ok=True)
    names = (
        "mcp-2026-authorization-profile.json",
        "mcp-2026-authorization-suite.json",
        "a2a-1-interface-authorization-profile.json",
        "a2a-1-interface-authorization-suite.json",
        "a2a-mcp-authority-relay-profile.json",
        "a2a-mcp-authority-relay-suite.json",
    )
    for name in names:
        shutil.copyfile(ROOT / "examples" / name, examples / name)
    return Namespace(
        workspace=workspace,
        out=output,
        mcp_profile=examples / names[0],
        mcp_suite=examples / names[1],
        mcp_adapter_command=f"{sys.executable} {ROOT / 'examples/mcp_2026_reference_adapter.py'}",
        a2a_profile=examples / names[2],
        a2a_suite=examples / names[3],
        a2a_adapter_command=f"{sys.executable} {ROOT / 'examples/a2a_1_reference_adapter.py'}",
        relay_profile=examples / names[4],
        relay_suite=examples / names[5],
        relay_adapter_command=f"{sys.executable} {ROOT / 'examples/authority_relay_reference_adapter.py'}",
        timeout=3,
    )


def test_current_matrix_is_exact_and_recomputable(tmp_path):
    args = arguments(tmp_path, Path("evidence/current-matrix"))
    matrix = MATRIX.run_pack(args)
    assert matrix["status"] == "evidence_passed"
    assert matrix["aggregate"] == {
        "case_count": 58,
        "clean_twin_count": 6,
        "violation_count": 52,
        "exact_count": 58,
        "unsafe_allow_count": 0,
        "legitimate_block_count": 0,
    }
    assert MATRIX.verify_pack(args) == matrix
    assert (tmp_path / args.out / "SUMMARY.md").read_text().startswith(
        "## AAU current agent-assurance matrix"
    )


def test_pack_tampering_and_extra_files_fail_closed(tmp_path):
    args = arguments(tmp_path, Path("matrix"))
    MATRIX.run_pack(args)
    summary = tmp_path / args.out / "SUMMARY.md"
    summary.write_text(summary.read_text() + "tampered\n")
    with pytest.raises(MATRIX.MatrixError, match="summary"):
        MATRIX.verify_pack(args)
    summary.write_text(MATRIX._summary(MATRIX._load(tmp_path / args.out / "matrix-receipt.json")))
    (tmp_path / args.out / "extra.txt").write_text("extra")
    with pytest.raises(MATRIX.MatrixError, match="missing, extra"):
        MATRIX.verify_pack(args)


def test_output_escape_and_overwrite_are_rejected(tmp_path):
    args = arguments(tmp_path, Path("../escape"))
    with pytest.raises(MATRIX.MatrixError, match="inside the workspace"):
        MATRIX.run_pack(args)
    args.out = Path("matrix")
    MATRIX.run_pack(args)
    with pytest.raises(MATRIX.MatrixError, match="refusing to overwrite"):
        MATRIX.run_pack(args)
