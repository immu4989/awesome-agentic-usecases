"""Capture and verify a bounded static-local Python execution-material set."""

from __future__ import annotations

import argparse
import ast
import base64
import binascii
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


MATERIAL_VERSION = "aau-python-execution-materials/0.1"
CAPTURE_MODES = {"static_local_python_imports", "entrypoint_only_non_python"}
MAX_FILE_BYTES = 2_000_000
MAX_TOTAL_BYTES = 20_000_000
MAX_MATERIALS = 200
BOUNDARIES = {
    "workspace_regular_files_only",
    "static_import_syntax_only",
    "obvious_dynamic_code_loading_rejected",
    "workspace_ancestor_search_is_conservative",
    "unresolved_imports_are_explicit",
    "byte_equality_not_continuous_immutability",
    "not_interpreter_installed_dependency_config_environment_container_or_runtime_identity",
}
DYNAMIC_CALLS = {
    "__import__",
    "eval",
    "exec",
    "exec_module",
    "import_module",
    "module_from_spec",
    "run_module",
    "run_path",
    "spec_from_file_location",
}


class MaterialError(ValueError):
    """Raised when an execution-material set cannot be captured or verified."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else _canonical(value)
    return hashlib.sha256(payload).hexdigest()


def _safe_relative(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 500
        or Path(value).is_absolute()
        or ".." in Path(value).parts
    ):
        raise MaterialError(f"{label} must be a bounded traversal-free relative path")
    return value


def _inside_file(workspace: Path, value: Path, label: str) -> Path:
    candidate = value if value.is_absolute() else workspace / value
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(workspace):
        raise MaterialError(f"{label} must remain inside the workspace")
    if candidate.is_symlink() or not resolved.is_file():
        raise MaterialError(f"{label} must be a regular non-symbolic-link file")
    if not 0 < resolved.stat().st_size <= MAX_FILE_BYTES:
        raise MaterialError(f"{label} must contain 1 to {MAX_FILE_BYTES} bytes")
    return resolved


def _absolute_candidates(
    workspace: Path,
    source: Path,
    module: str,
) -> set[Path]:
    parts = tuple(part for part in module.split(".") if part)
    if not parts:
        return set()
    roots = []
    current = source.parent
    while current.is_relative_to(workspace):
        roots.append(current)
        if current == workspace:
            break
        current = current.parent
    result: set[Path] = set()
    for root in roots:
        candidates = {
            root.joinpath(*parts[:-1], f"{parts[-1]}.py"),
            root.joinpath(*parts, "__init__.py"),
        }
        candidates.update(
            root.joinpath(*parts[:size], "__init__.py")
            for size in range(1, len(parts))
        )
        for path in candidates:
            if path.is_symlink():
                raise MaterialError("local Python import candidates cannot be symbolic links")
            if path.is_file():
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(workspace):
                    raise MaterialError("local Python import candidate escapes workspace")
                result.add(resolved)
    return result


def _relative_candidates(
    workspace: Path,
    source: Path,
    level: int,
    module: str | None,
    imported_names: list[str],
) -> set[Path]:
    base = source.parent
    for _ in range(level - 1):
        base = base.parent
    if not base.is_relative_to(workspace):
        raise MaterialError(f"relative import escapes workspace: {source}")
    module_parts = tuple(module.split(".")) if module else ()
    candidates = {
        base.joinpath(*module_parts).with_suffix(".py") if module_parts else base / "__init__.py",
        base.joinpath(*module_parts, "__init__.py") if module_parts else base / "__init__.py",
    }
    for name in imported_names:
        if name != "*":
            candidates.add(base.joinpath(*module_parts, f"{name}.py"))
            candidates.add(base.joinpath(*module_parts, name, "__init__.py"))
    if any(path.is_symlink() for path in candidates):
        raise MaterialError("relative Python imports cannot resolve through symbolic links")
    result = {path.resolve(strict=True) for path in candidates if path.is_file()}
    if any(not path.is_relative_to(workspace) for path in result):
        raise MaterialError("relative import resolved outside the workspace")
    for path in list(result):
        parent = path.parent
        while parent != base.parent and parent.is_relative_to(workspace):
            init = parent / "__init__.py"
            if init.is_symlink():
                raise MaterialError("package initializers cannot be symbolic links")
            if init.is_file():
                result.add(init.resolve(strict=True))
            if parent == base:
                break
            parent = parent.parent
    return result


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _discover(
    workspace: Path,
    entrypoint: Path,
) -> tuple[dict[Path, bytes], list[str]]:
    materials: dict[Path, bytes] = {}
    unresolved: set[str] = set()
    queue = [entrypoint]
    while queue:
        source = queue.pop(0)
        if source in materials:
            continue
        payload = source.read_bytes()
        if not 0 < len(payload) <= MAX_FILE_BYTES:
            raise MaterialError(f"Python material has invalid size: {source}")
        try:
            tree = ast.parse(payload, filename=str(source))
        except (SyntaxError, ValueError) as exc:
            raise MaterialError(f"Python material cannot be parsed: {source}") from exc
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node) in DYNAMIC_CALLS:
                raise MaterialError(
                    f"obvious dynamic code loading is outside static capture: {source}:{node.lineno}"
                )
        materials[source] = payload
        if len(materials) > MAX_MATERIALS:
            raise MaterialError("static local import closure exceeds the material count limit")
        if sum(len(value) for value in materials.values()) > MAX_TOTAL_BYTES:
            raise MaterialError("static local import closure exceeds the byte limit")
        for node in ast.walk(tree):
            candidates: set[Path] = set()
            label = ""
            if isinstance(node, ast.Import):
                for alias in node.names:
                    resolved = _absolute_candidates(workspace, source, alias.name)
                    if resolved:
                        candidates.update(resolved)
                    else:
                        unresolved.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                imported_names = [alias.name for alias in node.names]
                label = "." * node.level + (node.module or "")
                if node.level:
                    candidates = _relative_candidates(
                        workspace,
                        source,
                        node.level,
                        node.module,
                        imported_names,
                    )
                elif node.module:
                    candidates = _absolute_candidates(
                        workspace, source, node.module
                    )
                    for name in imported_names:
                        if name != "*":
                            candidates.update(
                                _absolute_candidates(
                                    workspace, source, f"{node.module}.{name}"
                                )
                            )
                if not candidates and label:
                    unresolved.add(label)
            queue.extend(sorted(candidates - materials.keys()))
    return materials, sorted(unresolved)


def capture_materials(
    workspace: Path,
    entrypoint: Path,
    capture_mode: str,
) -> dict[str, Any]:
    workspace = workspace.resolve(strict=True)
    if capture_mode not in CAPTURE_MODES:
        raise MaterialError("unsupported execution-material capture mode")
    entrypoint = _inside_file(workspace, entrypoint, "entrypoint")
    if capture_mode == "static_local_python_imports":
        payloads, unresolved = _discover(workspace, entrypoint)
    else:
        payloads, unresolved = {entrypoint: entrypoint.read_bytes()}, []
    rows = []
    for path, payload in sorted(
        payloads.items(), key=lambda item: item[0].relative_to(workspace).as_posix()
    ):
        rows.append(
            {
                "source_path": path.relative_to(workspace).as_posix(),
                "role": "entrypoint" if path == entrypoint else "static_local_python_import",
                "size_bytes": len(payload),
                "sha256": _digest(payload),
                "content_base64": base64.b64encode(payload).decode(),
            }
        )
    result = {
        "material_version": MATERIAL_VERSION,
        "capture_mode": capture_mode,
        "entrypoint": entrypoint.relative_to(workspace).as_posix(),
        "materials": rows,
        "unresolved_imports": unresolved,
        "boundaries": {key: True for key in sorted(BOUNDARIES)},
        "material_set_sha256": "",
    }
    result["material_set_sha256"] = _digest(
        {key: value for key, value in result.items() if key != "material_set_sha256"}
    )
    validate_materials(result)
    return result


def validate_materials(value: Any) -> dict[str, bytes]:
    if not isinstance(value, dict) or set(value) != {
        "material_version",
        "capture_mode",
        "entrypoint",
        "materials",
        "unresolved_imports",
        "boundaries",
        "material_set_sha256",
    }:
        raise MaterialError("execution-material fields differ from the 0.1 contract")
    if value["material_version"] != MATERIAL_VERSION:
        raise MaterialError("execution-material version is unsupported")
    if value["capture_mode"] not in CAPTURE_MODES:
        raise MaterialError("execution-material capture mode is unsupported")
    entrypoint = _safe_relative(value["entrypoint"], "entrypoint")
    boundaries = value["boundaries"]
    if (
        not isinstance(boundaries, dict)
        or set(boundaries) != BOUNDARIES
        or any(boundaries[key] is not True for key in BOUNDARIES)
    ):
        raise MaterialError("every execution-material boundary must be explicit and true")
    imports = value["unresolved_imports"]
    if (
        not isinstance(imports, list)
        or imports != sorted(set(imports))
        or len(imports) > MAX_MATERIALS
        or any(not isinstance(item, str) or not item or len(item) > 300 for item in imports)
    ):
        raise MaterialError("unresolved imports must be a sorted bounded unique list")
    rows = value["materials"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_MATERIALS:
        raise MaterialError("execution materials must be a non-empty bounded list")
    payloads = {}
    keys = []
    entrypoints = 0
    entrypoint_roles = 0
    total = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "source_path", "role", "size_bytes", "sha256", "content_base64"
        }:
            raise MaterialError("execution-material row fields are invalid")
        source_path = _safe_relative(row["source_path"], "material source_path")
        if row["role"] not in {"entrypoint", "static_local_python_import"}:
            raise MaterialError("execution-material role is invalid")
        try:
            payload = base64.b64decode(row["content_base64"], validate=True)
        except (TypeError, ValueError, binascii.Error) as exc:
            raise MaterialError("execution-material content is not canonical base64") from exc
        if base64.b64encode(payload).decode() != row["content_base64"]:
            raise MaterialError("execution-material content is not canonical base64")
        if (
            not 0 < len(payload) <= MAX_FILE_BYTES
            or row["size_bytes"] != len(payload)
            or row["sha256"] != _digest(payload)
        ):
            raise MaterialError("execution-material size or digest does not recompute")
        total += len(payload)
        if total > MAX_TOTAL_BYTES:
            raise MaterialError("execution materials exceed the byte limit")
        entrypoints += int(row["role"] == "entrypoint" and source_path == entrypoint)
        entrypoint_roles += int(row["role"] == "entrypoint")
        keys.append((source_path, row["role"]))
        payloads[source_path] = payload
    if (
        keys != sorted(set(keys))
        or len(payloads) != len(rows)
        or entrypoints != 1
        or entrypoint_roles != 1
    ):
        raise MaterialError("execution materials must be sorted, unique, and name one entrypoint")
    if value["capture_mode"] == "entrypoint_only_non_python" and len(rows) != 1:
        raise MaterialError("entrypoint-only capture may contain only its entrypoint")
    unsigned = {key: item for key, item in value.items() if key != "material_set_sha256"}
    if value["material_set_sha256"] != _digest(unsigned):
        raise MaterialError("execution-material set digest does not recompute")
    return payloads


def _load(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_TOTAL_BYTES * 2:
        raise MaterialError("material file must be a bounded regular file")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MaterialError("material file must contain one JSON object") from exc
    if not isinstance(value, dict):
        raise MaterialError("material file must contain one JSON object")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    capture = sub.add_parser("capture")
    capture.add_argument("--workspace", type=Path, required=True)
    capture.add_argument("--entrypoint", type=Path, required=True)
    capture.add_argument("--capture-mode", choices=sorted(CAPTURE_MODES), required=True)
    capture.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("material_file", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.action == "capture":
            workspace = args.workspace.resolve(strict=True)
            output = args.out if args.out.is_absolute() else workspace / args.out
            resolved = output.resolve(strict=False)
            if not resolved.is_relative_to(workspace):
                raise MaterialError("material output must remain inside the workspace")
            if output.exists() or output.is_symlink():
                raise MaterialError("refusing to overwrite material output")
            output.parent.mkdir(parents=True, exist_ok=True)
            value = capture_materials(workspace, args.entrypoint, args.capture_mode)
            output.write_text(json.dumps(value, indent=2) + "\n")
        else:
            value = _load(args.material_file)
        payloads = validate_materials(value)
        print(
            f"verified execution materials: {len(payloads)} files, "
            f"{len(value['unresolved_imports'])} unresolved imports"
        )
        return 0
    except (MaterialError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
