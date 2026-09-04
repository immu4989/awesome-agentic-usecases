"""Build and verify privacy-bounded CPython workspace observation receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


OBSERVER_VERSION = "aau-cpython-workspace-observer/0.1"
OBSERVATION_VERSION = "aau-cpython-workspace-observation/0.1"
SNAPSHOT_VERSION = "aau-cpython-workspace-release-snapshot/0.1"
CAPTURE_MODE = "cpython_audit_workspace_reads"
UNOBSERVED_MODE = "not_observed_non_python"
MAX_MATERIAL_BYTES = 2_000_000
MAX_TRACE_BYTES = 2_000_000
MAX_TRACE_FILES = 250
MAX_TRACE_LINES = 20_000
MAX_MATERIALS = 200
TRACE_EVENT_KINDS = {"exec", "import", "read", "run_file"}
EVENT_KINDS = {"code", "read"}
CAPABILITIES = {
    "dynamic_code",
    "native_or_extension_load",
    "network",
    "runtime_instrumentation_change",
    "subprocess",
}
BOUNDARIES = {
    "cpython_events_are_implementation_specific",
    "digest_sample_precedes_application_open",
    "no_interpreter_installed_package_environment_container_or_workload_identity",
    "outside_workspace_arguments_not_recorded",
    "python_level_audit_hook_is_not_a_sandbox",
    "runtime_only_bytes_not_embedded",
    "trusted_adapter_can_bypass_or_tamper_with_observation",
    "toctou_window_remains",
    "workspace_regular_files_only",
}


class ObservationError(ValueError):
    """Raised when runtime observation is missing, malformed, or inconsistent."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else _canonical(value)
    return hashlib.sha256(payload).hexdigest()


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ObservationError(f"{label} fields are invalid")
    return value


