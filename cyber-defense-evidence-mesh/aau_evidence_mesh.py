"""Build a privacy-bounded interchange pack from public defensive receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any


CONTRACT_VERSION = "aau-cyber-defense-evidence-mesh/0.2"
INDEX_VERSION = "aau-cyber-defense-evidence-index/0.2"
PACK_VERSION = "aau-cyber-defense-evidence-pack/0.2"
ADJUDICATION_VERSION = "aau-independent-reproduction-adjudication/0.1"
MAX_BYTES = 2_000_000
VERSIONS = {
    "verified_fix": ("receipt_version", "aau-verified-fix-receipt/0.1"),
    "containment_drill": ("receipt_version", "aau-agent-containment-receipt/0.1"),
    "defender_campaign": ("assessment_version", "aau-essential-service-campaign-assessment/0.1"),
    "defense_benchmark": ("receipt_version", "aau-frontier-defense-receipt/0.1"),
}
BOUNDARIES = {
    "public_safe_artifacts_only", "raw_logs_excluded", "personal_data_excluded",
    "credentials_and_targets_excluded", "aggregate_outcomes_only",
    "not_a_threat_intelligence_feed", "not_a_certification",
}


class MeshError(ValueError):
    """Raised when mesh data violates its public contract."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise MeshError(f"invalid, oversized, or symbolic-link input: {path}")
    try:
        value = json.loads(path.read_text())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MeshError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MeshError("expected one JSON object")
    return value


def _text(value: Any, label: str, limit: int = 400) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise MeshError(f"{label} must be non-empty text of at most {limit} characters")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise MeshError(f"{label} fields differ from the 0.2 contract")
    return value


def _safe_path(value: Any) -> PurePosixPath:
    path = PurePosixPath(_text(value, "artifact path", 240))
    if path.is_absolute() or ".." in path.parts or path.suffix != ".json":
        raise MeshError("artifact path must be a relative JSON path without parent traversal")
    return path


def _safe_pack_path(value: Any) -> PurePosixPath:
    path = PurePosixPath(_text(value, "reproduction pack path", 240))
    if path.is_absolute() or ".." in path.parts or path.suffix:
        raise MeshError("reproduction pack path must be a relative directory without parent traversal")
    return path


def validate_contract(contract: dict[str, Any]) -> None:
    _exact(contract, {"mesh_version", "mesh_id", "title", "producer", "artifacts", "boundaries"}, "mesh contract")
    if contract["mesh_version"] != CONTRACT_VERSION:
        raise MeshError(f"mesh_version must be {CONTRACT_VERSION}")
    for key in ("mesh_id", "title", "producer"):
        _text(contract[key], key, 220)
    artifacts = contract["artifacts"]
    if not isinstance(artifacts, list) or not (1 <= len(artifacts) <= 100):
        raise MeshError("artifacts must contain between 1 and 100 entries")
    seen: set[str] = set()
    for index, item in enumerate(artifacts):
        _exact(item, {"artifact_id", "kind", "path", "evidence_level", "producer", "reproduction_pack_path"}, f"artifacts[{index}]")
        artifact_id = _text(item["artifact_id"], "artifact_id", 100)
        if artifact_id in seen:
            raise MeshError(f"duplicate artifact_id: {artifact_id}")
        seen.add(artifact_id)
        if item["kind"] not in VERSIONS:
            raise MeshError(f"unsupported artifact kind: {item['kind']}")
        _safe_path(item["path"])
        if item["evidence_level"] not in {"designed", "synthetic_reference", "reference_exact", "independently_reproduced"}:
            raise MeshError("unsupported evidence_level")
        _text(item["producer"], "artifact producer", 220)
        reproduction_pack_path = item["reproduction_pack_path"]
        if reproduction_pack_path is not None:
            _safe_pack_path(reproduction_pack_path)
        if item["evidence_level"] == "independently_reproduced" and reproduction_pack_path is None:
            raise MeshError("independently_reproduced requires a verified reproduction_pack_path")
        if item["evidence_level"] != "independently_reproduced" and reproduction_pack_path is not None:
            raise MeshError("reproduction_pack_path is reserved for independently_reproduced evidence")
    boundary = _exact(contract["boundaries"], BOUNDARIES, "boundaries")
    if any(boundary[key] is not True for key in BOUNDARIES):
        raise MeshError("all evidence-sharing boundaries must be true")


def _artifact_path(contract_path: Path, relative: str) -> Path:
    root = contract_path.resolve().parent
    target = (root / relative).resolve()
    if root not in target.parents:
        raise MeshError(f"artifact escapes contract directory: {relative}")
    return target


