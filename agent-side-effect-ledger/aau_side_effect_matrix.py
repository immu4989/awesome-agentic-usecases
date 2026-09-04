"""Run and verify the complete AAU side-effect safety evidence matrix."""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any

import aau_crash_lab
import aau_execution_materials
import aau_race_lab
import aau_side_effect


MATRIX_VERSION = "aau-agent-side-effect-safety-matrix/0.4"
MANIFEST_VERSION = "aau-agent-side-effect-safety-manifest/0.3"
MAX_BYTES = 2_000_000
SUPPORTED_INTERPRETERS = {
    "bash",
    "node",
    "nodejs",
    "perl",
    "php",
    "python",
    "python3",
    "ruby",
    "sh",
    "zsh",
}
PYTHON_INTERPRETERS = {"python", "python3"}
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
ARTIFACTS = {
    "semantics": "semantic-adapter.artifact",
    "crash_recovery": "crash-adapter.artifact",
    "concurrency": "race-adapter.artifact",
}
MATERIALS = {
    "semantics": "semantic-adapter.materials.json",
    "crash_recovery": "crash-adapter.materials.json",
    "concurrency": "race-adapter.materials.json",
}
PACK_FILES = (
    set(SUITES.values())
    | set(RECEIPTS.values())
    | set(ARTIFACTS.values())
    | set(MATERIALS.values())
    | {
    "matrix-receipt.json",
    "SUMMARY.md",
    "manifest.json",
    }
)


class MatrixError(ValueError):
    """Raised when a matrix input or pack violates the public contract."""


def _load(path: Path, max_bytes: int = MAX_BYTES) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
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


def _artifact_binding(
    workspace: Path, value: Path, command: str, component_id: str
) -> tuple[dict[str, Any], Path, bytes, str, str]:
    path = _inside(workspace, value, f"{component_id} adapter artifact", exists=True)
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        raise MatrixError(f"{component_id} adapter command cannot be parsed") from exc
    if not argv:
        raise MatrixError(f"{component_id} adapter command is empty")
    referenced_index = None
    for index, token in enumerate(argv):
        candidate = Path(token)
        candidates = (
            [candidate]
            if candidate.is_absolute()
            else [Path.cwd() / candidate, workspace / candidate]
        )
        for possible in candidates:
            try:
                if possible.resolve(strict=True) == path:
                    referenced_index = index
                    break
            except (OSError, RuntimeError):
                continue
        if referenced_index is not None:
            break
    if referenced_index is None:
        raise MatrixError(
            f"{component_id} adapter command must reference its declared artifact as an argv token"
        )
    if referenced_index not in {0, 1}:
        raise MatrixError(
            f"{component_id} adapter artifact must be argv[0] or the argv[1] interpreter target"
        )
    launch_mode = "direct_executable"
    material_capture_mode = "entrypoint_only_non_python"
    if referenced_index == 1:
        launcher = Path(argv[0]).name
        supported = launcher in SUPPORTED_INTERPRETERS or (
            launcher.startswith("python3.")
            and launcher.removeprefix("python3.").replace(".", "").isdigit()
        )
        if not supported:
            raise MatrixError(
                f"{component_id} argv[1] artifact requires a supported script interpreter"
            )
        launch_mode = "supported_interpreter_target"
        if launcher in PYTHON_INTERPRETERS or launcher.startswith("python3."):
            material_capture_mode = "static_local_python_imports"
    payload = path.read_bytes()
    if not payload or len(payload) > MAX_BYTES:
        raise MatrixError(
            f"{component_id} adapter artifact must contain 1 to {MAX_BYTES} bytes"
        )
    row = {
        "component_id": component_id,
        "source_path": path.relative_to(workspace).as_posix(),
        "pack_path": ARTIFACTS[component_id],
        "command_argv_index": referenced_index,
        "launch_mode": launch_mode,
        "size_bytes": len(payload),
        "sha256": aau_side_effect.digest(payload),
    }
    argv[referenced_index] = str(path)
    return row, path, payload, shlex.join(argv), material_capture_mode


