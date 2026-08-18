#!/usr/bin/env python3
"""Validate, package, compare, and verify AAU federal mission profiles.

The tool has no third-party dependencies and makes no network requests.  Its validation
is intentionally structural and semantic; it does not make a compliance determination.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


VERSION = "aau-federal-mission-assurance/0.1"
CONTROL_STATUSES = {"gap", "planned", "evidenced", "not_applicable"}
REQUIRED_SECTIONS = (
    "mission",
    "impact",
    "authority",
    "data",
    "acquisition",
    "testing",
    "oversight",
    "monitoring",
)
PACK_NAMES = (
    "README.md",
    "federal-profile.json",
    "01-use-case-inventory.md",
    "02-high-impact-determination.md",
    "03-impact-assessment.md",
    "04-tev-test-plan.md",
    "05-risk-register.md",
    "06-human-oversight-and-appeals.md",
    "07-data-model-provenance.md",
    "08-acquisition-acceptance.md",
    "09-monitoring-notice-and-cease-use.md",
    "manifest.json",
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError("profile root must be a JSON object")
    return value


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def parse_iso(value: Any, *, datetime_value: bool = False) -> bool:
    if not isinstance(value, str):
        return False
    try:
        (datetime.fromisoformat(value.replace("Z", "+00:00")) if datetime_value else date.fromisoformat(value))
    except ValueError:
        return False
    return True


def validate_profile(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    def section(name: str) -> dict[str, Any]:
        value = profile.get(name)
        if not isinstance(value, dict):
            errors.append(f"{name} must be an object")
            return {}
        return value

    def string_list(value: Any, path: str, *, required: bool = True) -> list[str]:
        if not isinstance(value, list):
            errors.append(f"{path} must be an array")
            return []
        valid = [item for item in value if nonempty(item)]
        if len(valid) != len(value):
            errors.append(f"{path} must contain non-empty strings")
        if required and not valid:
            errors.append(f"{path} needs at least one value")
        return valid

    if profile.get("profile_version") != VERSION:
        errors.append(f"profile_version must equal {VERSION!r}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", str(profile.get("profile_id", ""))):
        errors.append("profile_id must be a 3-64 character lowercase slug")
    if not parse_iso(profile.get("created_at"), datetime_value=True):
        errors.append("created_at must be an ISO 8601 date-time")
    if profile.get("status") not in {"draft", "domain_review", "evidence_ready", "retired"}:
        errors.append("status must be draft, domain_review, evidence_ready, or retired")
    sections = {name: section(name) for name in REQUIRED_SECTIONS}
    mission = sections["mission"]
    for field in ("title", "problem", "baseline"):
        if not nonempty(mission.get(field)):
            errors.append(f"mission.{field} is required")
    if mission.get("agency_context") not in {
        "federal_civilian", "defense_or_intelligence", "state_local_tribal_territorial",
        "public_vendor", "other",
    }:
        errors.append("mission.agency_context has an invalid value")
    string_list(mission.get("affected_groups"), "mission.affected_groups")
    benefits = mission.get("expected_benefits")
    if not isinstance(benefits, list) or not benefits:
        errors.append("mission.expected_benefits needs at least one measurable benefit")
    else:
        for index, benefit in enumerate(benefits):
            if not isinstance(benefit, dict):
                errors.append(f"mission.expected_benefits[{index}] must be an object")
                continue
            for field in ("metric", "target", "measurement"):
                if not nonempty(benefit.get(field)):
                    errors.append(f"mission.expected_benefits[{index}].{field} is required")

    impact = sections["impact"]
    if impact.get("high_impact_determination") not in {"yes", "no", "uncertain"}:
        errors.append("impact.high_impact_determination must be yes, no, or uncertain")
    if not nonempty(impact.get("rationale")):
        errors.append("impact.rationale is required")
    string_list(impact.get("decision_effects"), "impact.decision_effects")
    string_list(impact.get("rights_safety_impacts"), "impact.rights_safety_impacts")

    authority = sections["authority"]
    for field in ("accountable_owner", "human_decision_owner", "risk_acceptance_owner"):
        if not nonempty(authority.get(field)):
            errors.append(f"authority.{field} is required")
    string_list(authority.get("prohibited_agent_actions"), "authority.prohibited_agent_actions")

    data = sections["data"]
    if data.get("classification") not in {
        "public", "controlled_unclassified", "sensitive_unclassified", "classified",
        "mixed", "unknown",
    }:
        errors.append("data.classification has an invalid value")
    for field in ("contains_pii", "synthetic_or_public_only"):
        if not isinstance(data.get(field), bool):
            errors.append(f"data.{field} must be a boolean")
    for field in ("training_use", "retention"):
        if not nonempty(data.get(field)):
            errors.append(f"data.{field} is required")
    string_list(data.get("provenance"), "data.provenance")

    acquisition = sections["acquisition"]
    if not isinstance(acquisition.get("vendor_involved"), bool):
        errors.append("acquisition.vendor_involved must be a boolean")
    string_list(acquisition.get("performance_metrics"), "acquisition.performance_metrics")
    for field in ("data_rights", "portability", "pricing", "exit_plan"):
        if not nonempty(acquisition.get(field)):
            errors.append(f"acquisition.{field} is required")

    testing = sections["testing"]
    if not nonempty(testing.get("intended_environment")):
        errors.append("testing.intended_environment is required")
    if not isinstance(testing.get("minimum_scenarios"), int) or testing.get("minimum_scenarios", 0) < 20:
        errors.append("testing.minimum_scenarios must be at least 20")
    if not isinstance(testing.get("minimum_repeats"), int) or testing.get("minimum_repeats", 0) < 3:
        errors.append("testing.minimum_repeats must be at least 3")
    string_list(testing.get("acceptance_thresholds"), "testing.acceptance_thresholds")
    if not nonempty(testing.get("independent_reviewer")):
        errors.append("testing.independent_reviewer is required")
    string_list(testing.get("transfer_traps"), "testing.transfer_traps")

    oversight = sections["oversight"]
    for field in ("review_point", "intervention", "failsafe", "appeal_or_remedy", "operator_training"):
        if not nonempty(oversight.get(field)):
            errors.append(f"oversight.{field} is required")

    monitoring = sections["monitoring"]
    string_list(monitoring.get("metrics"), "monitoring.metrics")
    for field in ("cadence", "feedback_channel", "incident_route", "cease_use_trigger", "reassessment_trigger"):
        if not nonempty(monitoring.get(field)):
            errors.append(f"monitoring.{field} is required")

    controls = profile.get("controls")
    if not isinstance(controls, list) or len(controls) < 8:
        errors.append("controls needs at least eight mapped controls")
        controls = []
    control_ids: set[str] = set()
    artifacts_raw = profile.get("artifacts", [])
    artifact_paths = {
        item.get("path")
        for item in artifacts_raw if isinstance(artifacts_raw, list)
        if isinstance(item, dict) and nonempty(item.get("path"))
    }
    known_evidence_refs = artifact_paths | (set(PACK_NAMES) - {"manifest.json"})
    sources_raw = profile.get("sources", [])
    source_ids = {
        item.get("source_id")
        for item in sources_raw if isinstance(sources_raw, list)
        if isinstance(item, dict) and nonempty(item.get("source_id"))
    }
    for index, control in enumerate(controls):
        if not isinstance(control, dict):
            errors.append(f"controls[{index}] must be an object")
            continue
        control_id = control.get("control_id")
        if not nonempty(control_id):
            errors.append(f"controls[{index}].control_id is required")
        elif control_id in control_ids:
            errors.append(f"duplicate control_id: {control_id}")
        else:
            control_ids.add(control_id)
        if control.get("status") not in CONTROL_STATUSES:
            errors.append(f"{control_id or f'controls[{index}]'} has an invalid status")
        if control.get("framework") not in {"OMB-M-25-21", "OMB-M-25-22", "NIST-AI-RMF", "GAO-HIGH-RISK"}:
            errors.append(f"{control_id or f'controls[{index}]'} has an invalid framework")
        for field in ("title", "owner"):
            if not nonempty(control.get(field)):
                errors.append(f"{control_id or f'controls[{index}]'}.{field} is required")
        if control.get("applicability") not in {"required", "recommended", "not_applicable"}:
            errors.append(f"{control_id or f'controls[{index}]'} has an invalid applicability")
        if control.get("status") == "not_applicable" and control.get("applicability") != "not_applicable":
            errors.append(f"{control_id} status not_applicable needs matching applicability")
        if control.get("status") == "evidenced" and not control.get("evidence_refs"):
            errors.append(f"{control_id} is evidenced but declares no evidence_refs")
        evidence_refs_raw = control.get("evidence_refs", [])
        if not isinstance(evidence_refs_raw, list):
            errors.append(f"{control_id or f'controls[{index}]'}.evidence_refs must be an array")
            evidence_refs_raw = []
        evidence_refs = [item for item in evidence_refs_raw if nonempty(item)]
        if len(evidence_refs) != len(evidence_refs_raw):
            errors.append(f"{control_id or f'controls[{index}]'}.evidence_refs must contain non-empty strings")
        unknown_evidence = set(evidence_refs) - known_evidence_refs
        if unknown_evidence:
            errors.append(f"{control_id} references undeclared evidence: {sorted(unknown_evidence)}")
        control_sources_raw = control.get("source_ids", [])
        if not isinstance(control_sources_raw, list):
            errors.append(f"{control_id or f'controls[{index}]'}.source_ids must be an array")
            control_sources_raw = []
        control_sources = [item for item in control_sources_raw if nonempty(item)]
        if len(control_sources) != len(control_sources_raw):
            errors.append(f"{control_id or f'controls[{index}]'}.source_ids must contain non-empty strings")
        unknown_sources = set(control_sources) - source_ids
        if unknown_sources:
            errors.append(f"{control_id} references unknown source IDs: {sorted(unknown_sources)}")

    if not isinstance(sources_raw, list) or not sources_raw:
        errors.append("sources needs at least one declared source")
        sources_raw = []
    if len(source_ids) != len(sources_raw):
        errors.append("source IDs must be non-empty and unique")
    for index, source in enumerate(sources_raw):
        if not isinstance(source, dict):
            errors.append(f"sources[{index}] must be an object")
            continue
        for field in ("source_id", "title", "authority", "jurisdiction"):
            if not nonempty(source.get(field)):
                errors.append(f"sources[{index}].{field} is required")
        if not str(source.get("url", "")).startswith("https://"):
            errors.append(f"sources[{index}].url must use HTTPS")
        for field in ("last_verified", "review_due"):
            if not parse_iso(source.get(field)):
                errors.append(f"sources[{index}].{field} must be an ISO date")
        if parse_iso(source.get("last_verified")) and parse_iso(source.get("review_due")):
            if date.fromisoformat(source["review_due"]) <= date.fromisoformat(source["last_verified"]):
                errors.append(f"sources[{index}].review_due must be after last_verified")

    artifacts = artifacts_raw
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifacts needs at least one declared artifact")
    elif len(artifact_paths) != len(artifacts):
        errors.append("artifact paths must be non-empty and unique")
    artifact_ids: set[str] = set()
    for index, artifact in enumerate(artifacts or []):
        if not isinstance(artifact, dict):
            continue
        artifact_id = artifact.get("artifact_id")
        if not nonempty(artifact_id) or artifact_id in artifact_ids:
            errors.append(f"artifacts[{index}].artifact_id must be non-empty and unique")
        else:
            artifact_ids.add(artifact_id)
        if artifact.get("status") not in {"missing", "planned", "present", "independently_reproduced"}:
            errors.append(f"artifact {artifact_id} has an invalid status")
        digest = artifact.get("sha256")
        if digest is not None and not re.fullmatch(r"[a-f0-9]{64}", str(digest)):
            errors.append(f"artifact {artifact.get('artifact_id')} has an invalid sha256")

    disclaimers = profile.get("disclaimers")
    if not isinstance(disclaimers, list) or len(disclaimers) < 3:
        errors.append("disclaimers needs at least three explicit boundary statements")
    else:
        joined = " ".join(disclaimers).lower()
        for phrase in ("not an official", "not a certification", "accountable"):
            if phrase not in joined:
                errors.append(f"disclaimers must state {phrase!r}")
    return errors


def bullet(items: Any) -> str:
    values = items if isinstance(items, list) else [items]
    return "\n".join(f"- {item}" for item in values if str(item).strip()) or "- Not yet documented"


def front(profile: dict[str, Any], title: str) -> str:
    return (
        f"# {title}\n\n"
        f"Profile: `{profile['profile_id']}` · Version: `{profile['profile_version']}` · Status: `{profile['status']}`\n\n"
        "> Draft evidence aid. Not an official government standard, certification, authorization, acquisition decision, or legal conclusion.\n\n"
    )


def render_files(profile: dict[str, Any]) -> dict[str, str]:
    mission, impact = profile["mission"], profile["impact"]
    authority, data = profile["authority"], profile["data"]
    acquisition, testing = profile["acquisition"], profile["testing"]
    oversight, monitoring = profile["oversight"], profile["monitoring"]
    controls = profile["controls"]
    gaps = [item for item in controls if item["status"] == "gap"]
    planned = [item for item in controls if item["status"] == "planned"]
    evidenced = [item for item in controls if item["status"] == "evidenced"]
    benefit_targets = [
        f"{item['metric']}: {item['target']}" for item in mission["expected_benefits"]
    ]
    files: dict[str, str] = {}
    files["README.md"] = front(profile, f"Assurance pack — {mission['title']}") + (
        f"## Mission\n\n{mission['problem']}\n\n"
        f"## Evidence state\n\n- {len(evidenced)} evidenced\n- {len(planned)} planned\n- {len(gaps)} visible gaps\n\n"
        "No aggregate compliance score is produced. Inspect every required control, source, and artifact.\n\n"
        "## Contents\n\n" + bullet(PACK_NAMES[1:-1]) + "\n"
    )
    files["federal-profile.json"] = json.dumps(profile, indent=2) + "\n"
    files["01-use-case-inventory.md"] = front(profile, "01 — AI use-case inventory draft") + (
        f"## Mission title\n\n{mission['title']}\n\n## Agency context\n\n`{mission['agency_context']}`\n\n"
        f"## Problem\n\n{mission['problem']}\n\n## Affected groups\n\n{bullet(mission['affected_groups'])}\n\n"
        f"## Current baseline\n\n{mission['baseline']}\n\n## Expected benefits and measures\n\n" +
        "\n".join(f"- **{item['metric']}** — target: {item['target']}; measure: {item['measurement']}" for item in mission["expected_benefits"]) + "\n"
    )
    files["02-high-impact-determination.md"] = front(profile, "02 — High-impact AI determination draft") + (
        f"## Determination\n\n`{impact['high_impact_determination']}`\n\n## Rationale\n\n{impact['rationale']}\n\n"
        f"## Decision effects\n\n{bullet(impact['decision_effects'])}\n\n## Rights and safety impacts\n\n{bullet(impact['rights_safety_impacts'])}\n"
    )
    files["03-impact-assessment.md"] = front(profile, "03 — AI impact assessment draft") + (
        f"## Intended benefit\n\n{bullet(benefit_targets)}\n\n"
        f"## Affected groups\n\n{bullet(mission['affected_groups'])}\n\n## Rights and safety\n\n{bullet(impact['rights_safety_impacts'])}\n\n"
        f"## Accountable owner\n\n{authority['accountable_owner']}\n\n## Reassessment trigger\n\n{monitoring['reassessment_trigger']}\n"
    )
    files["04-tev-test-plan.md"] = front(profile, "04 — Test, evaluation, verification, and validation plan") + (
        f"## Intended environment\n\n{testing['intended_environment']}\n\n"
        f"## Minimum design\n\n- Scenarios: {testing['minimum_scenarios']}\n- Repeats: {testing['minimum_repeats']}\n- Independent reviewer: {testing['independent_reviewer']}\n\n"
        f"## Acceptance thresholds\n\n{bullet(testing['acceptance_thresholds'])}\n\n## Transfer traps\n\n{bullet(testing['transfer_traps'])}\n"
    )
    files["05-risk-register.md"] = front(profile, "05 — Open risk and evidence register") + (
        "| Control | Framework | State | Owner | Evidence |\n|---|---|---|---|---|\n" +
        "\n".join(f"| `{item['control_id']}` | {item['framework']} | **{item['status']}** | {item['owner']} | {', '.join(item['evidence_refs']) or 'none'} |" for item in controls) + "\n"
    )
    files["06-human-oversight-and-appeals.md"] = front(profile, "06 — Human oversight, failsafe, and remedy plan") + (
        f"## Human decision owner\n\n{authority['human_decision_owner']}\n\n## Review point\n\n{oversight['review_point']}\n\n"
        f"## Intervention\n\n{oversight['intervention']}\n\n## Failsafe\n\n{oversight['failsafe']}\n\n"
        f"## Appeal or remedy\n\n{oversight['appeal_or_remedy']}\n\n## Operator training\n\n{oversight['operator_training']}\n\n"
        f"## Prohibited agent actions\n\n{bullet(authority['prohibited_agent_actions'])}\n"
    )
    files["07-data-model-provenance.md"] = front(profile, "07 — Data and model provenance card") + (
        f"## Classification\n\n`{data['classification']}`\n\n- Contains PII: `{str(data['contains_pii']).lower()}`\n- Synthetic or public only: `{str(data['synthetic_or_public_only']).lower()}`\n\n"
        f"## Training use\n\n{data['training_use']}\n\n## Retention\n\n{data['retention']}\n\n## Provenance\n\n{bullet(data['provenance'])}\n"
    )
    files["08-acquisition-acceptance.md"] = front(profile, "08 — Acquisition performance and acceptance plan") + (
        f"- Vendor involved: `{str(acquisition['vendor_involved']).lower()}`\n\n## Performance metrics\n\n{bullet(acquisition['performance_metrics'])}\n\n"
        f"## Government data and intellectual-property rights\n\n{acquisition['data_rights']}\n\n## Portability\n\n{acquisition['portability']}\n\n"
        f"## Pricing and lifecycle costs\n\n{acquisition['pricing']}\n\n## Exit\n\n{acquisition['exit_plan']}\n"
    )
    files["09-monitoring-notice-and-cease-use.md"] = front(profile, "09 — Monitoring, public feedback, incident, and cease-use plan") + (
        f"## Metrics\n\n{bullet(monitoring['metrics'])}\n\n## Cadence\n\n{monitoring['cadence']}\n\n"
        f"## Plain-language purpose\n\n{mission['problem']}\n\n## Affected groups\n\n{bullet(mission['affected_groups'])}\n\n"
        f"## Feedback channel\n\n{monitoring['feedback_channel']}\n\n## Human review and remedy\n\n{oversight['appeal_or_remedy']}\n\n"
        f"## Incident route\n\n{monitoring['incident_route']}\n\n## Cease-use trigger\n\n{monitoring['cease_use_trigger']}\n\n"
        f"## Reassessment trigger\n\n{monitoring['reassessment_trigger']}\n\n"
        "Publication, notice content, exemptions, and timing remain agency decisions. Remove procurement-sensitive, controlled, classified, and personally identifiable information before publication.\n"
    )
    return files


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def build_manifest(profile: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    return {
        "manifest_version": "aau-federal-pack-manifest/0.1",
        "profile_id": profile["profile_id"],
        "created_at": profile["created_at"],
        "hash_algorithm": "sha256",
        "files": [
            {"path": name, "sha256": sha256_bytes(contents.encode("utf-8")), "bytes": len(contents.encode("utf-8"))}
            for name, contents in sorted(files.items())
        ],
        "claims": {
            "byte_integrity_only": True,
            "authorship_proved": False,
            "independent_reproduction_proved": False,
            "government_approval_proved": False,
            "compliance_proved": False,
        },
    }


def command_validate(args: argparse.Namespace) -> int:
    profile = load_json(args.profile)
    errors = validate_profile(profile)
    result = {"valid": not errors, "profile_id": profile.get("profile_id"), "errors": errors}
    if args.json:
        print(json.dumps(result, indent=2))
    elif errors:
        print(f"INVALID — {len(errors)} issue(s)")
        for error in errors:
            print(f"- {error}")
    else:
        states = {status: 0 for status in CONTROL_STATUSES}
        for control in profile["controls"]:
            states[control["status"]] += 1
        print(f"VALID — {profile['profile_id']} ({len(profile['controls'])} controls; {states['evidenced']} evidenced, {states['planned']} planned, {states['gap']} gaps)")
        print("Structural validity is not compliance, certification, approval, or independent reproduction.")
    return 0 if not errors else 1


def command_pack(args: argparse.Namespace) -> int:
    profile = load_json(args.profile)
    errors = validate_profile(profile)
    if errors:
        raise ValueError("profile is invalid; run validate for details")
    output: Path = args.out
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"refusing to overwrite non-empty output path: {output}")
    output.mkdir(parents=True, exist_ok=True)
    files = render_files(profile)
    manifest = build_manifest(profile, files)
    files["manifest.json"] = json.dumps(manifest, indent=2) + "\n"
    for name, contents in files.items():
        (output / name).write_text(contents, encoding="utf-8")
    print(f"wrote {len(files)} files to {output}")
    print("Manifest hashes prove byte integrity only—not authorship, compliance, or approval.")
    return 0


def command_verify_pack(args: argparse.Namespace) -> int:
    manifest_path = args.directory / "manifest.json"
    manifest = load_json(manifest_path)
    errors: list[str] = []
    items = manifest.get("files", [])
    if not isinstance(items, list):
        items = []
        errors.append("manifest.files must be an array")
    names = [item.get("path") for item in items if isinstance(item, dict)]
    expected = set(PACK_NAMES) - {"manifest.json"}
    if len(names) != len(set(names)):
        errors.append("manifest contains duplicate file paths")
    if set(names) != expected:
        errors.append(f"manifest file set must equal the 11-file contract: {sorted(expected)}")
    for item in items:
        if not isinstance(item, dict):
            errors.append("manifest file entries must be objects")
            continue
        name = item.get("path")
        if name not in expected:
            continue
        path = args.directory / name
        if not path.is_file():
            errors.append(f"missing {name}")
            continue
        contents = path.read_bytes()
        digest = sha256_bytes(contents)
        if digest != item.get("sha256"):
            errors.append(f"digest mismatch: {name}")
        if len(contents) != item.get("bytes"):
            errors.append(f"byte-count mismatch: {name}")
    extra = {path.name for path in args.directory.iterdir()} - set(PACK_NAMES)
    if extra:
        errors.append(f"unlisted files: {sorted(extra)}")
    if errors:
        print("PACK INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PACK INTEGRITY VERIFIED — {len(manifest.get('files', []))} hashed files")
    print("Integrity verification does not prove authorship, evidence quality, compliance, or approval.")
    return 0


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, child in value.items():
            output.update(flatten(child, f"{prefix}.{key}" if prefix else key))
        return output
    if isinstance(value, list):
        return {prefix: value}
    return {prefix: value}


def command_diff(args: argparse.Namespace) -> int:
    before, after = flatten(load_json(args.before)), flatten(load_json(args.after))
    keys = sorted(set(before) | set(after))
    changed = [(key, before.get(key), after.get(key)) for key in keys if before.get(key) != after.get(key)]
    if args.json:
        print(json.dumps([{"path": key, "before": old, "after": new} for key, old, new in changed], indent=2))
    elif not changed:
        print("NO PROFILE CHANGES")
    else:
        print(f"{len(changed)} PROFILE CHANGE(S)")
        for key, old, new in changed:
            print(f"- {key}: {old!r} -> {new!r}")
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="AAU Federal Mission Assurance Profile tools")
    sub = value.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate one profile")
    validate.add_argument("profile", type=Path)
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate)
    pack = sub.add_parser("pack", help="render a 12-file assurance pack")
    pack.add_argument("profile", type=Path)
    pack.add_argument("--out", type=Path, required=True)
    pack.set_defaults(func=command_pack)
    verify = sub.add_parser("verify-pack", help="recompute and compare pack digests")
    verify.add_argument("directory", type=Path)
    verify.set_defaults(func=command_verify_pack)
    diff = sub.add_parser("diff", help="show semantic field changes between profiles")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    diff.add_argument("--json", action="store_true")
    diff.set_defaults(func=command_diff)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"ERROR — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