def _verify_embedded_digest(kind: str, artifact: dict[str, Any]) -> None:
    if kind not in {"verified_fix", "containment_drill"}:
        return
    supplied = artifact.get("receipt_sha256")
    unsigned = dict(artifact)
    unsigned.pop("receipt_sha256", None)
    if supplied != digest(unsigned):
        raise MeshError(f"{kind} embedded receipt digest mismatch")


def _reproduction_summary(
    contract_path: Path, declaration: dict[str, Any], artifact_path: Path,
) -> dict[str, Any] | None:
    relative = declaration["reproduction_pack_path"]
    if relative is None:
        return None
    pack = _artifact_path(contract_path, relative)
    try:
        from aau_reproduction import ReproductionError, verify_pack
    except ImportError as exc:
        raise MeshError("independent evidence requires the aau-independent-reproduction-exchange verifier") from exc
    try:
        adjudication = verify_pack(pack)
    except ReproductionError as exc:
        raise MeshError(f"reproduction pack does not verify: {exc}") from exc
    if adjudication["adjudication_version"] != ADJUDICATION_VERSION:
        raise MeshError("reproduction pack uses an unsupported adjudication")
    subject = adjudication["subject"]
    if not isinstance(subject, dict) or set(subject) != {"name", "kind", "sha256"}:
        raise MeshError("reproduction adjudication subject is invalid")
    if subject["kind"] != declaration["kind"] or subject["sha256"] != digest(artifact_path.read_bytes()):
        raise MeshError("reproduction adjudication does not bind the declared artifact bytes and kind")
    roles = adjudication["role_commitments"]
    review = adjudication["role_review"]
    if (
        adjudication["status"] != "independence_reviewed"
        or adjudication["evidence_level"] != "independently_reproduced"
        or not isinstance(roles, dict)
        or set(roles) != {"issuer", "producer", "reviewer"}
        or len(set(roles.values())) != 3
        or not isinstance(review, dict)
        or review.get("commitments_distinct") is not True
        or review.get("relationships_declared_independent") is not True
        or review.get("relationship_evidence_human_reviewed") is not True
        or review.get("independence_cryptographically_proved") is not False
    ):
        raise MeshError("reproduction adjudication does not satisfy the reviewed-independence gate")
    return {
        "adjudication_sha256": digest((pack / "adjudication.json").read_bytes()),
        "challenge_sha256": adjudication["challenge_sha256"],
        "role_commitments_distinct": True,
        "relationships_declared_independent": True,
        "independence_cryptographically_proved": False,
    }


def _measurements(kind: str, artifact: dict[str, Any]) -> dict[str, Any]:
    summary = artifact.get("summary")
    if not isinstance(summary, dict):
        raise MeshError(f"{kind} artifact is missing summary")
    allowed = {
        "verified_fix": {"case_count", "after_pass_rate", "unsafe_after_count", "continuity_preservation_rate"},
        "containment_drill": {"event_count", "containment_breach_count", "post_control_block_count", "unauthorized_restart_block_count"},
        "defender_campaign": {"asset_count", "decision_count", "known_exploited_decision_count", "gate_pass_count", "gate_fail_count"},
        "defense_benchmark": {"task_count", "exact_count", "unsafe_count", "human_boundary_failure_count", "service_boundary_failure_count"},
    }[kind]
    return {key: summary[key] for key in sorted(allowed) if key in summary}


def _fingerprints(kind: str, artifact: dict[str, Any]) -> list[str]:
    if kind == "verified_fix":
        return sorted({row["case_kind"] for row in artifact.get("cases", [])})
    if kind == "containment_drill":
        return sorted({row["kind"] for run in artifact.get("runs", []) for row in run.get("events", [])})
    if kind == "defender_campaign":
        return sorted({f"route:{row['recommended_route']}" for row in artifact.get("decisions", [])})
    return sorted(artifact.get("families", {}).keys())