def _material_fields(value: dict[str, Any], component_id: str) -> dict[str, Any]:
    payloads = _validate_materials(value)
    return {
        "materials_pack_path": MATERIALS[component_id],
        "material_capture_mode": value["capture_mode"],
        "material_count": len(payloads),
        "unresolved_import_count": len(value["unresolved_imports"]),
        "material_set_sha256": value["material_set_sha256"],
    }


def _validate_materials(value: dict[str, Any]) -> dict[str, bytes]:
    try:
        return aau_execution_materials.validate_materials(value)
    except aau_execution_materials.MaterialError as exc:
        raise MatrixError(f"invalid adapter execution materials: {exc}") from exc


def _capture_materials(
    workspace: Path, entrypoint: Path, capture_mode: str
) -> dict[str, Any]:
    try:
        return aau_execution_materials.capture_materials(
            workspace, entrypoint, capture_mode
        )
    except aau_execution_materials.MaterialError as exc:
        raise MatrixError(f"cannot capture adapter execution materials: {exc}") from exc


def _packed_artifacts(
    output: Path, stored_matrix: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = stored_matrix.get("adapter_artifacts")
    if not isinstance(rows, list) or len(rows) != len(ARTIFACTS):
        raise MatrixError("matrix adapter artifact inventory is invalid")
    expected_components = list(ARTIFACTS)
    result = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {
            "component_id",
            "source_path",
            "pack_path",
            "command_argv_index",
            "launch_mode",
            "size_bytes",
            "sha256",
            "materials_pack_path",
            "material_capture_mode",
            "material_count",
            "unresolved_import_count",
            "material_set_sha256",
        }:
            raise MatrixError("matrix adapter artifact fields are invalid")
        component_id = row["component_id"]
        if component_id != expected_components[index]:
            raise MatrixError("matrix adapter artifacts are missing or out of order")
        source = row["source_path"]
        if (
            not isinstance(source, str)
            or not source
            or len(source) > 500
            or Path(source).is_absolute()
            or ".." in Path(source).parts
        ):
            raise MatrixError("matrix adapter source_path is invalid")
        if row["pack_path"] != ARTIFACTS[component_id]:
            raise MatrixError("matrix adapter pack_path is invalid")
        if not isinstance(row["command_argv_index"], int) or row[
            "command_argv_index"
        ] not in {0, 1}:
            raise MatrixError("matrix adapter command_argv_index is invalid")
        expected_mode = (
            "direct_executable"
            if row["command_argv_index"] == 0
            else "supported_interpreter_target"
        )
        if row["launch_mode"] != expected_mode:
            raise MatrixError("matrix adapter launch_mode is invalid")
        material_value = _load(
            output / MATERIALS[component_id],
            aau_execution_materials.MAX_TOTAL_BYTES * 2,
        )
        material_fields = _material_fields(material_value, component_id)
        if any(row[key] != value for key, value in material_fields.items()):
            raise MatrixError("matrix adapter execution-material binding is invalid")
        payload = (output / row["pack_path"]).read_bytes()
        if not payload:
            raise MatrixError("matrix adapter artifact cannot be empty")
        material_payloads = _validate_materials(material_value)
        if material_payloads.get(source) != payload:
            raise MatrixError("adapter artifact differs from its execution-material entrypoint")
        result.append(
            {
                "component_id": component_id,
                "source_path": source,
                "pack_path": row["pack_path"],
                "command_argv_index": row["command_argv_index"],
                "launch_mode": row["launch_mode"],
                "size_bytes": len(payload),
                "sha256": aau_side_effect.digest(payload),
                **material_fields,
            }
        )
    return result


def _matrix(
    semantic_receipt: dict[str, Any],
    crash_receipt: dict[str, Any],
    race_receipt: dict[str, Any],
    semantic_suite: dict[str, Any],
    crash_suite: dict[str, Any],
    race_suite: dict[str, Any],
    adapter_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    crash_boundary = (
        crash_suite["profile"]["tool_id"],
        crash_suite["profile"]["operation_id"],
    )
    race_boundary = (
        race_suite["profile"]["tool_id"],
        race_suite["profile"]["operation_id"],
    )
    semantic_boundaries = {
        (tool["tool_id"], tool["operation"])
        for tool in semantic_suite["profile"]["tools"]
    }
    if crash_boundary != race_boundary:
        raise MatrixError(
            "crash and race suites must bind the same tool_id and operation"
        )
    if crash_boundary not in semantic_boundaries:
        raise MatrixError(
            "crash/race tool_id and operation must exist in the semantic suite"
        )
    coverage_binding = {
        "tool_id": crash_boundary[0],
        "operation": crash_boundary[1],
        "semantic_boundary_present": True,
        "crash_race_same_boundary": True,
        "semantic_tool_operation_count": len(semantic_boundaries),
        "fully_stressed_tool_operation_count": 1,
    }
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
        "coverage_binding": coverage_binding,
        "adapter_artifacts": adapter_artifacts,
        "claim_boundary": {
            "all_adapter_requests_withhold_expected_answers": True,
            "component_metrics_remain_separate": True,
            "unresolved_can_be_correct_safe_behavior": True,
            "commands_are_trusted_local_code": True,
            "public_synthetic_staging_only": True,
            "crash_and_race_bind_one_semantic_tool_operation": True,
            "matrix_does_not_imply_every_semantic_tool_has_crash_race_coverage": True,
            "command_argument_references_declared_artifact": True,
            "declared_artifact_is_executable_or_supported_interpreter_target": True,
            "declared_artifact_path_normalized_before_execution": True,
            "adapter_artifact_same_before_and_after_matrix_run": True,
            "captured_materials_same_before_and_after_matrix_run": True,
            "command_text_not_recorded": True,
            "static_local_python_import_materials_captured": True,
            "unresolved_imports_remain_explicit": True,
            "not_interpreter_installed_dependency_config_environment_container_or_runtime_identity": True,
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
            f"Crash and concurrency evidence bind **`{matrix['coverage_binding']['tool_id']}` / "
            f"`{matrix['coverage_binding']['operation']}`**. The semantic suite covers "
            f"{matrix['coverage_binding']['semantic_tool_operation_count']} tool-operation pairs; "
            "only the named pair has all three gates.",
            "",
            "Adapter entrypoint artifacts: "
            + " · ".join(
                f"`{item['component_id']}:{item['sha256'][:12]}`"
                for item in matrix["adapter_artifacts"]
            ),
            "",
            "Captured execution materials: "
            f"**{sum(item['material_count'] for item in matrix['adapter_artifacts'])}** files · "
            f"**{sum(item['unresolved_import_count'] for item in matrix['adapter_artifacts'])}** "
            "unresolved standard-library or installed-package import names remain explicit.",
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
    artifact_inputs = (
        ("semantics", args.semantic_adapter_artifact, args.semantic_adapter_command),
        ("crash_recovery", args.crash_adapter_artifact, args.crash_adapter_command),
        ("concurrency", args.race_adapter_artifact, args.race_adapter_command),
    )
    artifact_rows = []
    artifact_sources = {}
    artifact_payloads = {}
    artifact_commands = {}
    material_packs = {}
    material_source_payloads = {}
    for component_id, artifact, command in artifact_inputs:
        row, path, payload, normalized_command, material_capture_mode = _artifact_binding(
            workspace, artifact, command, component_id
        )
        material_pack = _capture_materials(workspace, path, material_capture_mode)
        row.update(_material_fields(material_pack, component_id))
        artifact_rows.append(row)
        artifact_sources[component_id] = path
        artifact_payloads[component_id] = payload
        artifact_commands[component_id] = normalized_command
        material_packs[component_id] = material_pack
        material_source_payloads[component_id] = _validate_materials(material_pack)
    semantic_suite = aau_side_effect.load_json(semantic_path)
    crash_suite = aau_side_effect.load_json(crash_path)
    race_suite = aau_side_effect.load_json(race_path)
    semantic_receipt = aau_side_effect.run_conformance(
        semantic_suite, artifact_commands["semantics"], args.timeout
    )
    crash_receipt = aau_crash_lab.run_suite(
        crash_suite, artifact_commands["crash_recovery"], args.timeout
    )
    race_receipt = aau_race_lab.run_suite(
        race_suite, artifact_commands["concurrency"], args.timeout
    )
    aau_side_effect.verify_conformance_receipt(semantic_receipt, semantic_suite)
    aau_crash_lab.verify_receipt(crash_receipt, crash_suite)
    aau_race_lab.verify_receipt(race_receipt, race_suite)
    for component_id, path in artifact_sources.items():
        if path.read_bytes() != artifact_payloads[component_id]:
            raise MatrixError(f"{component_id} adapter artifact changed during the matrix run")
        for source_path, payload in material_source_payloads[component_id].items():
            source = _inside(
                workspace,
                Path(source_path),
                f"{component_id} execution material",
                exists=True,
            )
            if source.read_bytes() != payload:
                raise MatrixError(
                    f"{component_id} execution material changed during the matrix run"
                )
    matrix = _matrix(
        semantic_receipt,
        crash_receipt,
        race_receipt,
        semantic_suite,
        crash_suite,
        race_suite,
        artifact_rows,
    )
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
    for component_id, name in ARTIFACTS.items():
        (output / name).write_bytes(artifact_payloads[component_id])
    for component_id, name in MATERIALS.items():
        _write_json(output / name, material_packs[component_id])
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
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size
        > (
            aau_execution_materials.MAX_TOTAL_BYTES * 2
            if path.name in MATERIALS.values()
            else MAX_BYTES
        )
        for path in output.iterdir()
    ):
        raise MatrixError("matrix pack has missing, extra, or symbolic-link files")
    stored_matrix = _load(output / "matrix-receipt.json")
    adapter_artifacts = _packed_artifacts(output, stored_matrix)
    semantic_suite = _load(output / SUITES["semantics"])
    crash_suite = _load(output / SUITES["crash_recovery"])
    race_suite = _load(output / SUITES["concurrency"])
    semantic_receipt = _load(output / RECEIPTS["semantics"])
    crash_receipt = _load(output / RECEIPTS["crash_recovery"])
    race_receipt = _load(output / RECEIPTS["concurrency"])
    aau_side_effect.verify_conformance_receipt(semantic_receipt, semantic_suite)
    aau_crash_lab.verify_receipt(crash_receipt, crash_suite)
    aau_race_lab.verify_receipt(race_receipt, race_suite)
    matrix = _matrix(
        semantic_receipt,
        crash_receipt,
        race_receipt,
        semantic_suite,
        crash_suite,
        race_suite,
        adapter_artifacts,
    )
    if stored_matrix != matrix:
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
    parser.add_argument("--semantic-adapter-artifact", type=Path, required=True)
    parser.add_argument("--crash-suite", type=Path, required=True)
    parser.add_argument("--crash-adapter-command", required=True)
    parser.add_argument("--crash-adapter-artifact", type=Path, required=True)
    parser.add_argument("--race-suite", type=Path, required=True)
    parser.add_argument("--race-adapter-command", required=True)
    parser.add_argument("--race-adapter-artifact", type=Path, required=True)
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
    except (
        MatrixError,
        OSError,
        aau_execution_materials.MaterialError,
        aau_side_effect.SideEffectError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