def _digest_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or value != value.lower():
        raise ObservationError(f"{label} must be a lowercase SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ObservationError(f"{label} must be a lowercase SHA-256 digest") from exc
    return value


def _relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 500:
        raise ObservationError(f"{label} must be bounded non-empty text")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or value != path.as_posix():
        raise ObservationError(f"{label} must be normalized and workspace-relative")
    return value


def _source() -> tuple[Path, bytes]:
    path = Path(__file__).with_name("aau_runtime_sitecustomize.py")
    if path.is_symlink() or not path.is_file():
        raise ObservationError("runtime observer source is missing or symbolic")
    payload = path.read_bytes()
    if not payload or len(payload) > MAX_MATERIAL_BYTES:
        raise ObservationError("runtime observer source is empty or oversized")
    return path, payload


def prepare_observer(directory: Path) -> tuple[Path, bytes]:
    """Materialize the exact startup observer as sitecustomize.py."""
    _path, payload = _source()
    directory.mkdir(parents=True, exist_ok=False)
    destination = directory / "sitecustomize.py"
    destination.write_bytes(payload)
    return destination, payload


def instrumentation_environment(
    workspace: Path, trace_directory: Path, observer_directory: Path
) -> dict[str, str]:
    workspace = workspace.resolve(strict=True)
    trace_directory = trace_directory.resolve(strict=True)
    observer_directory = observer_directory.resolve(strict=True)
    for path, label in (
        (workspace, "workspace"),
        (trace_directory, "trace directory"),
        (observer_directory, "observer directory"),
    ):
        if path.is_symlink() or not path.is_dir():
            raise ObservationError(f"{label} must be a regular directory")
    environment = dict(os.environ)
    previous = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(observer_directory) + (
        os.pathsep + previous if previous else ""
    )
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["AAU_RUNTIME_TRACE_DIRECTORY"] = str(trace_directory)
    environment["AAU_RUNTIME_WORKSPACE"] = str(workspace)
    return environment


def _workspace_file(workspace: Path, relative: str) -> Path:
    relative = _relative_path(relative, "runtime material path")
    candidate = workspace / relative
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(workspace):
        raise ObservationError("runtime material escapes the workspace")
    if (
        candidate.is_symlink()
        or not resolved.is_file()
        or not 1 <= resolved.stat().st_size <= MAX_MATERIAL_BYTES
    ):
        raise ObservationError("runtime material must be a regular non-symbolic-link file")
    return resolved


def _load_trace(path: Path) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_TRACE_BYTES:
        raise ObservationError("runtime trace must be a bounded regular file")
    try:
        lines = path.read_text().splitlines()
    except UnicodeDecodeError as exc:
        raise ObservationError("runtime trace must be UTF-8") from exc
    if not lines or len(lines) > MAX_TRACE_LINES:
        raise ObservationError("runtime trace line count is invalid")
    result = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ObservationError("runtime trace contains invalid JSON") from exc
        if not isinstance(value, dict):
            raise ObservationError("runtime trace rows must be objects")
        result.append(value)
    return result


def observer_descriptor(payload: bytes) -> dict[str, Any]:
    return {
        "observer_version": OBSERVER_VERSION,
        "pack_path": "runtime-observer.artifact",
        "size_bytes": len(payload),
        "sha256": _digest(payload),
    }


def capture_observation(
    workspace: Path,
    trace_directory: Path,
    expected_sessions: int,
    static_materials: dict[str, bytes],
    observer_payload: bytes,
) -> dict[str, Any]:
    """Aggregate per-process traces and bind every stable workspace read by digest."""
    workspace = workspace.resolve(strict=True)
    trace_directory = trace_directory.resolve(strict=True)
    if not isinstance(expected_sessions, int) or not 1 <= expected_sessions <= MAX_TRACE_FILES:
        raise ObservationError("expected runtime session count is invalid")
    paths = sorted(trace_directory.iterdir())
    if not paths or len(paths) > MAX_TRACE_FILES:
        raise ObservationError("runtime trace file count is invalid")
    observations: dict[str, tuple[int, str, set[str]]] = {}
    capabilities: set[str] = set()
    violations: list[tuple[str, str]] = []
    sessions = 0
    for path in paths:
        session_rows = 0
        for row in _load_trace(path):
            row_type = row.get("type")
            if row_type == "session":
                _exact(row, {"type", "observer_version"}, "runtime session")
                if row["observer_version"] != OBSERVER_VERSION:
                    raise ObservationError("runtime observer version mismatch")
                session_rows += 1
            elif row_type == "material":
                _exact(
                    row,
                    {"type", "path", "event_kind", "size_bytes", "sha256"},
                    "runtime material trace",
                )
                relative = _relative_path(row["path"], "runtime material path")
                if row["event_kind"] not in TRACE_EVENT_KINDS:
                    raise ObservationError("runtime material event kind is invalid")
                if not isinstance(row["size_bytes"], int) or not (
                    1 <= row["size_bytes"] <= MAX_MATERIAL_BYTES
                ):
                    raise ObservationError("runtime material size is invalid")
                digest = _digest_text(row["sha256"], "runtime material digest")
                existing = observations.get(relative)
                if existing is None:
                    observations[relative] = (
                        row["size_bytes"],
                        digest,
                        {row["event_kind"]},
                    )
                elif existing[:2] != (row["size_bytes"], digest):
                    raise ObservationError(
                        f"runtime material changed between observations: {relative}"
                    )
                else:
                    existing[2].add(row["event_kind"])
            elif row_type == "capability":
                _exact(row, {"type", "capability"}, "runtime capability trace")
                if row["capability"] not in CAPABILITIES:
                    raise ObservationError("runtime capability is invalid")
                capabilities.add(row["capability"])
            elif row_type == "violation":
                _exact(row, {"type", "code", "path"}, "runtime violation trace")
                relative = _relative_path(row["path"], "runtime violation path")
                if not isinstance(row["code"], str) or not row["code"]:
                    raise ObservationError("runtime violation code is invalid")
                violations.append((row["code"], relative))
            else:
                raise ObservationError("runtime trace row type is invalid")
        if session_rows != 1:
            raise ObservationError("each runtime trace must contain one session marker")
        sessions += 1
    if sessions != expected_sessions:
        raise ObservationError(
            f"observed {sessions} runtime sessions; expected {expected_sessions}"
        )
    if violations:
        code, relative = sorted(violations)[0]
        raise ObservationError(f"runtime observation violation {code}: {relative}")
    if not observations or len(observations) > MAX_MATERIALS:
        raise ObservationError("runtime material count is invalid")
    materials = []
    for relative, (size, observed_digest, kinds) in sorted(observations.items()):
        source = _workspace_file(workspace, relative)
        payload = source.read_bytes()
        if len(payload) != size or _digest(payload) != observed_digest:
            raise ObservationError(
                f"runtime material differs after its observed read: {relative}"
            )
        normalized_kinds = (
            ["code"] if kinds & {"exec", "import", "run_file"} else ["read"]
        )
        materials.append(
            {
                "path": relative,
                "size_bytes": size,
                "sha256": observed_digest,
                "event_kinds": normalized_kinds,
            }
        )
    static_paths = set(static_materials)
    observed_paths = set(observations)
    result = {
        "observation_version": OBSERVATION_VERSION,
        "capture_mode": CAPTURE_MODE,
        "observer": observer_descriptor(observer_payload),
        "expected_session_count": expected_sessions,
        "observed_session_count": sessions,
        "materials": materials,
        "runtime_only_paths": sorted(observed_paths - static_paths),
        "unobserved_static_paths": sorted(static_paths - observed_paths),
        "capabilities": sorted(capabilities),
        "boundaries": {key: True for key in sorted(BOUNDARIES)},
    }
    result["observation_sha256"] = _digest(result)
    validate_observation(result, static_paths)
    return result


def unobserved_non_python(
    static_materials: dict[str, bytes], observer_payload: bytes
) -> dict[str, Any]:
    """Make the lack of Python runtime observation explicit and verifiable."""
    result = {
        "observation_version": OBSERVATION_VERSION,
        "capture_mode": UNOBSERVED_MODE,
        "observer": observer_descriptor(observer_payload),
        "expected_session_count": 0,
        "observed_session_count": 0,
        "materials": [],
        "runtime_only_paths": [],
        "unobserved_static_paths": sorted(static_materials),
        "capabilities": [],
        "boundaries": {key: True for key in sorted(BOUNDARIES)},
    }
    result["observation_sha256"] = _digest(result)
    validate_observation(result, set(static_materials))
    return result


def validate_observation(
    value: dict[str, Any], static_paths: set[str] | None = None
) -> dict[str, tuple[int, str]]:
    value = _exact(
        value,
        {
            "observation_version",
            "capture_mode",
            "observer",
            "expected_session_count",
            "observed_session_count",
            "materials",
            "runtime_only_paths",
            "unobserved_static_paths",
            "capabilities",
            "boundaries",
            "observation_sha256",
        },
        "runtime observation",
    )
    if value["observation_version"] != OBSERVATION_VERSION:
        raise ObservationError("runtime observation version is unsupported")
    if value["capture_mode"] not in {CAPTURE_MODE, UNOBSERVED_MODE}:
        raise ObservationError("runtime observation capture mode is unsupported")
    observer = _exact(
        value["observer"],
        {"observer_version", "pack_path", "size_bytes", "sha256"},
        "runtime observer descriptor",
    )
    if observer["observer_version"] != OBSERVER_VERSION or observer["pack_path"] != (
        "runtime-observer.artifact"
    ):
        raise ObservationError("runtime observer descriptor is invalid")
    if not isinstance(observer["size_bytes"], int) or not (
        1 <= observer["size_bytes"] <= MAX_MATERIAL_BYTES
    ):
        raise ObservationError("runtime observer size is invalid")
    _digest_text(observer["sha256"], "runtime observer digest")
    observed_mode = value["capture_mode"] == CAPTURE_MODE
    for key in ("expected_session_count", "observed_session_count"):
        minimum = 1 if observed_mode else 0
        maximum = MAX_TRACE_FILES if observed_mode else 0
        if not isinstance(value[key], int) or not minimum <= value[key] <= maximum:
            raise ObservationError(f"{key} is invalid")
    if value["expected_session_count"] != value["observed_session_count"]:
        raise ObservationError("runtime session coverage is incomplete")
    materials = value["materials"]
    minimum_materials = 1 if observed_mode else 0
    maximum_materials = MAX_MATERIALS if observed_mode else 0
    if (
        not isinstance(materials, list)
        or not minimum_materials <= len(materials) <= maximum_materials
    ):
        raise ObservationError("runtime materials are invalid")
    mapping: dict[str, tuple[int, str]] = {}
    for row in materials:
        row = _exact(
            row,
            {"path", "size_bytes", "sha256", "event_kinds"},
            "runtime material",
        )
        relative = _relative_path(row["path"], "runtime material path")
        if relative in mapping:
            raise ObservationError("runtime material paths must be unique")
        if not isinstance(row["size_bytes"], int) or not (
            1 <= row["size_bytes"] <= MAX_MATERIAL_BYTES
        ):
            raise ObservationError("runtime material size is invalid")
        digest = _digest_text(row["sha256"], "runtime material digest")
        kinds = row["event_kinds"]
        if (
            not isinstance(kinds, list)
            or not kinds
            or kinds != sorted(set(kinds))
            or any(kind not in EVENT_KINDS for kind in kinds)
        ):
            raise ObservationError("runtime material event kinds are invalid")
        mapping[relative] = (row["size_bytes"], digest)
    if list(mapping) != sorted(mapping):
        raise ObservationError("runtime materials must be sorted by path")
    for key in ("runtime_only_paths", "unobserved_static_paths"):
        paths = value[key]
        if not isinstance(paths, list):
            raise ObservationError(f"{key} must be a list")
        normalized = [_relative_path(path, key) for path in paths]
        if normalized != sorted(set(normalized)):
            raise ObservationError(f"{key} must be sorted and unique")
    if static_paths is not None:
        if value["runtime_only_paths"] != sorted(set(mapping) - static_paths):
            raise ObservationError("runtime-only path classification is invalid")
        if value["unobserved_static_paths"] != sorted(static_paths - set(mapping)):
            raise ObservationError("unobserved static path classification is invalid")
    capabilities = value["capabilities"]
    if (
        not isinstance(capabilities, list)
        or capabilities != sorted(set(capabilities))
        or any(item not in CAPABILITIES for item in capabilities)
    ):
        raise ObservationError("runtime capabilities are invalid")
    boundaries = _exact(value["boundaries"], BOUNDARIES, "runtime boundaries")
    if any(boundaries[key] is not True for key in BOUNDARIES):
        raise ObservationError("every runtime observation boundary must be true")
    unsigned = dict(value)
    supplied = _digest_text(
        unsigned.pop("observation_sha256"), "runtime observation digest"
    )
    if supplied != _digest(unsigned):
        raise ObservationError("runtime observation digest mismatch")
    return mapping


def capture_release_snapshot(
    workspace: Path, observation: dict[str, Any]
) -> dict[str, Any]:
    """Re-hash the tested runtime paths without re-running the adapter."""
    workspace = workspace.resolve(strict=True)
    tested = validate_observation(observation)
    materials = []
    for relative, (tested_size, tested_digest) in tested.items():
        payload = _workspace_file(workspace, relative).read_bytes()
        current_digest = _digest(payload)
        materials.append(
            {
                "path": relative,
                "size_bytes": len(payload),
                "sha256": current_digest,
                "tested_size_bytes": tested_size,
                "tested_sha256": tested_digest,
                "matches_tested": len(payload) == tested_size
                and current_digest == tested_digest,
            }
        )
    result = {
        "snapshot_version": SNAPSHOT_VERSION,
        "tested_observation_sha256": observation["observation_sha256"],
        "materials": materials,
        "all_materials_match": all(row["matches_tested"] for row in materials),
        "boundaries": {
            "digest_only_no_runtime_reexecution": True,
            "not_live_workload_identity": True,
            "runtime_only_bytes_not_embedded": True,
        },
    }
    result["snapshot_sha256"] = _digest(result)
    validate_release_snapshot(result, observation)
    return result


def validate_release_snapshot(
    value: dict[str, Any], observation: dict[str, Any]
) -> dict[str, tuple[int, str]]:
    tested = validate_observation(observation)
    value = _exact(
        value,
        {
            "snapshot_version",
            "tested_observation_sha256",
            "materials",
            "all_materials_match",
            "boundaries",
            "snapshot_sha256",
        },
        "runtime release snapshot",
    )
    if value["snapshot_version"] != SNAPSHOT_VERSION:
        raise ObservationError("runtime release snapshot version is unsupported")
    if value["tested_observation_sha256"] != observation["observation_sha256"]:
        raise ObservationError("runtime release snapshot targets a different observation")
    rows = value["materials"]
    if not isinstance(rows, list) or len(rows) != len(tested):
        raise ObservationError("runtime release snapshot material count is invalid")
    current: dict[str, tuple[int, str]] = {}
    for row in rows:
        row = _exact(
            row,
            {
                "path",
                "size_bytes",
                "sha256",
                "tested_size_bytes",
                "tested_sha256",
                "matches_tested",
            },
            "runtime release material",
        )
        relative = _relative_path(row["path"], "runtime release material path")
        if relative in current or relative not in tested:
            raise ObservationError("runtime release material path is invalid")
        for key in ("size_bytes", "tested_size_bytes"):
            if not isinstance(row[key], int) or not 1 <= row[key] <= MAX_MATERIAL_BYTES:
                raise ObservationError("runtime release material size is invalid")
        digest = _digest_text(row["sha256"], "runtime release material digest")
        tested_digest = _digest_text(
            row["tested_sha256"], "tested runtime material digest"
        )
        expected_size, expected_digest = tested[relative]
        if (row["tested_size_bytes"], tested_digest) != (
            expected_size,
            expected_digest,
        ):
            raise ObservationError("tested runtime material binding is invalid")
        expected_match = (row["size_bytes"], digest) == (
            expected_size,
            expected_digest,
        )
        if row["matches_tested"] is not expected_match:
            raise ObservationError("runtime release material match is invalid")
        current[relative] = (row["size_bytes"], digest)
    if list(current) != sorted(current) or set(current) != set(tested):
        raise ObservationError("runtime release materials must be complete and sorted")
    if value["all_materials_match"] is not all(
        row["matches_tested"] for row in rows
    ):
        raise ObservationError("runtime release aggregate match is invalid")
    boundaries = _exact(
        value["boundaries"],
        {
            "digest_only_no_runtime_reexecution",
            "not_live_workload_identity",
            "runtime_only_bytes_not_embedded",
        },
        "runtime release boundaries",
    )
    if any(item is not True for item in boundaries.values()):
        raise ObservationError("every runtime release boundary must be true")
    unsigned = dict(value)
    supplied = _digest_text(
        unsigned.pop("snapshot_sha256"), "runtime release snapshot digest"
    )
    if supplied != _digest(unsigned):
        raise ObservationError("runtime release snapshot digest mismatch")
    return current


def _load(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_TRACE_BYTES:
        raise ObservationError("receipt must be a bounded regular file")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ObservationError("receipt must contain one JSON object") from exc
    if not isinstance(value, dict):
        raise ObservationError("receipt must contain one JSON object")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    verify = sub.add_parser("verify", help="verify an observation receipt")
    verify.add_argument("observation", type=Path)
    snapshot = sub.add_parser("verify-snapshot", help="verify a release snapshot")
    snapshot.add_argument("snapshot", type=Path)
    snapshot.add_argument("observation", type=Path)
    return parser


def main() -> int:
    try:
        args = _parser().parse_args()
        observation = _load(args.observation)
        if args.action == "verify":
            materials = validate_observation(observation)
            print(
                f"verified runtime observation: {len(materials)} materials, "
                f"{observation['observed_session_count']} sessions"
            )
        else:
            snapshot = _load(args.snapshot)
            materials = validate_release_snapshot(snapshot, observation)
            print(
                f"verified runtime release snapshot: {len(materials)} materials, "
                f"all_match={snapshot['all_materials_match']}"
            )
        return 0
    except (ObservationError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