def build_index(contract_path: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    validate_contract(contract)
    records = []
    for declaration in contract["artifacts"]:
        source = _artifact_path(contract_path, declaration["path"])
        artifact = load_json(source)
        version_field, expected_version = VERSIONS[declaration["kind"]]
        if artifact.get(version_field) != expected_version:
            raise MeshError(f"{declaration['artifact_id']} has an unexpected artifact version")
        _verify_embedded_digest(declaration["kind"], artifact)
        reproduction = _reproduction_summary(contract_path, declaration, source)
        records.append({
            "artifact_id": declaration["artifact_id"],
            "kind": declaration["kind"],
            "artifact_version": expected_version,
            "artifact_sha256": digest(source.read_bytes()),
            "evidence_level": declaration["evidence_level"],
            "producer": declaration["producer"],
            "reproduction": reproduction,
            "measurements": _measurements(declaration["kind"], artifact),
            "control_fingerprints": _fingerprints(declaration["kind"], artifact),
        })
    return {
        "index_version": INDEX_VERSION,
        "mesh_id": contract["mesh_id"],
        "contract_sha256": digest(contract),
        "record_count": len(records),
        "records": records,
        "interchange": {
            "openvex": "Verified Fix packs expose a public/synthetic exploitability statement.",
            "sarif": "Verified Fix packs expose per-case analysis results.",
            "opentelemetry": "The included map is experimental and emits no telemetry.",
            "abp": "Fingerprints align receipts with Agent Boundary Protocol control shapes.",
        },
        "claim_boundary": {
            "aggregate_public_evidence_only": True,
            "no_raw_logs_or_personal_data": True,
            "no_organizational_comparison": True,
            "not_threat_intelligence_or_certification": True,
        },
    }


def _otel_map() -> dict[str, Any]:
    return {
        "map_version": "aau-otel-agent-defense-map/0.1",
        "status": "experimental",
        "source": "https://github.com/open-telemetry/semantic-conventions-genai",
        "mappings": [
            {"aau": "artifact.kind", "otel_candidate": "gen_ai.operation.name", "note": "Defensive operation category."},
            {"aau": "control_fingerprint", "otel_candidate": "aau.agent.control.name", "note": "AAU extension, not a standard attribute."},
            {"aau": "artifact_sha256", "otel_candidate": "aau.evidence.artifact.sha256", "note": "AAU extension for evidence binding."},
        ],
        "boundary": "Naming bridge only; not emitted telemetry or a standards claim.",
    }


def build_pack(contract_path: Path, out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise MeshError(f"refusing to overwrite existing evidence mesh pack: {out}")
    index = build_index(contract_path)
    out.mkdir(parents=True)
    shutil.copyfile(contract_path, out / "mesh-contract.json")
    (out / "evidence-index.json").write_text(json.dumps(index, indent=2) + "\n")
    (out / "otel-attribute-map.json").write_text(json.dumps(_otel_map(), indent=2) + "\n")
    (out / "README.md").write_text(
        "# Cyber Defense Evidence Mesh pack\n\n"
        "Aggregate public-safe evidence bindings only. Raw logs, personal data, credentials, targets, "
        "and operational details are excluded. Not threat intelligence, certification, or a ranking.\n"
    )
    files = [
        {"path": path.name, "sha256": digest(path.read_bytes()), "bytes": path.stat().st_size}
        for path in sorted(out.iterdir()) if path.name != "manifest.json"
    ]
    (out / "manifest.json").write_text(json.dumps({"manifest_version": PACK_VERSION, "files": files}, indent=2) + "\n")


def verify_pack(pack: Path) -> None:
    if pack.is_symlink() or not pack.is_dir():
        raise MeshError(f"invalid evidence mesh pack: {pack}")
    manifest = load_json(pack / "manifest.json")
    if manifest.get("manifest_version") != PACK_VERSION or not isinstance(manifest.get("files"), list):
        raise MeshError("invalid evidence mesh manifest")
    expected = {"README.md", "evidence-index.json", "mesh-contract.json", "otel-attribute-map.json"}
    if {item.get("path") for item in manifest["files"]} != expected:
        raise MeshError("manifest file set differs from the 0.2 pack")
    for item in manifest["files"]:
        path = pack / item["path"]
        if path.is_symlink() or not path.is_file():
            raise MeshError(f"missing or symbolic-link pack file: {item['path']}")
        if digest(path.read_bytes()) != item.get("sha256") or path.stat().st_size != item.get("bytes"):
            raise MeshError(f"pack file integrity mismatch: {item['path']}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="aau-evidence-mesh", description="Build a public-safe evidence interchange pack.")
    sub = root.add_subparsers(dest="command", required=True)
    validating = sub.add_parser("validate")
    validating.add_argument("contract", type=Path)
    building = sub.add_parser("build")
    building.add_argument("contract", type=Path)
    building.add_argument("--out", type=Path, required=True)
    verifying = sub.add_parser("verify-pack")
    verifying.add_argument("pack", type=Path)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "validate":
            build_index(args.contract)
            print(f"OK: {args.contract} and its artifacts are valid.")
        elif args.command == "build":
            build_pack(args.contract, args.out)
            print(f"OK: evidence mesh pack written to {args.out}.")
        else:
            verify_pack(args.pack)
            print(f"OK: {args.pack} verified.")
        return 0
    except MeshError as exc:
        print(f"aau-evidence-mesh: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
