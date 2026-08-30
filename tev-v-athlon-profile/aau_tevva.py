"""Machine-readable AAU profile for the NIST AI 200-2 initial public draft.

The tool validates the four TEVV-Athlon stages, verifies public artifact bytes,
derives coverage and visible gaps, and builds a deterministic evidence pack. It is
an independent experimental implementation, not a NIST validator or endorsement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import Any


PROFILE_VERSION = "aau-tevv-athlon-profile/0.1"
ASSESSMENT_VERSION = "aau-tevv-athlon-assessment/0.1"
PACK_VERSION = "aau-tevv-athlon-pack/0.1"
MAX_BYTES = 2_000_000
MAX_ITEMS = 200
HEX64 = re.compile(r"^[0-9a-f]{64}$")
STAGES = (
    "articulate_and_organize",
    "define_and_construct",
    "apply_and_measure",
    "synthesize_and_interrogate",
)


class TevvError(ValueError):
    """Raised when a profile or evidence pack cannot be verified."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(value: Any) -> str:
    return digest_bytes(canonical_bytes(value))


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise TevvError(f"refusing unsafe, missing, or oversized JSON file: {path}")
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TevvError(f"cannot read JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise TevvError(f"JSON root must be an object: {path}")
    return value


def _text(value: Any, label: str, limit: int = 1_000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise TevvError(f"{label} must be non-empty text no longer than {limit} characters")
    return value.strip()


def _list(value: Any, label: str, *, minimum: int = 1) -> list[Any]:
    if not isinstance(value, list) or len(value) < minimum or len(value) > MAX_ITEMS:
        raise TevvError(f"{label} must contain between {minimum} and {MAX_ITEMS} items")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TevvError(f"{label} must be an object")
    if set(value) != keys:
        raise TevvError(
            f"{label} keys differ; missing={sorted(keys-set(value))}, unexpected={sorted(set(value)-keys)}"
        )
    return value


def _ids(rows: Any, label: str) -> list[dict[str, Any]]:
    values = _list(rows, label)
    seen: set[str] = set()
    for index, row in enumerate(values):
        if not isinstance(row, dict):
            raise TevvError(f"{label}[{index}] must be an object")
        item_id = _text(row.get("id"), f"{label}[{index}].id", 160)
        if item_id in seen:
            raise TevvError(f"{label} ids must be unique")
        seen.add(item_id)
    return values


def _string_ids(rows: Any, label: str, *, minimum: int = 1) -> list[str]:
    values = _list(rows, label, minimum=minimum)
    for index, value in enumerate(values):
        _text(value, f"{label}[{index}]", 160)
    if len(set(values)) != len(values):
        raise TevvError(f"{label} must be unique")
    return values


def _safe_relative(value: Any, label: str) -> PurePosixPath:
    text = _text(value, label, 500)
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise TevvError(f"{label} must be a safe repository-relative path")
    return path


def _artifact_path(repository_root: Path, relative: PurePosixPath) -> Path:
    root = repository_root.resolve()
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise TevvError(f"evidence artifact path contains a symlink: {relative}")
    try:
        resolved = current.resolve(strict=True)
    except OSError as exc:
        raise TevvError(f"evidence artifact is missing or unsafe: {relative}") from exc
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise TevvError(f"evidence artifact escapes its declared root: {relative}")
    if resolved.stat().st_size > MAX_BYTES:
        raise TevvError(f"evidence artifact is oversized: {relative}")
    return resolved


def validate_profile(profile: dict[str, Any]) -> None:
    _exact(
        profile,
        {
            "profile_version",
            "profile_id",
            "title",
            "draft_basis",
            *STAGES,
            "evidence_artifacts",
            "claim_boundaries",
        },
        "profile",
    )
    if profile["profile_version"] != PROFILE_VERSION:
        raise TevvError(f"profile_version must be {PROFILE_VERSION}")
    _text(profile["profile_id"], "profile_id", 160)
    _text(profile["title"], "title", 300)

    basis = _exact(
        profile["draft_basis"],
        {"publication", "version", "doi", "reviewed_on", "comment_deadline", "not_nist_endorsement"},
        "draft_basis",
    )
    if basis["publication"] != "NIST AI 200-2" or basis["version"] != "initial_public_draft_august_2026":
        raise TevvError("draft basis must identify NIST AI 200-2 initial public draft")
    if basis["doi"] != "https://doi.org/10.6028/NIST.AI.200-2.ipd":
        raise TevvError("draft DOI is incorrect")
    if basis["comment_deadline"] != "2026-10-06" or basis["not_nist_endorsement"] is not True:
        raise TevvError("draft deadline and non-endorsement boundary must remain explicit")

    stage1 = _exact(
        profile["articulate_and_organize"],
        {"goal", "stakeholders", "lifecycle_stages", "system_attributes", "time_cost_scope", "organizational_decision", "challenges"},
        STAGES[0],
    )
    _text(stage1["goal"], "stage 1 goal")
    for key in ("stakeholders", "lifecycle_stages", "system_attributes", "challenges"):
        _string_ids(stage1[key], f"stage 1 {key}")
    _text(stage1["time_cost_scope"], "stage 1 time_cost_scope")
    _text(stage1["organizational_decision"], "stage 1 organizational_decision")

    stage2 = _exact(profile["define_and_construct"], {"blocks"}, STAGES[1])
    blocks = _ids(stage2["blocks"], "blocks")
    block_ids = {row["id"] for row in blocks}
    for index, block in enumerate(blocks):
        _exact(
            block,
            {"id", "characteristic", "definition", "evidence_required", "success_interpretation", "failure_interpretation"},
            f"blocks[{index}]",
        )
        for key in ("characteristic", "definition", "success_interpretation", "failure_interpretation"):
            _text(block[key], f"blocks[{index}].{key}")
        for item in _list(block["evidence_required"], f"blocks[{index}].evidence_required"):
            _text(item, "required evidence", 300)

    stage3 = _exact(profile["apply_and_measure"], {"events", "toolbox", "protocol"}, STAGES[2])
    tools = _ids(stage3["toolbox"], "toolbox")
    tool_ids = {row["id"] for row in tools}
    for index, tool in enumerate(tools):
        _exact(
            tool,
            {"id", "method", "implementation_path", "human_review", "executes_live_system"},
            f"toolbox[{index}]",
        )
        _text(tool["method"], f"toolbox[{index}].method")
        _safe_relative(tool["implementation_path"], f"toolbox[{index}].implementation_path")
        if not isinstance(tool["human_review"], bool) or tool["executes_live_system"] is not False:
            raise TevvError("toolbox must declare human review and prohibit live execution")
    events = _ids(stage3["events"], "events")
    for index, event in enumerate(events):
        _exact(
            event,
            {
                "id",
                "title",
                "status",
                "independent_reproduction",
                "block_ids",
                "tool_ids",
                "evidence_artifact_ids",
            },
            f"events[{index}]",
        )
        _text(event["title"], f"events[{index}].title", 300)
        if event["status"] not in {"observed", "planned", "not_applicable"}:
            raise TevvError("event status is invalid")
        if not isinstance(event["independent_reproduction"], bool):
            raise TevvError("event independent_reproduction must be boolean")
        if not set(_string_ids(event["block_ids"], "event block_ids")).issubset(block_ids):
            raise TevvError("event references an unknown Block")
        if not set(_string_ids(event["tool_ids"], "event tool_ids")).issubset(tool_ids):
            raise TevvError("event references an unknown Tool")
        _string_ids(event["evidence_artifact_ids"], "event evidence_artifact_ids", minimum=0)
        if event["status"] == "observed" and not event["evidence_artifact_ids"]:
            raise TevvError("observed events require evidence artifacts")
    protocol = _exact(
        stage3["protocol"],
        {"predeclared", "held_out_material", "clean_twins", "repeats", "environment", "human_participant_data"},
        "apply_and_measure.protocol",
    )
    for key in ("predeclared", "held_out_material", "clean_twins"):
        if not isinstance(protocol[key], bool):
            raise TevvError(f"protocol.{key} must be boolean")
    if type(protocol["repeats"]) is not int or protocol["repeats"] < 1:
        raise TevvError("protocol.repeats must be positive")
    _text(protocol["environment"], "protocol.environment", 500)
    if protocol["human_participant_data"] is not False:
        raise TevvError("reference profile must not include human participant data")

    stage4 = _exact(
        profile["synthesize_and_interrogate"],
        {"analysis_plan", "joint_analysis", "decision_owner", "decision_boundary", "reporting_outputs", "goodhart_controls", "transfer_limits"},
        STAGES[3],
    )
    for key in ("analysis_plan", "joint_analysis", "decision_owner", "decision_boundary"):
        _text(stage4[key], f"stage 4 {key}")
    for key in ("reporting_outputs", "goodhart_controls", "transfer_limits"):
        for item in _list(stage4[key], f"stage 4 {key}"):
            _text(item, f"stage 4 {key} item", 500)

    artifacts = _ids(profile["evidence_artifacts"], "evidence_artifacts")
    artifact_ids = {row["id"] for row in artifacts}
    artifact_paths: set[PurePosixPath] = set()
    for index, artifact in enumerate(artifacts):
        _exact(artifact, {"id", "stage", "path", "sha256", "kind", "public_synthetic"}, f"evidence_artifacts[{index}]")
        if artifact["stage"] not in STAGES:
            raise TevvError("evidence artifact stage is invalid")
        artifact_path = _safe_relative(artifact["path"], f"evidence_artifacts[{index}].path")
        if artifact_path in artifact_paths:
            raise TevvError("evidence artifact paths must be unique")
        artifact_paths.add(artifact_path)
        if not isinstance(artifact["sha256"], str) or not HEX64.fullmatch(artifact["sha256"]):
            raise TevvError("evidence artifact digest must be SHA-256")
        _text(artifact["kind"], "evidence artifact kind", 160)
        if artifact["public_synthetic"] is not True:
            raise TevvError("reference artifacts must be explicitly public and synthetic")
    for event in events:
        if not set(event["evidence_artifact_ids"]).issubset(artifact_ids):
            raise TevvError("event references an unknown evidence artifact")

    boundaries = profile["claim_boundaries"]
    if boundaries != {
        "not_nist_conformance": True,
        "not_certification": True,
        "not_compliance_finding": True,
        "not_deployment_authorization": True,
        "not_government_endorsement": True,
        "no_universal_score": True,
    }:
        raise TevvError("claim boundaries must preserve every non-claim")


def assess(profile: dict[str, Any], repository_root: Path) -> dict[str, Any]:
    validate_profile(profile)
    artifacts = []
    for artifact in profile["evidence_artifacts"]:
        relative = _safe_relative(artifact["path"], "artifact path")
        path = _artifact_path(repository_root, relative)
        actual = digest_bytes(path.read_bytes())
        if actual != artifact["sha256"]:
            raise TevvError(f"evidence artifact digest differs: {relative}")
        artifacts.append({**artifact, "bytes_verified": True, "size": path.stat().st_size})

    block_events: dict[str, list[str]] = {
        block["id"]: [] for block in profile["define_and_construct"]["blocks"]
    }
    event_rows = []
    for event in profile["apply_and_measure"]["events"]:
        for block_id in event["block_ids"]:
            block_events[block_id].append(event["id"])
        event_rows.append(
            {
                "event_id": event["id"],
                "status": event["status"],
                "independent_reproduction": event["independent_reproduction"],
                "block_count": len(event["block_ids"]),
                "tool_count": len(event["tool_ids"]),
                "artifact_count": len(event["evidence_artifact_ids"]),
            }
        )
    uncovered = sorted(block_id for block_id, event_ids in block_events.items() if not event_ids)
    planned = sorted(row["event_id"] for row in event_rows if row["status"] == "planned")
    observed = sorted(row["event_id"] for row in event_rows if row["status"] == "observed")
    visible_gaps = []
    if uncovered:
        visible_gaps.append("blocks_without_events")
    if planned:
        visible_gaps.append("planned_events_not_observed")
    if not profile["apply_and_measure"]["protocol"]["held_out_material"]:
        visible_gaps.append("no_held_out_material")
    if not any(
        event["independent_reproduction"] and event["status"] == "observed"
        for event in profile["apply_and_measure"]["events"]
    ):
        visible_gaps.append("no_observed_independent_reproduction")
    status = "structurally_complete_with_visible_gaps" if visible_gaps else "structurally_complete"
    result = {
        "assessment_version": ASSESSMENT_VERSION,
        "profile_id": profile["profile_id"],
        "profile_sha256": digest(profile),
        "draft_basis": profile["draft_basis"],
        "stage_coverage": {
            STAGES[0]: {"present": True, "stakeholder_count": len(profile[STAGES[0]]["stakeholders"])},
            STAGES[1]: {"present": True, "block_count": len(block_events), "uncovered_block_ids": uncovered},
            STAGES[2]: {"present": True, "observed_event_ids": observed, "planned_event_ids": planned, "tool_count": len(profile[STAGES[2]]["toolbox"])},
            STAGES[3]: {"present": True, "reporting_output_count": len(profile[STAGES[3]]["reporting_outputs"])},
        },
        "events": event_rows,
        "artifacts": artifacts,
        "status": status,
        "visible_gaps": visible_gaps,
        "claim_boundaries": profile["claim_boundaries"],
    }
    result["assessment_sha256"] = digest(result)
    return result


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n")


def _pack_readme(profile: dict[str, Any], assessment: dict[str, Any]) -> str:
    return (
        "# AAU TEVV-Athlon evidence pack\n\n"
        f"Profile: `{profile['profile_id']}`\n\n"
        f"Derived status: **{assessment['status']}**\n\n"
        f"Visible gaps: **{', '.join(assessment['visible_gaps']) or 'none'}**\n\n"
        "This is an independent experimental profile of the NIST AI 200-2 initial public draft. "
        "It is not NIST conformance, certification, compliance, deployment authorization, or "
        "government endorsement.\n"
    )


def build_pack(profile_path: Path, repository_root: Path, out: Path) -> dict[str, Any]:
    if out.exists():
        raise TevvError(f"refusing to overwrite existing path: {out}")
    profile = load_json(profile_path)
    assessment = assess(profile, repository_root)
    out.mkdir(parents=False)
    try:
        _write_json(out / "profile.json", profile)
        _write_json(out / "assessment.json", assessment)
        evidence_index = []
        for artifact in profile["evidence_artifacts"]:
            source_rel = _safe_relative(artifact["path"], "artifact path")
            source = _artifact_path(repository_root, source_rel)
            target_rel = PurePosixPath("artifacts") / source_rel
            target = out.joinpath(*target_rel.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            evidence_index.append({"id": artifact["id"], "path": str(target_rel), "sha256": artifact["sha256"], "size": source.stat().st_size})
        _write_json(out / "evidence-index.json", {"artifacts": evidence_index})
        (out / "README.md").write_text(_pack_readme(profile, assessment))
        files = []
        for path in sorted(item for item in out.rglob("*") if item.is_file()):
            relative = path.relative_to(out).as_posix()
            data = path.read_bytes()
            files.append({"path": relative, "sha256": digest_bytes(data), "size": len(data)})
        _write_json(out / "manifest.json", {"pack_version": PACK_VERSION, "files": files})
        return {"pack": str(out), "status": assessment["status"], "artifact_count": len(evidence_index)}
    except Exception:
        shutil.rmtree(out)
        raise


def verify_pack(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_dir():
        raise TevvError("pack must be a regular directory")
    manifest = load_json(path / "manifest.json")
    if manifest.get("pack_version") != PACK_VERSION or not isinstance(manifest.get("files"), list):
        raise TevvError("manifest is malformed")
    if not manifest["files"] or len(manifest["files"]) > MAX_ITEMS:
        raise TevvError("manifest file list is empty or oversized")
    entries = list(path.rglob("*"))
    if len(entries) > MAX_ITEMS:
        raise TevvError("pack contains too many entries")
    for item in entries:
        mode = item.lstat().st_mode
        if item.is_symlink():
            raise TevvError(f"pack contains a symlink: {item.relative_to(path)}")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise TevvError(f"pack contains a non-regular entry: {item.relative_to(path)}")
        if item.stat().st_size > MAX_BYTES:
            raise TevvError(f"pack entry is oversized: {item.relative_to(path)}")
    actual_paths = sorted(
        item.relative_to(path).as_posix()
        for item in entries
        if item != path / "manifest.json" and item.is_file()
    )
    if any(not isinstance(row, dict) or set(row) != {"path", "sha256", "size"} for row in manifest["files"]):
        raise TevvError("manifest file entries are malformed")
    listed = [row["path"] for row in manifest["files"]]
    if listed != actual_paths or listed != sorted(set(listed)):
        raise TevvError("manifest and pack file set differ")
    for row in manifest["files"]:
        relative = _safe_relative(row["path"], "manifest path")
        target = path.joinpath(*relative.parts)
        data = target.read_bytes()
        if row != {"path": row["path"], "sha256": digest_bytes(data), "size": len(data)}:
            raise TevvError(f"manifest binding differs: {row['path']}")
    profile = load_json(path / "profile.json")
    assessment = load_json(path / "assessment.json")
    expected_assessment = assess(profile, path / "artifacts")
    if assessment != expected_assessment:
        raise TevvError("assessment differs from deterministic recomputation")
    if (path / "README.md").read_text() != _pack_readme(profile, assessment):
        raise TevvError("pack README differs from deterministic recomputation")
    index = load_json(path / "evidence-index.json")
    expected_index = []
    for artifact in profile["evidence_artifacts"]:
        target_rel = PurePosixPath("artifacts") / _safe_relative(artifact["path"], "artifact path")
        target = path.joinpath(*target_rel.parts)
        data = target.read_bytes()
        if digest_bytes(data) != artifact["sha256"]:
            raise TevvError(f"packed evidence differs: {target_rel}")
        expected_index.append({"id": artifact["id"], "path": str(target_rel), "sha256": artifact["sha256"], "size": len(data)})
    if index != {"artifacts": expected_index}:
        raise TevvError("evidence index differs")
    return {
        "status": "verified_experimental_profile",
        "profile_id": profile["profile_id"],
        "assessment_status": assessment["status"],
        "visible_gaps": assessment["visible_gaps"],
        "not_nist_conformance": True,
    }


def _emit(value: Any, out: Path | None = None) -> None:
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if out is None:
        sys.stdout.write(rendered)
    else:
        if out.exists():
            raise TevvError(f"refusing to overwrite existing path: {out}")
        out.write_text(rendered)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("profile", type=Path)
    assess_command = commands.add_parser("assess")
    assess_command.add_argument("profile", type=Path)
    assess_command.add_argument("--root", type=Path, default=Path.cwd())
    assess_command.add_argument("--out", type=Path)
    pack = commands.add_parser("pack")
    pack.add_argument("profile", type=Path)
    pack.add_argument("--root", type=Path, default=Path.cwd())
    pack.add_argument("--out", type=Path, required=True)
    verify = commands.add_parser("verify-pack")
    verify.add_argument("path", type=Path)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "validate":
            profile = load_json(args.profile)
            validate_profile(profile)
            _emit({"status": "valid_experimental_profile", "profile_sha256": digest(profile)})
        elif args.command == "assess":
            _emit(assess(load_json(args.profile), args.root.resolve()), args.out)
        elif args.command == "pack":
            _emit(build_pack(args.profile, args.root.resolve(), args.out))
        elif args.command == "verify-pack":
            _emit(verify_pack(args.path))
    except TevvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
