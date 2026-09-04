"""Bind side-effect evidence to one exact AABOM release and adapter snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "harness" / "src"))

from aau_harness.agent_bom import AgentBomError, validate_bom  # noqa: E402

import aau_side_effect_matrix  # noqa: E402


PLAN_VERSION = "aau-agent-side-effect-release-binding-plan/0.1"
RECEIPT_VERSION = "aau-agent-side-effect-release-binding-receipt/0.4"
PACK_VERSION = "aau-agent-side-effect-release-binding-pack/0.4"
MAX_BYTES = 2_000_000
ROLES = ("semantic", "crash", "race")
MATRIX_COMPONENT = {
    "semantic": "semantics",
    "crash": "crash_recovery",
    "race": "concurrency",
}
BOUNDARY_KEYS = {
    "public_synthetic_staging_only",
    "adapter_paths_workspace_relative",
    "all_consequential_operations_must_be_bound",
    "human_approval_required_for_consequential_authority",
    "no_production_identity_or_deployment_claim",
}
BASE_FILES = {
    "agent-capability-bom.json",
    "binding-plan.json",
    "binding-receipt.json",
    "README.md",
    "manifest.json",
}


class BindingError(ValueError):
    """Raised when a release binding or pack violates the public contract."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else _canonical(value)
    return hashlib.sha256(payload).hexdigest()


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise BindingError(f"{label} fields differ from the 0.1 contract")
    return value


def _text(value: Any, label: str, limit: int = 300) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise BindingError(
            f"{label} must be non-empty text of at most {limit} characters"
        )
    return value


