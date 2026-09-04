"""Run and verify the complete AAU side-effect safety evidence matrix."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import aau_crash_lab
import aau_race_lab
import aau_side_effect


MATRIX_VERSION = "aau-agent-side-effect-safety-matrix/0.1"
MANIFEST_VERSION = "aau-agent-side-effect-safety-manifest/0.1"
MAX_BYTES = 2_000_000
SUITES = {
    "semantics": "semantic-suite.json",
    "crash_recovery": "crash-suite.json",
    "concurrency": "race-suite.json",
}
RECEIPTS = {
    "semantics": "semantic-receipt.json",
    "crash_recovery": "crash-receipt.json",
    "concurrency": "race-receipt.json",
}
PACK_FILES = set(SUITES.values()) | set(RECEIPTS.values()) | {
    "matrix-receipt.json",
    "SUMMARY.md",
    "manifest.json",
}


class MatrixError(ValueError):
    """Raised when a matrix input or pack violates the public contract."""


def _load(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise MatrixError(f"invalid, oversized, or symbolic-link file: {path}")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MatrixError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise MatrixError(f"expected one JSON object: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def _inside(workspace: Path, value: Path, label: str, *, exists: bool) -> Path:
    workspace = workspace.resolve(strict=True)
    candidate = value if value.is_absolute() else workspace / value
    resolved = candidate.resolve(strict=exists)
    if not resolved.is_relative_to(workspace):
        raise MatrixError(f"{label} must remain inside the workspace")
    if exists and (candidate.is_symlink() or not resolved.is_file()):
        raise MatrixError(f"{label} must be a regular non-symbolic-link file")
    return resolved


def _matrix(
    semantic_receipt: dict[str, Any],
    crash_receipt: dict[str, Any],
    race_receipt: dict[str, Any],
) -> dict[str, Any]:
    semantic = semantic_receipt["summary"]
    crash = crash_receipt["summary"]
    race = race_receipt["summary"]
    components = [
        {
            "component_id": "semantics",
            "status": semantic_receipt["status"],
            "suite_sha256": semantic_receipt["suite_sha256"],
            "receipt_sha256": semantic_receipt["receipt_sha256"],
            "case_count": semantic["case_count"],
            "checked_outcome_count": semantic["event_count"],
            "exact_count": semantic["exact_outcome_count"],
            "unsafe_count": semantic["unsafe_effect_outcome_count"],
            "availability_loss_count": semantic["legitimate_effect_block_count"],
            "unresolved_count": 0,
        },
        {
            "component_id": "crash_recovery",
            "status": crash_receipt["status"],
            "suite_sha256": crash_receipt["suite_sha256"],
            "receipt_sha256": crash_receipt["receipt_sha256"],
            "case_count": crash["case_count"],
            "checked_outcome_count": crash["case_count"],
            "exact_count": crash["exact_count"],
            "unsafe_count": crash["unsafe_resume_count"]
            + crash["duplicate_effect_breach_count"],
            "availability_loss_count": 0,
            "unresolved_count": crash["unresolved_effect_count"],
        },
        {
            "component_id": "concurrency",
            "status": race_receipt["status"],
            "suite_sha256": race_receipt["suite_sha256"],
            "receipt_sha256": race_receipt["receipt_sha256"],
            "case_count": race["case_count"],
            "checked_outcome_count": race["case_count"],
            "exact_count": race["exact_count"],
            "unsafe_count": race["duplicate_effect_count"]
            + race["response_state_mismatch_count"],
            "availability_loss_count": race["missing_effect_count"],
            "unresolved_count": 0,
        },
    ]
    aggregate_keys = (
        "case_count",
        "checked_outcome_count",
        "exact_count",
        "unsafe_count",
        "availability_loss_count",
        "unresolved_count",
    )
    aggregate = {
        key: sum(component[key] for component in components) for key in aggregate_keys
    }
    status = (
        "evidence_passed"
        if all(component["status"] == "evidence_passed" for component in components)
        else "evidence_failed"
    )
    result = {
        "matrix_version": MATRIX_VERSION,
        "status": status,
        "component_count": len(components),
        "components": components,
        "aggregate": aggregate,
        "claim_boundary": {
            "all_adapter_requests_withhold_expected_answers": True,
            "component_metrics_remain_separate": True,
            "unresolved_can_be_correct_safe_behavior": True,
            "commands_are_trusted_local_code": True,
            "public_synthetic_staging_only": True,
            "passing_not_atomicity_linearizability_exactly_once_or_deployment_authority": True,
        },
    }
    result["matrix_sha256"] = aau_side_effect.digest(result)
    return result


def _summary(matrix: dict[str, Any]) -> str:
    labels = {
        "semantics": "Intent + approval semantics",
        "crash_recovery": "Fresh-process crash recovery",
        "concurrency": "Multi-process concurrency",
    }
    lines = [
        "## AAU side-effect safety matrix",
        "",
        f"**{matrix['status'].replace('_', ' ').upper()}** · "
        f"{matrix['aggregate']['exact_count']}/{matrix['aggregate']['checked_outcome_count']} "
        f"exact checked outcomes · {matrix['aggregate']['unsafe_count']} unsafe outcomes · "
        f"{matrix['aggregate']['availability_loss_count']} availability losses · "
        f"{matrix['aggregate']['unresolved_count']} uncertainties preserved",
        "",
        "| Component | Exact | Cases | Unsafe | Availability loss | Unresolved |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for component in matrix["components"]:
        lines.append(
            f"| {labels[component['component_id']]} | "
            f"{component['exact_count']}/{component['checked_outcome_count']} | "
            f"{component['case_count']} | {component['unsafe_count']} | "
            f"{component['availability_loss_count']} | {component['unresolved_count']} |"
        )
    lines.extend(
        [
            "",
            "Expected answers were not sent to adapters. Every command is trusted local code and "
            "must be restricted to public-synthetic staging state.",
            "",
            "A passing matrix is bounded evidence for these exact adapters and suites. It is not "
            "proof of production atomicity, linearizability, exactly-once execution, safety, "
            "certification, compliance, deployment approval, or an Authority to Operate.",
            "",
        ]
    )
    return "\n".join(lines)


def _manifest(directory: Path) -> dict[str, Any]:
    files = []
    for name in sorted(PACK_FILES - {"manifest.json"}):
        payload = (directory / name).read_bytes()
        files.append(
            {"path": name, "size_bytes": len(payload), "sha256": aau_side_effect.digest(payload)}
        )
    manifest = {"manifest_version": MANIFEST_VERSION, "files": files}
    manifest["manifest_sha256"] = aau_side_effect.digest(manifest)
    return manifest


def run_pack(args: argparse.Namespace) -> dict[str, Any]:
    workspace = args.workspace.resolve(strict=True)
    semantic_path = _inside(workspace, args.semantic_suite, "semantic suite", exists=True)
    crash_path = _inside(workspace, args.crash_suite, "crash suite", exists=True)
    race_path = _inside(workspace, args.race_suite, "race suite", exists=True)
    output = _inside(workspace, args.out, "matrix output", exists=False)
    if output.exists() or output.is_symlink():
        raise MatrixError(f"refusing to overwrite matrix output: {output}")
    for label, command in (
        ("semantic", args.semantic_adapter_command),
        ("crash", args.crash_adapter_command),
        ("race", args.race_adapter_command),
    ):
        if not isinstance(command, str) or not command.strip():
            raise MatrixError(f"{label} adapter command is empty")
    semantic_suite = aau_side_effect.load_json(semantic_path)
    crash_suite = aau_side_effect.load_json(crash_path)
    race_suite = aau_side_effect.load_json(race_path)
    semantic_receipt = aau_side_effect.run_conformance(
        semantic_suite, args.semantic_adapter_command, args.timeout
    )
    crash_receipt = aau_crash_lab.run_suite(
        crash_suite, args.crash_adapter_command, args.timeout
    )
    race_receipt = aau_race_lab.run_suite(race_suite, args.race_adapter_command, args.timeout)
    aau_side_effect.verify_conformance_receipt(semantic_receipt, semantic_suite)
    aau_crash_lab.verify_receipt(crash_receipt, crash_suite)
    aau_race_lab.verify_receipt(race_receipt, race_suite)
    matrix = _matrix(semantic_receipt, crash_receipt, race_receipt)
    output.mkdir(parents=True)
    for source, name in (
        (semantic_path, SUITES["semantics"]),
        (crash_path, SUITES["crash_recovery"]),
        (race_path, SUITES["concurrency"]),
    ):
        shutil.copyfile(source, output / name)
    for receipt, name in (
        (semantic_receipt, RECEIPTS["semantics"]),
        (crash_receipt, RECEIPTS["crash_recovery"]),
        (race_receipt, RECEIPTS["concurrency"]),
    ):
        _write_json(output / name, receipt)
    _write_json(output / "matrix-receipt.json", matrix)
    (output / "SUMMARY.md").write_text(_summary(matrix))
    _write_json(output / "manifest.json", _manifest(output))
    verify_pack(output)
    return matrix


def verify_pack(output: Path) -> dict[str, Any]:
    if output.is_symlink() or not output.is_dir():
        raise MatrixError("matrix output must be a regular directory")
    files = {path.name for path in output.iterdir()}
    if files != PACK_FILES or any(
        path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES
        for path in output.iterdir()
    ):
        raise MatrixError("matrix pack has missing, extra, or symbolic-link files")
    semantic_suite = _load(output / SUITES["semantics"])
    crash_suite = _load(output / SUITES["crash_recovery"])
    race_suite = _load(output / SUITES["concurrency"])
    semantic_receipt = _load(output / RECEIPTS["semantics"])
    crash_receipt = _load(output / RECEIPTS["crash_recovery"])
    race_receipt = _load(output / RECEIPTS["concurrency"])
    aau_side_effect.verify_conformance_receipt(semantic_receipt, semantic_suite)
    aau_crash_lab.verify_receipt(crash_receipt, crash_suite)
    aau_race_lab.verify_receipt(race_receipt, race_suite)
    matrix = _matrix(semantic_receipt, crash_receipt, race_receipt)
    if _load(output / "matrix-receipt.json") != matrix:
        raise MatrixError("matrix receipt does not recompute")
    if (output / "SUMMARY.md").read_text() != _summary(matrix):
        raise MatrixError("matrix summary does not recompute")
    if _load(output / "manifest.json") != _manifest(output):
        raise MatrixError("matrix manifest does not recompute")
    return matrix


def _run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--semantic-suite", type=Path, required=True)
    parser.add_argument("--semantic-adapter-command", required=True)
    parser.add_argument("--crash-suite", type=Path, required=True)
    parser.add_argument("--crash-adapter-command", required=True)
    parser.add_argument("--race-suite", type=Path, required=True)
    parser.add_argument("--race-adapter-command", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    _run_args(sub.add_parser("run", help="run all three gates and build a portable pack"))
    verify = sub.add_parser("verify", help="verify a self-contained matrix pack")
    verify.add_argument("pack", type=Path)
    return parser


def main() -> int:
    try:
        args = _parser().parse_args()
        matrix = run_pack(args) if args.action == "run" else verify_pack(args.pack)
        print(
            f"verified side-effect matrix: {matrix['aggregate']['exact_count']}/"
            f"{matrix['aggregate']['checked_outcome_count']} exact checked outcomes"
        )
        return 0 if matrix["status"] == "evidence_passed" else 1
    except (MatrixError, OSError, aau_side_effect.SideEffectError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