def _load(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise BindingError(f"invalid, oversized, or symbolic-link file: {path}")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BindingError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise BindingError(f"expected one JSON object: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def validate_plan(plan: dict[str, Any]) -> None:
    _exact(
        plan,
        {
            "binding_version",
            "binding_id",
            "agent_id",
            "release_id",
            "bindings",
            "boundaries",
        },
        "release binding plan",
    )
    if plan["binding_version"] != PLAN_VERSION:
        raise BindingError(f"binding_version must be {PLAN_VERSION}")
    for key in ("binding_id", "agent_id", "release_id"):
        _text(plan[key], key, 160)
    bindings = plan["bindings"]
    if not isinstance(bindings, list) or not 1 <= len(bindings) <= 50:
        raise BindingError("bindings must contain 1 to 50 entries")
    pairs: set[tuple[str, str]] = set()
    for index, binding in enumerate(bindings):
        binding = _exact(
            binding,
            {
                "tool_id",
                "operation",
                "semantic_adapter",
                "crash_adapter",
                "race_adapter",
            },
            f"bindings[{index}]",
        )
        pair = (
            _text(binding["tool_id"], f"bindings[{index}].tool_id", 120),
            _text(binding["operation"], f"bindings[{index}].operation", 160),
        )
        if pair in pairs:
            raise BindingError(f"duplicate tool-operation binding: {pair[0]} / {pair[1]}")
        pairs.add(pair)
        for role in ROLES:
            key = f"{role}_adapter"
            value = _text(binding[key], f"bindings[{index}].{key}", 500)
            path = Path(value)
            if path.is_absolute() or ".." in path.parts:
                raise BindingError(
                    "adapter paths must be workspace-relative and traversal-free"
                )
    boundaries = _exact(plan["boundaries"], BOUNDARY_KEYS, "binding boundaries")
    if any(boundaries[key] is not True for key in BOUNDARY_KEYS):
        raise BindingError("every release-binding boundary must be true")


def _inside_file(workspace: Path, value: Path, label: str) -> Path:
    candidate = value if value.is_absolute() else workspace / value
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(workspace):
        raise BindingError(f"{label} must remain inside the workspace")
    if candidate.is_symlink() or not resolved.is_file() or resolved.stat().st_size > MAX_BYTES:
        raise BindingError(f"{label} must be a bounded regular non-symbolic-link file")
    return resolved


def _inside_directory(workspace: Path, value: Path, label: str) -> Path:
    candidate = value if value.is_absolute() else workspace / value
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(workspace):
        raise BindingError(f"{label} must remain inside the workspace")
    if candidate.is_symlink() or not resolved.is_dir():
        raise BindingError(f"{label} must be a regular non-symbolic-link directory")
    return resolved


def _output_path(workspace: Path, value: Path) -> Path:
    candidate = value if value.is_absolute() else workspace / value
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(workspace):
        raise BindingError("binding output must remain inside the workspace")
    if candidate.exists() or candidate.is_symlink():
        raise BindingError(f"refusing to overwrite binding output: {candidate}")
    parent = candidate.parent.resolve(strict=False)
    if not parent.is_relative_to(workspace):
        raise BindingError("binding output parent must remain inside the workspace")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def _adapter_pack_path(binding_index: int, role: str) -> str:
    return f"adapters/{binding_index + 1:03d}-{role}.artifact"


def _adapter_material_pack_path(binding_index: int, role: str) -> str:
    return f"adapters/{binding_index + 1:03d}-{role}.materials.json"


def _adapter_runtime_snapshot_path(binding_index: int, role: str) -> str:
    return f"adapters/{binding_index + 1:03d}-{role}.runtime-snapshot.json"


def _expected_files(plan: dict[str, Any]) -> set[str]:
    files = set(BASE_FILES)
    files.update(f"matrix/{name}" for name in aau_side_effect_matrix.PACK_FILES)
    for index, _binding in enumerate(plan["bindings"]):
        files.update(_adapter_pack_path(index, role) for role in ROLES)
        files.update(_adapter_material_pack_path(index, role) for role in ROLES)
        files.update(_adapter_runtime_snapshot_path(index, role) for role in ROLES)
    return files


def _validate_materials(value: dict[str, Any]) -> dict[str, bytes]:
    try:
        return aau_side_effect_matrix.aau_execution_materials.validate_materials(value)
    except aau_side_effect_matrix.aau_execution_materials.MaterialError as exc:
        raise BindingError(f"invalid adapter execution materials: {exc}") from exc


def _capture_materials(
    workspace: Path,
    source: Path,
    capture_mode: str,
) -> dict[str, Any]:
    try:
        return aau_side_effect_matrix.aau_execution_materials.capture_materials(
            workspace, source, capture_mode
        )
    except aau_side_effect_matrix.aau_execution_materials.MaterialError as exc:
        raise BindingError(f"cannot capture adapter execution materials: {exc}") from exc


def _load_material(path: Path) -> dict[str, Any]:
    limit = aau_side_effect_matrix.aau_execution_materials.MAX_TOTAL_BYTES * 2
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise BindingError("adapter material pack must be a bounded regular file")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BindingError("adapter material pack must contain one JSON object") from exc
    if not isinstance(value, dict):
        raise BindingError("adapter material pack must contain one JSON object")
    _validate_materials(value)
    return value


def _load_runtime_value(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise BindingError(f"{label} must be a bounded regular file")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BindingError(f"{label} must contain one JSON object") from exc
    if not isinstance(value, dict):
        raise BindingError(f"{label} must contain one JSON object")
    return value


def _authority_ids(
    bom: dict[str, Any], tool_id: str, operation: str
) -> tuple[list[str], bool]:
    authorities = [
        item
        for item in bom["authorities"]
        if tool_id in item["tool_ids"] and operation in item["operations"]
    ]
    return (
        sorted(item["authority_id"] for item in authorities),
        bool(authorities)
        and all(item["human_approval_required"] for item in authorities),
    )


def _receipt(
    bom: dict[str, Any],
    plan: dict[str, Any],
    matrix: dict[str, Any],
    bom_bytes: bytes,
    plan_bytes: bytes,
    matrix_manifest_bytes: bytes,
    adapter_payloads: dict[tuple[int, str], bytes],
    adapter_materials: dict[tuple[int, str], dict[str, Any]],
    matrix_observations: dict[str, dict[str, Any]],
    adapter_runtime_snapshots: dict[tuple[int, str], dict[str, Any]],
) -> dict[str, Any]:
    validate_bom(bom)
    validate_plan(plan)
    if plan["agent_id"] != bom["agent_id"]:
        raise BindingError("binding plan agent_id does not match the AABOM")
    if plan["release_id"] != bom["release_id"]:
        raise BindingError("binding plan release_id does not match the AABOM")

    tools = {item["component_id"]: item for item in bom["tools"]}
    findings: list[dict[str, str]] = []

    def add(code: str, subject: str, detail: str) -> None:
        findings.append({"code": code, "subject": subject, "detail": detail})

    matrix_artifacts = {
        item["component_id"]: item for item in matrix["adapter_artifacts"]
    }
    plan_pairs: set[tuple[str, str]] = set()
    binding_matches: dict[tuple[str, str], bool] = {}
    rows: list[dict[str, Any]] = []
    for index, binding in enumerate(plan["bindings"]):
        tool_id, operation = binding["tool_id"], binding["operation"]
        tool = tools.get(tool_id)
        if tool is None or operation not in tool["operations"]:
            raise BindingError(
                f"binding references an undeclared AABOM operation: {tool_id} / {operation}"
            )
        plan_pairs.add((tool_id, operation))
        authority_ids, approval_required = _authority_ids(bom, tool_id, operation)
        adapters = {}
        all_adapters_match = True
        for role in ROLES:
            payload = adapter_payloads[(index, role)]
            sha256 = _digest(payload)
            matrix_artifact = matrix_artifacts[MATRIX_COMPONENT[role]]
            material_pack = adapter_materials[(index, role)]
            material_payloads = _validate_materials(material_pack)
            runtime_observation = matrix_observations[MATRIX_COMPONENT[role]]
            runtime_snapshot = adapter_runtime_snapshots[(index, role)]
            try:
                runtime_materials = (
                    aau_side_effect_matrix.aau_runtime_observation.validate_observation(
                        runtime_observation, set(material_payloads)
                    )
                )
                aau_side_effect_matrix.aau_runtime_observation.validate_release_snapshot(
                    runtime_snapshot, runtime_observation
                )
            except aau_side_effect_matrix.aau_runtime_observation.ObservationError as exc:
                raise BindingError(f"invalid runtime material binding: {exc}") from exc
            path_matches = binding[f"{role}_adapter"] == matrix_artifact["source_path"]
            bytes_match = sha256 == matrix_artifact["sha256"]
            material_entrypoint_matches = (
                material_pack["entrypoint"] == binding[f"{role}_adapter"]
                and material_payloads.get(material_pack["entrypoint"]) == payload
            )
            material_set_matches = (
                material_pack["capture_mode"]
                == matrix_artifact["material_capture_mode"]
                and material_pack["material_set_sha256"]
                == matrix_artifact["material_set_sha256"]
            )
            runtime_materials_match = runtime_snapshot["all_materials_match"]
            matches_matrix = (
                path_matches
                and bytes_match
                and material_entrypoint_matches
                and material_set_matches
                and runtime_materials_match
            )
            all_adapters_match = all_adapters_match and matches_matrix
            adapters[role] = {
                "source_path": binding[f"{role}_adapter"],
                "pack_path": _adapter_pack_path(index, role),
                "size_bytes": len(payload),
                "sha256": sha256,
                "matrix_sha256": matrix_artifact["sha256"],
                "materials_pack_path": _adapter_material_pack_path(index, role),
                "material_capture_mode": material_pack["capture_mode"],
                "material_count": len(material_payloads),
                "unresolved_import_count": len(material_pack["unresolved_imports"]),
                "material_set_sha256": material_pack["material_set_sha256"],
                "matrix_material_set_sha256": matrix_artifact["material_set_sha256"],
                "material_set_matches_matrix": material_set_matches,
                "runtime_observation_pack_path": (
                    f"matrix/{aau_side_effect_matrix.OBSERVATIONS[MATRIX_COMPONENT[role]]}"
                ),
                "runtime_capture_mode": runtime_observation["capture_mode"],
                "runtime_session_count": runtime_observation["observed_session_count"],
                "runtime_material_count": len(runtime_materials),
                "runtime_only_material_count": len(
                    runtime_observation["runtime_only_paths"]
                ),
                "runtime_capabilities": runtime_observation["capabilities"],
                "runtime_observation_sha256": runtime_observation[
                    "observation_sha256"
                ],
                "runtime_snapshot_pack_path": _adapter_runtime_snapshot_path(
                    index, role
                ),
                "runtime_snapshot_sha256": runtime_snapshot["snapshot_sha256"],
                "runtime_materials_match_matrix": runtime_materials_match,
                "matches_matrix": matches_matrix,
            }
            if not path_matches:
                add(
                    "ADAPTER_PATH_DIFFERS_FROM_MATRIX",
                    f"{tool_id} / {operation} / {role}",
                    "The release plan path differs from the artifact path declared during the matrix run.",
                )
            if not bytes_match:
                add(
                    "ADAPTER_BYTES_DIFFER_FROM_MATRIX",
                    f"{tool_id} / {operation} / {role}",
                    "The release adapter bytes differ from the artifact hashed during the matrix run.",
                )
            if not material_entrypoint_matches:
                add(
                    "ADAPTER_MATERIAL_ENTRYPOINT_DIFFERS",
                    f"{tool_id} / {operation} / {role}",
                    "The release material set does not contain the exact declared adapter entrypoint bytes.",
                )
            if not material_set_matches:
                add(
                    "ADAPTER_MATERIALS_DIFFER_FROM_MATRIX",
                    f"{tool_id} / {operation} / {role}",
                    "The release execution-material set differs from the one captured during the matrix run.",
                )
            if not runtime_materials_match:
                add(
                    "RUNTIME_MATERIALS_DIFFER_FROM_MATRIX",
                    f"{tool_id} / {operation} / {role}",
                    "At least one workspace material observed during the matrix run differs at release binding.",
                )
        binding_matches[(tool_id, operation)] = all_adapters_match
        rows.append(
            {
                "tool_id": tool_id,
                "operation": operation,
                "side_effect": tool["side_effect"],
                "authority_ids": authority_ids,
                "human_approval_required": approval_required,
                "all_adapters_match_matrix": all_adapters_match,
                "adapters": adapters,
            }
        )

    consequential = {
        (tool["component_id"], operation)
        for tool in bom["tools"]
        if tool["side_effect"] in {"write", "irreversible"}
        for operation in tool["operations"]
    }
    matrix_pair = (
        matrix["coverage_binding"]["tool_id"],
        matrix["coverage_binding"]["operation"],
    )
    if matrix["status"] != "evidence_passed":
        add("MATRIX_NOT_PASSING", "side-effect matrix", matrix["status"])
    if not consequential:
        add(
            "NO_CONSEQUENTIAL_OPERATIONS",
            "AABOM tools",
            "The release declares no write or irreversible operation to bind.",
        )
    if matrix_pair not in plan_pairs:
        add(
            "MATRIX_BOUNDARY_NOT_IN_PLAN",
            f"{matrix_pair[0]} / {matrix_pair[1]}",
            "The three-gate matrix boundary is absent from the release binding plan.",
        )
    if matrix_pair not in consequential:
        add(
            "MATRIX_BOUNDARY_NOT_CONSEQUENTIAL_IN_AABOM",
            f"{matrix_pair[0]} / {matrix_pair[1]}",
            "The matrix boundary is not a declared write or irreversible AABOM operation.",
        )
    for tool_id, operation in sorted(consequential):
        subject = f"{tool_id} / {operation}"
        if (tool_id, operation) not in plan_pairs:
            add(
                "CONSEQUENTIAL_OPERATION_NOT_IN_PLAN",
                subject,
                "Every AABOM write or irreversible operation requires an adapter binding.",
            )
        if (tool_id, operation) != matrix_pair:
            add(
                "CONSEQUENTIAL_OPERATION_NOT_FULLY_STRESSED",
                subject,
                "This operation is not the matrix's semantic + crash + race boundary.",
            )
        authority_ids, approval_required = _authority_ids(bom, tool_id, operation)
        if not authority_ids:
            add(
                "CONSEQUENTIAL_AUTHORITY_MISSING",
                subject,
                "No AABOM authority names this tool and operation.",
            )
        elif not approval_required:
            add(
                "HUMAN_APPROVAL_NOT_REQUIRED",
                subject,
                "At least one matching AABOM authority omits human approval.",
            )
    matrix_manifest_sha256 = _digest(matrix_manifest_bytes)
    matrix_evidence_bound = any(
        item["sha256"] == matrix_manifest_sha256
        and item["kind"] in {"evaluation_receipt", "release_pack"}
        for item in bom["evidence"]
    )
    if not matrix_evidence_bound:
        add(
            "AABOM_MATRIX_EVIDENCE_NOT_BOUND",
            "AABOM evidence",
            "No evaluation or release-pack evidence entry hashes the exact matrix manifest bytes.",
        )

    findings.sort(key=lambda item: (item["code"], item["subject"], item["detail"]))
    fully_bound = sum(
        pair in plan_pairs
        and pair == matrix_pair
        and bool(_authority_ids(bom, *pair)[0])
        and _authority_ids(bom, *pair)[1]
        and matrix["status"] == "evidence_passed"
        and matrix_evidence_bound
        and binding_matches.get(pair, False)
        for pair in consequential
    )
    result = {
        "receipt_version": RECEIPT_VERSION,
        "binding_id": plan["binding_id"],
        "agent_id": bom["agent_id"],
        "release_id": bom["release_id"],
        "status": "evidence_bound" if not findings else "binding_held",
        "aabom_sha256": _digest(bom_bytes),
        "plan_sha256": _digest(plan_bytes),
        "matrix_manifest_sha256": matrix_manifest_sha256,
        "matrix_sha256": matrix["matrix_sha256"],
        "matrix_status": matrix["status"],
        "matrix_boundary": {"tool_id": matrix_pair[0], "operation": matrix_pair[1]},
        "consequential_operation_count": len(consequential),
        "fully_bound_consequential_operation_count": fully_bound,
        "bindings": rows,
        "findings": findings,
        "claim_boundary": {
            "hashes_bind_pack_bytes_not_runtime_identity": True,
            "source_paths_are_declarations_not_provenance": True,
            "adapter_byte_mismatches_are_binding_holds": True,
            "execution_material_mismatches_are_binding_holds": True,
            "runtime_material_mismatches_are_binding_holds": True,
            "runtime_observation_is_digest_only_and_not_a_sandbox": True,
            "static_and_observed_materials_not_complete_runtime_dependency_graph": True,
            "public_synthetic_staging_only": True,
            "valid_binding_not_deployment_approval_or_authority": True,
            "passing_matrix_not_production_equivalence": True,
        },
    }
    result["receipt_sha256"] = _digest(result)
    return result


def _summary(receipt: dict[str, Any]) -> str:
    finding_lines = (
        [
            f"- `{item['code']}` · **{item['subject']}** — {item['detail']}"
            for item in receipt["findings"]
        ]
        or ["- No binding holds were found in this public-synthetic reference pack."]
    )
    return "\n".join(
        [
            "# AAU side-effect release binding",
            "",
            f"**{receipt['status'].replace('_', ' ').upper()}** · agent "
            f"`{receipt['agent_id']}` · release `{receipt['release_id']}`",
            "",
            f"Fully bound consequential operations: "
            f"**{receipt['fully_bound_consequential_operation_count']}/"
            f"{receipt['consequential_operation_count']}**",
            "",
            f"Matrix boundary: `{receipt['matrix_boundary']['tool_id']} / "
            f"{receipt['matrix_boundary']['operation']}`",
            "",
            "Each adapter binding compares the entrypoint bytes, static-local Python material set, "
            "and every digest-only workspace material observed during the matrix run.",
            "",
            "## Holds",
            "",
            *finding_lines,
            "",
            "The manifest binds these copied bytes and digest-only runtime snapshots. Source paths "
            "are declarations; Python-level audit hooks are bypassable observation, not a sandbox. "
            "This does not bind the interpreter, installed dependencies, environment, container, "
            "or live workload identity. Neither a valid binding nor a passing matrix proves "
            "production equivalence, authorization, safety, compliance, certification, deployment "
            "approval, or an ATO.",
            "",
        ]
    )


def _manifest(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise BindingError("binding packs cannot contain symbolic links")
        if not path.is_file() or path.relative_to(root).as_posix() == "manifest.json":
            continue
        payload = path.read_bytes()
        limit = (
            aau_side_effect_matrix.aau_execution_materials.MAX_TOTAL_BYTES * 2
            if path.name.endswith(".materials.json")
            else MAX_BYTES
        )
        if len(payload) > limit:
            raise BindingError(f"binding pack file is oversized: {path.relative_to(root)}")
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": len(payload),
                "sha256": _digest(payload),
            }
        )
    result = {"pack_version": PACK_VERSION, "files": files}
    result["manifest_sha256"] = _digest(result)
    return result


def build_pack(args: argparse.Namespace) -> dict[str, Any]:
    workspace = args.workspace.resolve(strict=True)
    bom_path = _inside_file(workspace, args.bom, "AABOM")
    plan_path = _inside_file(workspace, args.plan, "binding plan")
    matrix_path = _inside_directory(workspace, args.matrix, "matrix pack")
    output = _output_path(workspace, args.out)
    bom, plan = _load(bom_path), _load(plan_path)
    validate_bom(bom)
    validate_plan(plan)
    matrix = aau_side_effect_matrix.verify_pack(matrix_path)
    matrix_artifacts = {
        item["component_id"]: item for item in matrix["adapter_artifacts"]
    }
    matrix_observations = {
        component_id: _load_runtime_value(
            matrix_path / aau_side_effect_matrix.OBSERVATIONS[component_id],
            f"{component_id} runtime observation",
        )
        for component_id in aau_side_effect_matrix.OBSERVATIONS
    }
    adapter_sources: dict[tuple[int, str], Path] = {}
    adapter_payloads: dict[tuple[int, str], bytes] = {}
    adapter_materials: dict[tuple[int, str], dict[str, Any]] = {}
    adapter_runtime_snapshots: dict[tuple[int, str], dict[str, Any]] = {}
    for index, binding in enumerate(plan["bindings"]):
        for role in ROLES:
            source = _inside_file(
                workspace, Path(binding[f"{role}_adapter"]), f"{role} adapter"
            )
            adapter_sources[(index, role)] = source
            adapter_payloads[(index, role)] = source.read_bytes()
            capture_mode = matrix_artifacts[MATRIX_COMPONENT[role]][
                "material_capture_mode"
            ]
            adapter_materials[(index, role)] = _capture_materials(
                workspace, source, capture_mode
            )
            try:
                adapter_runtime_snapshots[(index, role)] = (
                    aau_side_effect_matrix.aau_runtime_observation.capture_release_snapshot(
                        workspace, matrix_observations[MATRIX_COMPONENT[role]]
                    )
                )
            except aau_side_effect_matrix.aau_runtime_observation.ObservationError as exc:
                raise BindingError(
                    f"cannot snapshot {role} runtime materials: {exc}"
                ) from exc
    receipt = _receipt(
        bom,
        plan,
        matrix,
        bom_path.read_bytes(),
        plan_path.read_bytes(),
        (matrix_path / "manifest.json").read_bytes(),
        adapter_payloads,
        adapter_materials,
        matrix_observations,
        adapter_runtime_snapshots,
    )

    scratch = Path(tempfile.mkdtemp(prefix=".aau-binding-", dir=output.parent))
    try:
        (scratch / "adapters").mkdir()
        (scratch / "matrix").mkdir()
        shutil.copyfile(bom_path, scratch / "agent-capability-bom.json")
        shutil.copyfile(plan_path, scratch / "binding-plan.json")
        for name in aau_side_effect_matrix.PACK_FILES:
            shutil.copyfile(matrix_path / name, scratch / "matrix" / name)
        for (index, role), source in adapter_sources.items():
            shutil.copyfile(source, scratch / _adapter_pack_path(index, role))
            _write_json(
                scratch / _adapter_material_pack_path(index, role),
                adapter_materials[(index, role)],
            )
            _write_json(
                scratch / _adapter_runtime_snapshot_path(index, role),
                adapter_runtime_snapshots[(index, role)],
            )
        _write_json(scratch / "binding-receipt.json", receipt)
        (scratch / "README.md").write_text(_summary(receipt))
        _write_json(scratch / "manifest.json", _manifest(scratch))
        verify_pack(scratch)
        scratch.rename(output)
    except Exception:
        shutil.rmtree(scratch, ignore_errors=True)
        raise
    return receipt


def verify_pack(root: Path) -> dict[str, Any]:
    if root.is_symlink() or not root.is_dir():
        raise BindingError("binding pack must be a regular directory")
    paths = list(root.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise BindingError("binding packs cannot contain symbolic links")
    if any(not path.is_file() and not path.is_dir() for path in paths):
        raise BindingError("binding packs may contain only regular files and directories")
    if any(
        path.is_file()
        and path.stat().st_size
        > (
            aau_side_effect_matrix.aau_execution_materials.MAX_TOTAL_BYTES * 2
            if path.name.endswith(".materials.json")
            else MAX_BYTES
        )
        for path in paths
    ):
        raise BindingError("binding pack contains an oversized file")
    bom = _load(root / "agent-capability-bom.json")
    plan = _load(root / "binding-plan.json")
    validate_bom(bom)
    validate_plan(plan)
    actual_files = {
        path.relative_to(root).as_posix() for path in paths if path.is_file()
    }
    if actual_files != _expected_files(plan):
        raise BindingError("binding pack has missing or extra files")
    actual_directories = {
        path.relative_to(root).as_posix() for path in paths if path.is_dir()
    }
    if actual_directories != {"adapters", "matrix"}:
        raise BindingError("binding pack has missing or extra directories")
    matrix = aau_side_effect_matrix.verify_pack(root / "matrix")
    matrix_observations = {
        component_id: _load_runtime_value(
            root / "matrix" / aau_side_effect_matrix.OBSERVATIONS[component_id],
            f"{component_id} runtime observation",
        )
        for component_id in aau_side_effect_matrix.OBSERVATIONS
    }
    payloads = {
        (index, role): (root / _adapter_pack_path(index, role)).read_bytes()
        for index, _binding in enumerate(plan["bindings"])
        for role in ROLES
    }
    materials = {
        (index, role): _load_material(
            root / _adapter_material_pack_path(index, role)
        )
        for index, _binding in enumerate(plan["bindings"])
        for role in ROLES
    }
    runtime_snapshots = {
        (index, role): _load_runtime_value(
            root / _adapter_runtime_snapshot_path(index, role),
            f"{role} runtime release snapshot",
        )
        for index, _binding in enumerate(plan["bindings"])
        for role in ROLES
    }
    expected = _receipt(
        bom,
        plan,
        matrix,
        (root / "agent-capability-bom.json").read_bytes(),
        (root / "binding-plan.json").read_bytes(),
        (root / "matrix" / "manifest.json").read_bytes(),
        payloads,
        materials,
        matrix_observations,
        runtime_snapshots,
    )
    if _load(root / "binding-receipt.json") != expected:
        raise BindingError("binding receipt does not recompute")
    if (root / "README.md").read_text() != _summary(expected):
        raise BindingError("binding summary does not recompute")
    if _load(root / "manifest.json") != _manifest(root):
        raise BindingError("binding manifest does not recompute")
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    pack = sub.add_parser("pack", help="bind AABOM, matrix, and exact adapter bytes")
    pack.add_argument("--workspace", type=Path, required=True)
    pack.add_argument("--bom", type=Path, required=True)
    pack.add_argument("--matrix", type=Path, required=True)
    pack.add_argument("--plan", type=Path, required=True)
    pack.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify", help="recompute a self-contained binding pack")
    verify.add_argument("pack", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        receipt = build_pack(args) if args.action == "pack" else verify_pack(args.pack)
        print(
            f"verified release binding: "
            f"{receipt['fully_bound_consequential_operation_count']}/"
            f"{receipt['consequential_operation_count']} consequential operations"
        )
        return 0 if receipt["status"] == "evidence_bound" else 1
    except (BindingError, AgentBomError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
