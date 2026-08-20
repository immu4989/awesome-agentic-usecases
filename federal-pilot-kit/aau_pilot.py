#!/usr/bin/env python3
"""Validate and inspect AAU Federal Pilot Kit evidence exchanges.

The dependency-free tool performs structural and deterministic evidence checks. It does
not evaluate proposal merit, rank vendors, make a source-selection decision, certify a
system, or replace an accountable government official.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


AGENCY_VERSION = "aau-federal-pilot-agency/0.2"
VENDOR_VERSION = "aau-federal-pilot-vendor/0.2"
TEST_VERSION = "aau-federal-pilot-tests/0.2"
ASSESSMENT_VERSION = "aau-federal-pilot-assessment/0.2"
PACK_VERSION = "aau-federal-pilot-pack/0.2"
LESSON_VERSION = "aau-federal-ai-lesson/0.4"
LESSON_SCAN_VERSION = "aau-public-redaction-scan/0.4"
LESSON_CLOSEOUT_VERSION = "aau-federal-ai-lesson-closeout/0.4"
SOURCE_LEDGER_VERSION = "aau-federal-ai-lesson-sources/0.4"

PACK_NAMES = (
    "README.md",
    "agency-intake.json",
    "vendor-response.json",
    "acceptance-tests.json",
    "01-claim-evidence-test-ledger.md",
    "02-acceptance-test-report.md",
    "03-commercial-data-and-exit-review.md",
    "04-post-award-monitoring-plan.md",
    "05-lessons-learned.md",
    "assessment.json",
    "manifest.json",
)

CLOSEOUT_NAMES = (
    "README.md",
    "lesson.json",
    "assessment-summary.json",
    "evidence-index.json",
    "privacy-scan.json",
    "source-snapshot.json",
    "manifest.json",
)

LESSON_RESULTS = {"succeeded", "changed", "stopped", "mixed"}
LESSON_STATUSES = {"public_synthetic", "public_record", "revalidation_due", "retired"}
LIFECYCLE_STAGES = {"pre_award", "award", "post_award", "closeout", "cross_lifecycle"}
CHALLENGE_CATEGORIES = {
    "technical_expertise",
    "requirements_and_contract_terms",
    "government_data_and_ip",
    "early_testing_and_continuous_evaluation",
    "pricing_and_total_cost",
    "portability_and_exit",
    "privacy_and_data_handling",
    "human_authority",
    "accessibility_and_public_service",
    "program_management",
}
REUSE_STATES = {"promising", "evidence_backed", "needs_revalidation", "retired"}

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{2,79}$")
ITEM_ID = re.compile(r"^[A-Z][A-Z0-9-]{2,39}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
MAX_JSON_BYTES = 2_000_000
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 50_000
MAX_STRING_BYTES = 256_000
MAX_PACK_FILE_BYTES = 5_000_000

SENSITIVE_PATTERNS = (
    ("EMAIL", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}(?!\d)")),
    ("PRIVATE_KEY", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("GITHUB_TOKEN", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("AWS_ACCESS_KEY", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("BEARER_TOKEN", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.I)),
)
SENSITIVE_FIELD_NAMES = {
    "account_number",
    "address",
    "date_of_birth",
    "dob",
    "full_name",
    "home_address",
    "person_name",
    "social_security_number",
}


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not permitted: {value}")


def enforce_json_limits(value: Any) -> None:
    stack: list[tuple[Any, int]] = [(value, 1)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise ValueError(f"JSON document exceeds the {MAX_JSON_NODES}-node limit")
        if depth > MAX_JSON_DEPTH:
            raise ValueError(f"JSON document exceeds the {MAX_JSON_DEPTH}-level nesting limit")
        if isinstance(item, str) and len(item.encode("utf-8")) > MAX_STRING_BYTES:
            raise ValueError(f"JSON string exceeds the {MAX_STRING_BYTES}-byte limit")
        if isinstance(item, dict):
            stack.extend((key, depth + 1) for key in item)
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)


def load_json(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"JSON input must be a regular file: {path}")
        if path.stat().st_size > MAX_JSON_BYTES:
            raise ValueError(f"JSON input exceeds the {MAX_JSON_BYTES}-byte limit: {path}")
        value = json.loads(path.read_bytes(), parse_constant=reject_json_constant)
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {path}") from exc
    except UnicodeDecodeError as exc:
        raise ValueError(f"JSON input is not valid UTF-8: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except RecursionError as exc:
        raise ValueError("JSON document nesting exceeds the parser safety limit") from exc
    if not isinstance(value, dict):
        raise ValueError("document root must be a JSON object")
    enforce_json_limits(value)
    return value


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def iso_datetime(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def safe_relative_path(value: Any) -> bool:
    if not nonempty(value) or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts


def walk_strings(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}" if prefix else str(key)
            output.extend(walk_strings(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            output.extend(walk_strings(child, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        output.append((prefix, value))
    return output


def scan_sensitive(value: dict[str, Any]) -> dict[str, Any]:
    """Run a narrow deterministic pre-publication scan without echoing matched values."""
    findings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for path, content in walk_strings(value):
        leaf = re.sub(r"\[\d+\]$", "", path.rsplit(".", 1)[-1]).lower()
        if leaf in SENSITIVE_FIELD_NAMES and content.strip():
            key = ("SENSITIVE_FIELD", path)
            if key not in seen:
                seen.add(key)
                findings.append(
                    {
                        "code": "SENSITIVE_FIELD",
                        "path": path,
                        "fingerprint": sha256_bytes(content.encode("utf-8"))[:16],
                    }
                )
        for code, pattern in SENSITIVE_PATTERNS:
            match = pattern.search(content)
            if not match:
                continue
            key = (code, path)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                {
                    "code": code,
                    "path": path,
                    "fingerprint": sha256_bytes(match.group(0).encode("utf-8"))[:16],
                }
            )
    sharing = value.get("sharing") if isinstance(value.get("sharing"), dict) else {}
    for field in (
        "contains_personally_identifiable_information",
        "contains_procurement_sensitive_information",
        "contains_controlled_unclassified_information",
        "contains_classified_information",
        "contains_secrets_or_credentials",
    ):
        if sharing.get(field) is not False:
            findings.append(
                {
                    "code": "PUBLICATION_ATTESTATION_MISSING",
                    "path": f"sharing.{field}",
                    "fingerprint": sha256_bytes(f"{field}:{sharing.get(field)!r}".encode())[:16],
                }
            )
    return {
        "scan_version": LESSON_SCAN_VERSION,
        "finding_count": len(findings),
        "safe_to_package": not findings,
        "findings": findings,
        "boundary": (
            "A zero-finding scan is not a privacy, records, classification, export-control, "
            "procurement-sensitivity, or disclosure determination. Authorized human review remains required."
        ),
    }


def object_at(value: dict[str, Any], key: str, errors: list[str]) -> dict[str, Any]:
    child = value.get(key)
    if not isinstance(child, dict):
        errors.append(f"{key} must be an object")
        return {}
    return child


def object_list(value: Any, path: str, errors: list[str], *, minimum: int = 1) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        errors.append(f"{path} must be an array")
        return []
    items = [item for item in value if isinstance(item, dict)]
    if len(items) != len(value):
        errors.append(f"{path} must contain objects")
    if len(items) < minimum:
        errors.append(f"{path} needs at least {minimum} item(s)")
    return items


def string_list(value: Any, path: str, errors: list[str], *, minimum: int = 1) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{path} must be an array")
        return []
    items = [item.strip() for item in value if nonempty(item)]
    if len(items) != len(value):
        errors.append(f"{path} must contain non-empty strings")
    if len(set(items)) != len(items):
        errors.append(f"{path} must not contain duplicates")
    if len(items) < minimum:
        errors.append(f"{path} needs at least {minimum} value(s)")
    return items


def require_strings(value: dict[str, Any], fields: tuple[str, ...], prefix: str, errors: list[str]) -> None:
    for field in fields:
        if not nonempty(value.get(field)):
            errors.append(f"{prefix}{field} is required")


def validate_disclaimers(value: Any, path: str, errors: list[str]) -> None:
    items = string_list(value, path, errors, minimum=3)
    joined = " ".join(items).lower()
    for phrase in ("not a source-selection", "not a certification", "accountable"):
        if phrase not in joined:
            errors.append(f"{path} must state {phrase!r}")


def validate_source_ledger(ledger: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if ledger.get("ledger_version") != SOURCE_LEDGER_VERSION:
        errors.append(f"ledger_version must equal {SOURCE_LEDGER_VERSION!r}")
    sources = object_list(ledger.get("sources"), "sources", errors, minimum=3)
    source_ids: set[str] = set()
    for index, item in enumerate(sources):
        path = f"sources[{index}]"
        source_id = item.get("source_id")
        if not SLUG.fullmatch(str(source_id or "")):
            errors.append(f"{path}.source_id must be a lowercase slug")
        elif source_id in source_ids:
            errors.append(f"duplicate source_id: {source_id}")
        else:
            source_ids.add(source_id)
        require_strings(
            item,
            ("title", "authority", "url", "selector"),
            f"{path}.",
            errors,
        )
        if not str(item.get("url", "")).startswith("https://"):
            errors.append(f"{path}.url must use HTTPS")
        for field in ("published_at", "last_verified", "review_due"):
            if not iso_date(item.get(field)):
                errors.append(f"{path}.{field} must be an ISO 8601 date")
        if iso_date(item.get("last_verified")) and iso_date(item.get("review_due")):
            if item["review_due"] <= item["last_verified"]:
                errors.append(f"{path}.review_due must follow last_verified")
    require_strings(ledger, ("boundary",), "", errors)
    return errors


def validate_lesson(lesson: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if lesson.get("profile_version") != LESSON_VERSION:
        errors.append(f"profile_version must equal {LESSON_VERSION!r}")
    for field in ("lesson_id", "pilot_id"):
        if not SLUG.fullmatch(str(lesson.get(field, ""))):
            errors.append(f"{field} must be a 3-80 character lowercase slug")
    if not iso_datetime(lesson.get("published_at")):
        errors.append("published_at must be an ISO 8601 date-time")
    if not iso_date(lesson.get("review_due")):
        errors.append("review_due must be an ISO 8601 date")
    if lesson.get("status") not in LESSON_STATUSES:
        errors.append(f"status must be one of {sorted(LESSON_STATUSES)}")

    origin = object_at(lesson, "origin", errors)
    if origin.get("kind") not in {"reference_exchange", "standalone_synthetic_exercise"}:
        errors.append("origin.kind must be reference_exchange or standalone_synthetic_exercise")
    require_strings(origin, ("summary",), "origin.", errors)
    exchange_path = origin.get("exchange_path")
    if exchange_path is not None and not safe_relative_path(exchange_path):
        errors.append("origin.exchange_path must be a safe relative path or null")
    response_id = origin.get("response_id")
    if response_id is not None and not SLUG.fullmatch(str(response_id)):
        errors.append("origin.response_id must be a lowercase slug or null")

    sharing = object_at(lesson, "sharing", errors)
    if sharing.get("classification") not in {"public_synthetic", "public_record"}:
        errors.append("sharing.classification must be public_synthetic or public_record")
    require_strings(
        sharing,
        ("human_redaction_review_role", "publication_authority_role", "public_release_basis"),
        "sharing.",
        errors,
    )
    for field in (
        "contains_personally_identifiable_information",
        "contains_procurement_sensitive_information",
        "contains_controlled_unclassified_information",
        "contains_classified_information",
        "contains_secrets_or_credentials",
    ):
        if sharing.get(field) is not False:
            errors.append(f"sharing.{field} must be false for a public lesson")
    if sharing.get("human_review_complete") is not True:
        errors.append("sharing.human_review_complete must be true")

    mission = object_at(lesson, "mission", errors)
    require_strings(
        mission,
        ("title", "archetype", "beneficiary", "baseline", "intended_outcome"),
        "mission.",
        errors,
    )
    stages = string_list(lesson.get("lifecycle_stages"), "lifecycle_stages", errors)
    unknown_stages = set(stages) - LIFECYCLE_STAGES
    if unknown_stages:
        errors.append(f"lifecycle_stages contain invalid values: {sorted(unknown_stages)}")

    challenge = object_at(lesson, "challenge", errors)
    categories = string_list(challenge.get("categories"), "challenge.categories", errors)
    unknown_categories = set(categories) - CHALLENGE_CATEGORIES
    if unknown_categories:
        errors.append(f"challenge.categories contain invalid values: {sorted(unknown_categories)}")
    require_strings(challenge, ("failure_shape", "decision_point"), "challenge.", errors)

    trace = object_at(lesson, "trace", errors)
    string_list(trace.get("requirement_ids"), "trace.requirement_ids", errors, minimum=0)
    string_list(trace.get("case_ids"), "trace.case_ids", errors, minimum=0)
    string_list(trace.get("evidence_ids"), "trace.evidence_ids", errors)

    evidence = object_list(lesson.get("evidence"), "evidence", errors)
    evidence_ids: set[str] = set()
    for index, item in enumerate(evidence):
        path = f"evidence[{index}]"
        evidence_id = item.get("evidence_id")
        if not ITEM_ID.fullmatch(str(evidence_id or "")):
            errors.append(f"{path}.evidence_id must be an uppercase identifier")
        elif evidence_id in evidence_ids:
            errors.append(f"duplicate evidence_id: {evidence_id}")
        else:
            evidence_ids.add(evidence_id)
        if item.get("kind") not in {
            "test_report", "architecture", "policy", "pricing", "data_terms",
            "operations", "accessibility", "decision_record", "synthetic_trace", "other",
        }:
            errors.append(f"{path}.kind has an invalid value")
        require_strings(
            item,
            ("title", "reference", "scope", "limitations", "verification"),
            f"{path}.",
            errors,
        )
        if not safe_relative_path(item.get("reference")):
            errors.append(f"{path}.reference must be a safe relative path")
        digest = item.get("sha256")
        if digest is not None and not SHA256.fullmatch(str(digest)):
            errors.append(f"{path}.sha256 must be a lowercase SHA-256 digest or null")
        if item.get("public_or_synthetic") is not True:
            errors.append(f"{path}.public_or_synthetic must be true")
    trace_evidence = trace.get("evidence_ids") if isinstance(trace.get("evidence_ids"), list) else []
    unknown_evidence = set(trace_evidence) - evidence_ids
    if unknown_evidence:
        errors.append(f"trace references undeclared evidence: {sorted(unknown_evidence)}")

    outcome = object_at(lesson, "outcome", errors)
    if outcome.get("result") not in LESSON_RESULTS:
        errors.append(f"outcome.result must be one of {sorted(LESSON_RESULTS)}")
    require_strings(
        outcome,
        ("summary", "observed_change", "human_decision"),
        "outcome.",
        errors,
    )
    metrics = object_list(outcome.get("metrics"), "outcome.metrics", errors)
    metric_ids: set[str] = set()
    for index, item in enumerate(metrics):
        metric_id = item.get("metric_id")
        if not ITEM_ID.fullmatch(str(metric_id or "")) or metric_id in metric_ids:
            errors.append(f"outcome.metrics[{index}].metric_id must be a unique uppercase identifier")
        else:
            metric_ids.add(metric_id)
        require_strings(
            item,
            ("measure", "before", "after", "interpretation"),
            f"outcome.metrics[{index}].",
            errors,
        )

    practice = object_at(lesson, "reusable_practice", errors)
    require_strings(practice, ("title", "action", "rationale"), "reusable_practice.", errors)
    if practice.get("reuse_state") not in REUSE_STATES:
        errors.append(f"reusable_practice.reuse_state must be one of {sorted(REUSE_STATES)}")
    string_list(practice.get("artifact_refs"), "reusable_practice.artifact_refs", errors)
    string_list(
        practice.get("contract_considerations"),
        "reusable_practice.contract_considerations",
        errors,
    )
    if practice.get("not_universal") is not True:
        errors.append("reusable_practice.not_universal must be true")

    applicability = object_at(lesson, "applicability", errors)
    for field in ("contexts", "does_not_transfer_to", "prerequisites", "limitations"):
        string_list(applicability.get(field), f"applicability.{field}", errors)
    if applicability.get("transfer_test_required") is not True:
        errors.append("applicability.transfer_test_required must be true")

    commercial = object_at(lesson, "commercial", errors)
    require_strings(
        commercial,
        ("pricing_insight", "government_data_and_ip", "portability", "exit_insight"),
        "commercial.",
        errors,
    )
    if commercial.get("vendor_identified") is not False:
        errors.append("commercial.vendor_identified must be false")

    privacy = object_at(lesson, "privacy", errors)
    require_strings(
        privacy,
        ("data_used", "data_minimization", "retention", "privacy_performance_tradeoff"),
        "privacy.",
        errors,
    )
    if privacy.get("data_classification") not in {"synthetic", "public", "mixed_public_synthetic"}:
        errors.append("privacy.data_classification has an invalid value")

    authority = object_at(lesson, "authority", errors)
    require_strings(
        authority,
        ("accountable_official_role", "stop_or_change_decision"),
        "authority.",
        errors,
    )
    string_list(authority.get("protected_decisions"), "authority.protected_decisions", errors)
    string_list(
        authority.get("prohibited_system_actions"),
        "authority.prohibited_system_actions",
        errors,
    )
    if authority.get("system_made_protected_decision") is not False:
        errors.append("authority.system_made_protected_decision must be false")

    dependencies = object_list(lesson.get("policy_dependencies"), "policy_dependencies", errors)
    source_ids: set[str] = set()
    for index, item in enumerate(dependencies):
        path = f"policy_dependencies[{index}]"
        source_id = item.get("source_id")
        if not SLUG.fullmatch(str(source_id or "")):
            errors.append(f"{path}.source_id must be a lowercase slug")
        elif source_id in source_ids:
            errors.append(f"duplicate policy dependency: {source_id}")
        else:
            source_ids.add(source_id)
        require_strings(item, ("dependency",), f"{path}.", errors)
        string_list(item.get("revalidate_on"), f"{path}.revalidate_on", errors)

    attestations = object_at(lesson, "attestations", errors)
    for field in (
        "public_or_synthetic_only",
        "human_redaction_review_complete",
        "limitations_disclosed",
        "no_vendor_ranking",
        "no_award_recommendation",
        "accountable_authority_preserved",
    ):
        if attestations.get(field) is not True:
            errors.append(f"attestations.{field} must be true")
    validate_disclaimers(lesson.get("disclaimers"), "disclaimers", errors)
    return errors


def cross_validate_lesson(
    lesson: dict[str, Any],
    agency: dict[str, Any],
    vendor: dict[str, Any],
    tests: dict[str, Any],
    ledger: dict[str, Any],
) -> list[str]:
    errors = validate_lesson(lesson) + cross_validate(agency, vendor, tests) + validate_source_ledger(ledger)
    if lesson.get("pilot_id") != agency.get("pilot_id"):
        errors.append("lesson pilot_id must match the source exchange")
    origin = lesson.get("origin") if isinstance(lesson.get("origin"), dict) else {}
    if origin.get("kind") != "reference_exchange":
        errors.append("closeout requires origin.kind to be reference_exchange")
    if origin.get("response_id") != vendor.get("response_id"):
        errors.append("lesson origin.response_id must match the source response")
    trace = lesson.get("trace") if isinstance(lesson.get("trace"), dict) else {}
    known_requirements = {
        item.get("requirement_id") for item in agency.get("requirements", []) if isinstance(item, dict)
    }
    known_cases = {item.get("case_id") for item in tests.get("cases", []) if isinstance(item, dict)}
    known_evidence = {
        item.get("evidence_id") for item in vendor.get("evidence", []) if isinstance(item, dict)
    }
    for key, known in (
        ("requirement_ids", known_requirements),
        ("case_ids", known_cases),
        ("evidence_ids", known_evidence),
    ):
        submitted = trace.get(key) if isinstance(trace.get(key), list) else []
        unknown = set(submitted) - known
        if unknown:
            errors.append(f"lesson trace.{key} references unknown values: {sorted(unknown)}")
    ledger_ids = {
        item.get("source_id") for item in ledger.get("sources", []) if isinstance(item, dict)
    }
    lesson_source_ids = {
        item.get("source_id")
        for item in lesson.get("policy_dependencies", [])
        if isinstance(item, dict)
    }
    unknown_sources = lesson_source_ids - ledger_ids
    if unknown_sources:
        errors.append(f"lesson references unknown policy sources: {sorted(unknown_sources)}")
    return errors


def validate_agency(agency: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if agency.get("profile_version") != AGENCY_VERSION:
        errors.append(f"profile_version must equal {AGENCY_VERSION!r}")
    if not SLUG.fullmatch(str(agency.get("pilot_id", ""))):
        errors.append("pilot_id must be a 3-80 character lowercase slug")
    if not iso_datetime(agency.get("created_at")):
        errors.append("created_at must be an ISO 8601 date-time")
    if agency.get("status") not in {"draft", "request_for_comment", "pilot_authorized", "closed"}:
        errors.append("status must be draft, request_for_comment, pilot_authorized, or closed")

    mission = object_at(agency, "mission", errors)
    require_strings(
        mission,
        ("title", "problem", "current_baseline", "intended_environment"),
        "mission.",
        errors,
    )
    string_list(mission.get("affected_groups"), "mission.affected_groups", errors)
    string_list(mission.get("out_of_scope"), "mission.out_of_scope", errors)

    authority = object_at(agency, "authority", errors)
    require_strings(
        authority,
        ("accountable_official_role", "escalation_route"),
        "authority.",
        errors,
    )
    protected = string_list(
        authority.get("protected_decisions"), "authority.protected_decisions", errors
    )
    string_list(
        authority.get("prohibited_system_actions"),
        "authority.prohibited_system_actions",
        errors,
    )
    if not any("award" in item.lower() or "source selection" in item.lower() for item in protected):
        errors.append("authority.protected_decisions must preserve award or source-selection authority")

    data = object_at(agency, "data", errors)
    if data.get("classification") not in {"public", "synthetic", "mixed_public_synthetic"}:
        errors.append("data.classification must be public, synthetic, or mixed_public_synthetic")
    string_list(data.get("allowed_data"), "data.allowed_data", errors)
    string_list(data.get("prohibited_data"), "data.prohibited_data", errors)
    require_strings(data, ("training_use", "retention"), "data.", errors)

    requirements = object_list(agency.get("requirements"), "requirements", errors, minimum=3)
    requirement_ids: set[str] = set()
    for index, item in enumerate(requirements):
        path = f"requirements[{index}]"
        requirement_id = item.get("requirement_id")
        if not ITEM_ID.fullmatch(str(requirement_id or "")):
            errors.append(f"{path}.requirement_id must be an uppercase identifier")
        elif requirement_id in requirement_ids:
            errors.append(f"duplicate requirement_id: {requirement_id}")
        else:
            requirement_ids.add(requirement_id)
        require_strings(
            item,
            ("outcome", "measure", "threshold", "evidence_required", "verification_method"),
            f"{path}.",
            errors,
        )
        if item.get("criticality") not in {"critical", "important", "advisory"}:
            errors.append(f"{path}.criticality has an invalid value")
        if item.get("lifecycle_phase") not in {"pre_award", "post_award", "both"}:
            errors.append(f"{path}.lifecycle_phase has an invalid value")

    commercial = object_at(agency, "commercial", errors)
    require_strings(
        commercial,
        ("pricing_unit", "data_rights", "portability", "knowledge_transfer", "exit_plan"),
        "commercial.",
        errors,
    )
    scenarios = object_list(
        commercial.get("cost_scenarios"), "commercial.cost_scenarios", errors, minimum=2
    )
    names: set[str] = set()
    for index, item in enumerate(scenarios):
        require_strings(item, ("name", "volume"), f"commercial.cost_scenarios[{index}].", errors)
        name = item.get("name")
        if name in names:
            errors.append(f"duplicate commercial cost scenario: {name}")
        elif nonempty(name):
            names.add(name)

    monitoring = object_at(agency, "monitoring", errors)
    string_list(monitoring.get("metrics"), "monitoring.metrics", errors)
    require_strings(
        monitoring,
        ("cadence", "incident_route", "reassessment_trigger", "cease_use_trigger"),
        "monitoring.",
        errors,
    )
    validate_disclaimers(agency.get("disclaimers"), "disclaimers", errors)
    return errors


def validate_vendor(vendor: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if vendor.get("profile_version") != VENDOR_VERSION:
        errors.append(f"profile_version must equal {VENDOR_VERSION!r}")
    for field in ("response_id", "pilot_id"):
        if not SLUG.fullmatch(str(vendor.get(field, ""))):
            errors.append(f"{field} must be a 3-80 character lowercase slug")
    if not iso_datetime(vendor.get("submitted_at")):
        errors.append("submitted_at must be an ISO 8601 date-time")
    if not nonempty(vendor.get("respondent_label")):
        errors.append("respondent_label is required")

    evidence = object_list(vendor.get("evidence"), "evidence", errors)
    evidence_ids: set[str] = set()
    for index, item in enumerate(evidence):
        path = f"evidence[{index}]"
        evidence_id = item.get("evidence_id")
        if not ITEM_ID.fullmatch(str(evidence_id or "")):
            errors.append(f"{path}.evidence_id must be an uppercase identifier")
        elif evidence_id in evidence_ids:
            errors.append(f"duplicate evidence_id: {evidence_id}")
        else:
            evidence_ids.add(evidence_id)
        if item.get("kind") not in {
            "test_report", "architecture", "policy", "pricing", "data_terms",
            "operations", "accessibility", "other",
        }:
            errors.append(f"{path}.kind has an invalid value")
        require_strings(item, ("title", "reference", "scope", "limitations"), f"{path}.", errors)
        reference = str(item.get("reference", ""))
        reference_path = PurePosixPath(reference)
        if reference_path.is_absolute() or ".." in reference_path.parts or "\\" in reference:
            errors.append(f"{path}.reference must not escape the exchange directory")
        digest = item.get("sha256")
        if digest is not None and not SHA256.fullmatch(str(digest)):
            errors.append(f"{path}.sha256 must be a lowercase SHA-256 digest or null")

    claims = object_list(vendor.get("claims"), "claims", errors, minimum=3)
    claim_ids: set[str] = set()
    for index, item in enumerate(claims):
        path = f"claims[{index}]"
        requirement_id = item.get("requirement_id")
        if not ITEM_ID.fullmatch(str(requirement_id or "")):
            errors.append(f"{path}.requirement_id must be an uppercase identifier")
        elif requirement_id in claim_ids:
            errors.append(f"duplicate claim for requirement_id: {requirement_id}")
        else:
            claim_ids.add(requirement_id)
        if item.get("status") not in {"supported", "partial", "not_supported"}:
            errors.append(f"{path}.status has an invalid value")
        require_strings(item, ("claim", "limitations"), f"{path}.", errors)
        refs = string_list(item.get("evidence_refs"), f"{path}.evidence_refs", errors, minimum=0)
        unknown = set(refs) - evidence_ids
        if unknown:
            errors.append(f"{path} references undeclared evidence: {sorted(unknown)}")
        if item.get("status") == "supported" and not refs:
            errors.append(f"{path} is supported but has no evidence_refs")

    test_results = object_list(vendor.get("test_results"), "test_results", errors)
    case_ids: set[str] = set()
    for index, item in enumerate(test_results):
        path = f"test_results[{index}]"
        case_id = item.get("case_id")
        if not ITEM_ID.fullmatch(str(case_id or "")):
            errors.append(f"{path}.case_id must be an uppercase identifier")
        elif case_id in case_ids:
            errors.append(f"duplicate test result for case_id: {case_id}")
        else:
            case_ids.add(case_id)
        require_strings(item, ("observed_outcome", "authority_owner"), f"{path}.", errors)
        string_list(item.get("reason_codes"), f"{path}.reason_codes", errors)
        if not isinstance(item.get("authority_respected"), bool):
            errors.append(f"{path}.authority_respected must be a boolean")
        refs = string_list(item.get("evidence_refs"), f"{path}.evidence_refs", errors)
        unknown = set(refs) - evidence_ids
        if unknown:
            errors.append(f"{path} references undeclared evidence: {sorted(unknown)}")

    pricing = object_at(vendor, "pricing", errors)
    if pricing.get("currency") != "USD":
        errors.append("pricing.currency must equal 'USD'")
    object_list(pricing.get("line_items"), "pricing.line_items", errors)
    string_list(pricing.get("assumptions"), "pricing.assumptions", errors)
    require_strings(pricing, ("maximum_scenario_cost",), "pricing.", errors)

    terms = object_at(vendor, "terms", errors)
    require_strings(
        terms,
        ("government_data_use", "portability", "knowledge_transfer", "exit_support"),
        "terms.",
        errors,
    )
    attestations = object_at(vendor, "attestations", errors)
    for field in (
        "synthetic_or_public_submission",
        "limitations_disclosed",
        "no_award_recommendation",
        "human_authority_acknowledged",
    ):
        if attestations.get(field) is not True:
            errors.append(f"attestations.{field} must be true")
    validate_disclaimers(vendor.get("disclaimers"), "disclaimers", errors)
    return errors


def validate_tests(tests: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if tests.get("profile_version") != TEST_VERSION:
        errors.append(f"profile_version must equal {TEST_VERSION!r}")
    if not SLUG.fullmatch(str(tests.get("pilot_id", ""))):
        errors.append("pilot_id must be a 3-80 character lowercase slug")
    require_strings(tests, ("title", "test_environment", "independent_reviewer_role"), "", errors)
    if not isinstance(tests.get("seed"), int) or tests.get("seed", -1) < 0:
        errors.append("seed must be a non-negative integer")
    if tests.get("data_classification") not in {"public", "synthetic", "mixed_public_synthetic"}:
        errors.append("data_classification must be public, synthetic, or mixed_public_synthetic")
    dimensions = string_list(tests.get("dimensions"), "dimensions", errors, minimum=2)
    cases = object_list(tests.get("cases"), "cases", errors, minimum=4)
    case_ids: set[str] = set()
    for index, item in enumerate(cases):
        path = f"cases[{index}]"
        case_id = item.get("case_id")
        if not ITEM_ID.fullmatch(str(case_id or "")):
            errors.append(f"{path}.case_id must be an uppercase identifier")
        elif case_id in case_ids:
            errors.append(f"duplicate case_id: {case_id}")
        else:
            case_ids.add(case_id)
        if item.get("dimension") not in dimensions:
            errors.append(f"{path}.dimension must reference a declared dimension")
        if not isinstance(item.get("input"), dict) or not item.get("input"):
            errors.append(f"{path}.input must be a non-empty object")
        oracle = item.get("oracle")
        if not isinstance(oracle, dict):
            errors.append(f"{path}.oracle must be an object")
            oracle = {}
        require_strings(oracle, ("outcome", "required_authority"), f"{path}.oracle.", errors)
        string_list(oracle.get("reason_codes"), f"{path}.oracle.reason_codes", errors)
        string_list(item.get("linked_requirements"), f"{path}.linked_requirements", errors)
        require_strings(item, ("failure_shape",), f"{path}.", errors)
        if not isinstance(item.get("critical"), bool):
            errors.append(f"{path}.critical must be a boolean")
    scoring = object_at(tests, "scoring_contract", errors)
    exact_fields = string_list(scoring.get("exact_fields"), "scoring_contract.exact_fields", errors)
    for required in ("observed_outcome", "reason_codes", "authority_owner"):
        if required not in exact_fields:
            errors.append(f"scoring_contract.exact_fields must include {required!r}")
    if scoring.get("conjunctive") is not True:
        errors.append("scoring_contract.conjunctive must be true")
    if scoring.get("ranking_permitted") is not False:
        errors.append("scoring_contract.ranking_permitted must be false")
    sources = object_list(tests.get("sources"), "sources", errors)
    source_ids: set[str] = set()
    for index, item in enumerate(sources):
        source_id = item.get("source_id")
        if not SLUG.fullmatch(str(source_id or "")) or source_id in source_ids:
            errors.append(f"sources[{index}].source_id must be a unique lowercase slug")
        else:
            source_ids.add(source_id)
        require_strings(item, ("title", "authority", "url", "selector"), f"sources[{index}].", errors)
        if not str(item.get("url", "")).startswith("https://"):
            errors.append(f"sources[{index}].url must use HTTPS")
    validate_disclaimers(tests.get("disclaimers"), "disclaimers", errors)
    return errors


VALIDATORS = {
    "agency": validate_agency,
    "lesson": validate_lesson,
    "vendor": validate_vendor,
    "tests": validate_tests,
}


def cross_validate(
    agency: dict[str, Any], vendor: dict[str, Any], tests: dict[str, Any]
) -> list[str]:
    errors = validate_agency(agency) + validate_vendor(vendor) + validate_tests(tests)
    pilot_ids = {agency.get("pilot_id"), vendor.get("pilot_id"), tests.get("pilot_id")}
    if len(pilot_ids) != 1:
        errors.append("agency, vendor, and tests pilot_id values must match")
    agency_requirements = agency.get("requirements")
    vendor_claims = vendor.get("claims")
    test_cases = tests.get("cases")
    vendor_results = vendor.get("test_results")
    requirement_ids = {
        item.get("requirement_id")
        for item in agency_requirements if isinstance(item, dict)
    } if isinstance(agency_requirements, list) else set()
    claim_ids = {
        item.get("requirement_id")
        for item in vendor_claims if isinstance(item, dict)
    } if isinstance(vendor_claims, list) else set()
    missing_claims = requirement_ids - claim_ids
    unknown_claims = claim_ids - requirement_ids
    if missing_claims:
        errors.append(f"vendor response omits requirements: {sorted(missing_claims)}")
    if unknown_claims:
        errors.append(f"vendor response claims unknown requirements: {sorted(unknown_claims)}")
    test_requirement_ids = {
        requirement_id
        for case in test_cases if isinstance(case, dict)
        for requirement_id in (
            case.get("linked_requirements")
            if isinstance(case.get("linked_requirements"), list)
            else []
        )
    } if isinstance(test_cases, list) else set()
    unknown_test_requirements = test_requirement_ids - requirement_ids
    if unknown_test_requirements:
        errors.append(f"tests reference unknown requirements: {sorted(unknown_test_requirements)}")
    case_ids = {
        item.get("case_id") for item in test_cases if isinstance(item, dict)
    } if isinstance(test_cases, list) else set()
    result_ids = {
        item.get("case_id") for item in vendor_results if isinstance(item, dict)
    } if isinstance(vendor_results, list) else set()
    missing_results = case_ids - result_ids
    unknown_results = result_ids - case_ids
    if missing_results:
        errors.append(f"vendor response omits test cases: {sorted(missing_results)}")
    if unknown_results:
        errors.append(f"vendor response reports unknown test cases: {sorted(unknown_results)}")
    return errors


def assess_exchange(
    agency: dict[str, Any], vendor: dict[str, Any], tests: dict[str, Any]
) -> dict[str, Any]:
    errors = cross_validate(agency, vendor, tests)
    if errors:
        raise ValueError("exchange is invalid: " + "; ".join(errors))
    claims = {item["requirement_id"]: item for item in vendor["claims"]}
    evidence_ids = {item["evidence_id"] for item in vendor["evidence"]}
    results = {item["case_id"]: item for item in vendor["test_results"]}
    case_rows: list[dict[str, Any]] = []
    passing_by_requirement: dict[str, list[bool]] = {
        item["requirement_id"]: [] for item in agency["requirements"]
    }
    dimension_rows: dict[str, list[bool]] = {item: [] for item in tests["dimensions"]}
    critical_authority_failures: list[str] = []
    for case in tests["cases"]:
        result = results[case["case_id"]]
        oracle = case["oracle"]
        checks = {
            "outcome": result["observed_outcome"] == oracle["outcome"],
            "reason_codes": set(result["reason_codes"]) == set(oracle["reason_codes"]),
            "authority_owner": result["authority_owner"] == oracle["required_authority"],
            "authority_respected": result["authority_respected"] is True,
            "evidence_declared": bool(set(result["evidence_refs"]) <= evidence_ids),
        }
        exact = all(checks.values())
        if case["critical"] and not checks["authority_respected"]:
            critical_authority_failures.append(case["case_id"])
        for requirement_id in case["linked_requirements"]:
            passing_by_requirement[requirement_id].append(exact)
        dimension_rows[case["dimension"]].append(exact)
        case_rows.append(
            {
                "case_id": case["case_id"],
                "dimension": case["dimension"],
                "critical": case["critical"],
                "exact": exact,
                "checks": checks,
                "expected": oracle,
                "observed": {
                    "outcome": result["observed_outcome"],
                    "reason_codes": result["reason_codes"],
                    "authority_owner": result["authority_owner"],
                },
                "failure_shape": case["failure_shape"],
            }
        )

    requirement_rows: list[dict[str, Any]] = []
    critical_gaps: list[str] = []
    for requirement in agency["requirements"]:
        requirement_id = requirement["requirement_id"]
        claim = claims[requirement_id]
        declared_evidence = [item for item in claim["evidence_refs"] if item in evidence_ids]
        linked_results = passing_by_requirement[requirement_id]
        if claim["status"] == "not_supported":
            state = "unsupported"
        elif claim["status"] == "partial":
            state = "partial"
        elif not declared_evidence:
            state = "claimed_without_evidence"
        elif not linked_results:
            state = "evidenced_not_tested"
        elif not all(linked_results):
            state = "tested_with_failures"
        else:
            state = "tested"
        if requirement["criticality"] == "critical" and state != "tested":
            critical_gaps.append(requirement_id)
        requirement_rows.append(
            {
                "requirement_id": requirement_id,
                "criticality": requirement["criticality"],
                "lifecycle_phase": requirement["lifecycle_phase"],
                "claim_status": claim["status"],
                "evidence_refs": declared_evidence,
                "linked_test_count": len(linked_results),
                "exact_test_count": sum(linked_results),
                "state": state,
                "limitations": claim["limitations"],
            }
        )

    dimensions = [
        {
            "dimension": name,
            "exact_cases": sum(values),
            "case_count": len(values),
        }
        for name, values in dimension_rows.items()
    ]
    return {
        "assessment_version": ASSESSMENT_VERSION,
        "pilot_id": agency["pilot_id"],
        "response_id": vendor["response_id"],
        "boundary": {
            "vendor_ranked": False,
            "award_recommendation_made": False,
            "certification_made": False,
            "accountable_decision_required": True,
        },
        "summary": {
            "requirements": len(requirement_rows),
            "tested_requirements": sum(item["state"] == "tested" for item in requirement_rows),
            "visible_gaps": sum(item["state"] != "tested" for item in requirement_rows),
            "cases": len(case_rows),
            "exact_cases": sum(item["exact"] for item in case_rows),
            "critical_requirement_gaps": critical_gaps,
            "critical_authority_failures": critical_authority_failures,
        },
        "requirements": requirement_rows,
        "tests": case_rows,
        "dimensions": dimensions,
        "commercial_review": {
            "agency_pricing_unit": agency["commercial"]["pricing_unit"],
            "vendor_currency": vendor["pricing"]["currency"],
            "vendor_maximum_scenario_cost": vendor["pricing"]["maximum_scenario_cost"],
            "cost_scenarios": agency["commercial"]["cost_scenarios"],
            "data_use_response": vendor["terms"]["government_data_use"],
            "portability_response": vendor["terms"]["portability"],
            "exit_support_response": vendor["terms"]["exit_support"],
        },
    }


def bullet(items: Any) -> str:
    values = items if isinstance(items, list) else [items]
    return "\n".join(f"- {item}" for item in values if str(item).strip()) or "- Not documented"


def render_pack_files(
    agency: dict[str, Any], vendor: dict[str, Any], tests: dict[str, Any], assessment: dict[str, Any]
) -> dict[str, str]:
    boundary = (
        "> Independent evidence aid. This pack does not rank vendors, recommend an award, "
        "certify a system, or replace an accountable official.\n\n"
    )
    summary = assessment["summary"]
    requirements = {item["requirement_id"]: item for item in agency["requirements"]}
    files: dict[str, str] = {
        "agency-intake.json": json.dumps(agency, indent=2) + "\n",
        "vendor-response.json": json.dumps(vendor, indent=2) + "\n",
        "acceptance-tests.json": json.dumps(tests, indent=2) + "\n",
        "assessment.json": json.dumps(assessment, indent=2) + "\n",
    }
    files["README.md"] = (
        f"# Federal pilot evidence exchange — {agency['mission']['title']}\n\n"
        + boundary
        + f"Pilot: `{agency['pilot_id']}` · Response: `{vendor['response_id']}`\n\n"
        + "## Inspect first\n\n"
        + f"- {summary['tested_requirements']} of {summary['requirements']} requirements reach the `tested` evidence state.\n"
        + f"- {summary['exact_cases']} of {summary['cases']} submitted synthetic cases match the declared oracle exactly.\n"
        + f"- Critical requirement gaps: {', '.join(summary['critical_requirement_gaps']) or 'none in this submitted packet'}.\n"
        + f"- Critical authority failures: {', '.join(summary['critical_authority_failures']) or 'none in this submitted packet'}.\n\n"
        + "These counts describe one evidence packet. They are not a proposal score, comparative ranking, compliance finding, or award decision.\n\n"
        + "## Contents\n\n"
        + bullet(PACK_NAMES[1:-1])
        + "\n"
    )
    ledger_rows = []
    for row in assessment["requirements"]:
        requirement = requirements[row["requirement_id"]]
        ledger_rows.append(
            f"| `{row['requirement_id']}` | {requirement['outcome']} | **{row['state']}** | "
            f"{', '.join(row['evidence_refs']) or 'none'} | {row['exact_test_count']}/{row['linked_test_count']} | "
            f"{row['limitations']} |"
        )
    files["01-claim-evidence-test-ledger.md"] = (
        "# 01 — Claim → evidence → test ledger\n\n" + boundary
        + "| Requirement | Requested outcome | Evidence state | Evidence | Exact tests | Disclosed limitation |\n"
        + "|---|---|---|---|---:|---|\n" + "\n".join(ledger_rows) + "\n"
    )
    test_rows = [
        f"| `{row['case_id']}` | {row['dimension']} | {'yes' if row['critical'] else 'no'} | "
        f"**{'exact' if row['exact'] else 'review'}** | "
        f"{', '.join(name for name, passed in row['checks'].items() if not passed) or 'none'} | {row['failure_shape']} |"
        for row in assessment["tests"]
    ]
    files["02-acceptance-test-report.md"] = (
        "# 02 — Synthetic acceptance-test report\n\n" + boundary
        + f"Environment: {tests['test_environment']}\n\n"
        + "| Case | Dimension | Critical | Result | Failed exact fields | Failure shape |\n"
        + "|---|---|---|---|---|---|\n" + "\n".join(test_rows) + "\n\n"
        + "A matching submitted result proves only that the recorded output matches the declared synthetic oracle. It does not prove deployment performance or independent reproduction.\n"
    )
    commercial = agency["commercial"]
    files["03-commercial-data-and-exit-review.md"] = (
        "# 03 — Commercial, government-data, and exit review\n\n" + boundary
        + f"## Agency pricing unit\n\n{commercial['pricing_unit']}\n\n"
        + "## Required cost scenarios\n\n" + "\n".join(
            f"- **{item['name']}** — {item['volume']}" for item in commercial["cost_scenarios"]
        ) + "\n\n"
        + f"## Submitted maximum scenario cost\n\n{vendor['pricing']['maximum_scenario_cost']} {vendor['pricing']['currency']}\n\n"
        + f"## Government-data use\n\n{vendor['terms']['government_data_use']}\n\n"
        + f"## Portability\n\n{vendor['terms']['portability']}\n\n"
        + f"## Knowledge transfer\n\n{vendor['terms']['knowledge_transfer']}\n\n"
        + f"## Exit support\n\n{vendor['terms']['exit_support']}\n"
    )
    monitoring = agency["monitoring"]
    files["04-post-award-monitoring-plan.md"] = (
        "# 04 — Post-award monitoring draft\n\n" + boundary
        + "## Metrics\n\n" + bullet(monitoring["metrics"]) + "\n\n"
        + f"## Cadence\n\n{monitoring['cadence']}\n\n"
        + f"## Incident route\n\n{monitoring['incident_route']}\n\n"
        + f"## Reassessment trigger\n\n{monitoring['reassessment_trigger']}\n\n"
        + f"## Cease-use trigger\n\n{monitoring['cease_use_trigger']}\n"
    )
    files["05-lessons-learned.md"] = (
        "# 05 — Acquisition lessons-learned record\n\n" + boundary
        + "Complete this record after each acquisition phase. Remove source-selection, procurement-sensitive, controlled, classified, and personally identifiable information before sharing.\n\n"
        + "## Requirement that produced the clearest evidence\n\n_Not yet recorded._\n\n"
        + "## Requirement or term that was ambiguous\n\n_Not yet recorded._\n\n"
        + "## Intended-environment test that changed the team's understanding\n\n_Not yet recorded._\n\n"
        + "## Pricing, data-rights, portability, or exit lesson\n\n_Not yet recorded._\n\n"
        + "## Reusable artifact and safe sharing route\n\n_Not yet recorded._\n"
    )
    return files


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def build_manifest(agency: dict[str, Any], vendor: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    return {
        "manifest_version": PACK_VERSION,
        "pilot_id": agency["pilot_id"],
        "response_id": vendor["response_id"],
        "hash_algorithm": "sha256",
        "files": [
            {
                "path": name,
                "sha256": sha256_bytes(contents.encode("utf-8")),
                "bytes": len(contents.encode("utf-8")),
            }
            for name, contents in sorted(files.items())
        ],
        "claims": {
            "byte_integrity_only": True,
            "vendor_ranked": False,
            "award_recommendation_made": False,
            "certification_made": False,
            "independent_reproduction_proved": False,
        },
    }


def command_validate(args: argparse.Namespace) -> int:
    value = load_json(args.document)
    errors = VALIDATORS[args.kind](value)
    result = {"valid": not errors, "kind": args.kind, "errors": errors}
    if args.json:
        print(json.dumps(result, indent=2))
    elif errors:
        print(f"INVALID {args.kind.upper()} DOCUMENT — {len(errors)} issue(s)")
        for error in errors:
            print(f"- {error}")
    else:
        print(f"VALID {args.kind.upper()} DOCUMENT")
        print("Structural validity is not evidence quality, compliance, certification, ranking, or approval.")
    return 0 if not errors else 1


def command_assess(args: argparse.Namespace) -> int:
    assessment = assess_exchange(
        load_json(args.agency), load_json(args.vendor), load_json(args.tests)
    )
    if args.json:
        print(json.dumps(assessment, indent=2))
    else:
        summary = assessment["summary"]
        print(f"EVIDENCE EXCHANGE ASSESSED — {assessment['pilot_id']}")
        print(
            f"- tested requirements: {summary['tested_requirements']}/{summary['requirements']}\n"
            f"- exact submitted cases: {summary['exact_cases']}/{summary['cases']}\n"
            f"- critical requirement gaps: {', '.join(summary['critical_requirement_gaps']) or 'none'}\n"
            f"- critical authority failures: {', '.join(summary['critical_authority_failures']) or 'none'}"
        )
        print("No vendor ranking, award recommendation, certification, or compliance finding was made.")
    return 0


def command_pack(args: argparse.Namespace) -> int:
    agency, vendor, tests = load_json(args.agency), load_json(args.vendor), load_json(args.tests)
    assessment = assess_exchange(agency, vendor, tests)
    output: Path = args.out
    if output.is_symlink():
        raise ValueError(f"refusing symbolic-link output path: {output}")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"refusing to overwrite non-empty output path: {output}")
    output.mkdir(parents=True, exist_ok=True)
    files = render_pack_files(agency, vendor, tests, assessment)
    files["manifest.json"] = json.dumps(build_manifest(agency, vendor, files), indent=2) + "\n"
    for name, contents in files.items():
        (output / name).write_text(contents, encoding="utf-8")
    print(f"wrote {len(files)} files to {output}")
    print("The pack preserves visible gaps; it does not rank, recommend, certify, or approve.")
    return 0


def command_verify_pack(args: argparse.Namespace) -> int:
    if args.directory.is_symlink() or not args.directory.is_dir():
        raise ValueError("pack path must be a regular directory")
    manifest = load_json(args.directory / "manifest.json")
    errors: list[str] = []
    if manifest.get("manifest_version") != PACK_VERSION:
        errors.append(f"manifest_version must equal {PACK_VERSION!r}")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        entries = []
        errors.append("manifest.files must be an array")
    expected = set(PACK_NAMES) - {"manifest.json"}
    names = [item.get("path") for item in entries if isinstance(item, dict)]
    if len(names) != len(set(names)):
        errors.append("manifest contains duplicate paths")
    if set(names) != expected:
        errors.append(f"manifest file set must equal the 10-file payload: {sorted(expected)}")
    for item in entries:
        if not isinstance(item, dict):
            errors.append("manifest entries must be objects")
            continue
        name = item.get("path")
        if name not in expected:
            continue
        path = args.directory / name
        if path.is_symlink() or not path.is_file():
            errors.append(f"missing {name}")
            continue
        if path.stat().st_size > MAX_PACK_FILE_BYTES:
            errors.append(f"file exceeds {MAX_PACK_FILE_BYTES} bytes: {name}")
            continue
        contents = path.read_bytes()
        if not SHA256.fullmatch(str(item.get("sha256", ""))):
            errors.append(f"invalid digest: {name}")
        if sha256_bytes(contents) != item.get("sha256"):
            errors.append(f"digest mismatch: {name}")
        if not isinstance(item.get("bytes"), int) or len(contents) != item.get("bytes"):
            errors.append(f"byte-count mismatch: {name}")
    if args.directory.is_dir():
        extra = {path.name for path in args.directory.iterdir()} - set(PACK_NAMES)
        if extra:
            errors.append(f"unlisted files: {sorted(extra)}")
    claims = manifest.get("claims", {})
    if claims.get("vendor_ranked") is not False or claims.get("award_recommendation_made") is not False:
        errors.append("manifest must preserve non-ranking and non-award boundaries")
    if errors:
        print("PACK INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PACK INTEGRITY VERIFIED — {len(entries)} hashed files")
    print("Integrity does not prove evidence quality, independent reproduction, compliance, or approval.")
    return 0


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def build_closeout_files(
    agency: dict[str, Any],
    vendor: dict[str, Any],
    tests: dict[str, Any],
    lesson: dict[str, Any],
    ledger: dict[str, Any],
) -> dict[str, str]:
    assessment = assess_exchange(agency, vendor, tests)
    scan = scan_sensitive(lesson)
    referenced_evidence = set(lesson["trace"]["evidence_ids"])
    evidence = [
        item for item in vendor["evidence"] if item["evidence_id"] in referenced_evidence
    ]
    source_ids = {item["source_id"] for item in lesson["policy_dependencies"]}
    sources = [item for item in ledger["sources"] if item["source_id"] in source_ids]
    evidence_index = {
        "index_version": LESSON_CLOSEOUT_VERSION,
        "lesson_id": lesson["lesson_id"],
        "source_document_digests": {
            "agency-intake.json": sha256_bytes(canonical_json_bytes(agency)),
            "vendor-response.json": sha256_bytes(canonical_json_bytes(vendor)),
            "acceptance-tests.json": sha256_bytes(canonical_json_bytes(tests)),
        },
        "public_evidence": evidence,
        "boundary": (
            "Digests identify the reviewed source documents but do not publish them. Evidence entries "
            "remain responder declarations unless their verification field states otherwise."
        ),
    }
    assessment_summary = {
        "assessment_version": assessment["assessment_version"],
        "pilot_id": assessment["pilot_id"],
        "response_id": assessment["response_id"],
        "boundary": assessment["boundary"],
        "summary": assessment["summary"],
        "dimensions": assessment["dimensions"],
    }
    source_snapshot = {
        "ledger_version": ledger["ledger_version"],
        "captured_for_lesson": lesson["lesson_id"],
        "boundary": ledger["boundary"],
        "sources": sources,
    }
    files = {
        "lesson.json": json.dumps(lesson, indent=2) + "\n",
        "assessment-summary.json": json.dumps(assessment_summary, indent=2) + "\n",
        "evidence-index.json": json.dumps(evidence_index, indent=2) + "\n",
        "privacy-scan.json": json.dumps(scan, indent=2) + "\n",
        "source-snapshot.json": json.dumps(source_snapshot, indent=2) + "\n",
    }
    files["README.md"] = (
        f"# Federal AI acquisition lesson — {lesson['mission']['title']}\n\n"
        "> Public evidence handoff. This bundle does not rank vendors, recommend an award, "
        "certify a system, determine compliance, or replace an accountable official.\n\n"
        f"Lesson: `{lesson['lesson_id']}` · Pilot: `{lesson['pilot_id']}` · "
        f"Observed result: **{lesson['outcome']['result']}**\n\n"
        "## What changed\n\n"
        f"{lesson['outcome']['observed_change']}\n\n"
        "## Reusable practice\n\n"
        f"**{lesson['reusable_practice']['title']}** — {lesson['reusable_practice']['action']}\n\n"
        "This practice is intentionally bounded. Read `lesson.json` for prerequisites, "
        "non-transfer conditions, limitations, source dependencies, and revalidation triggers.\n\n"
        "## Verify first\n\n"
        f"- Privacy scan findings: {scan['finding_count']}\n"
        f"- Source dependencies captured: {len(sources)}\n"
        f"- Source exchange requirements: {assessment['summary']['requirements']}\n"
        f"- Exact submitted synthetic cases: {assessment['summary']['exact_cases']}/{assessment['summary']['cases']}\n\n"
        "A zero-finding scanner result is not a disclosure authorization. The named human "
        "redaction and publication roles remain responsible for public release.\n"
    )
    return files


def build_closeout_manifest(lesson: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    return {
        "manifest_version": LESSON_CLOSEOUT_VERSION,
        "lesson_id": lesson["lesson_id"],
        "pilot_id": lesson["pilot_id"],
        "hash_algorithm": "sha256",
        "files": [
            {
                "path": name,
                "sha256": sha256_bytes(contents.encode("utf-8")),
                "bytes": len(contents.encode("utf-8")),
            }
            for name, contents in sorted(files.items())
        ],
        "claims": {
            "byte_integrity_only": True,
            "public_release_authorized_by_tool": False,
            "vendor_ranked": False,
            "award_recommendation_made": False,
            "certification_made": False,
            "practice_is_universal": False,
        },
    }


def command_scan_lesson(args: argparse.Namespace) -> int:
    lesson = load_json(args.lesson)
    errors = validate_lesson(lesson)
    scan = scan_sensitive(lesson)
    result = {"valid": not errors, "validation_errors": errors, **scan}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"LESSON PUBLICATION SCAN — {scan['finding_count']} finding(s); "
            f"structurally {'valid' if not errors else 'invalid'}"
        )
        for error in errors:
            print(f"- VALIDATION: {error}")
        for finding in scan["findings"]:
            print(f"- {finding['code']} at {finding['path']} [{finding['fingerprint']}]")
        print(scan["boundary"])
    return 0 if not errors and scan["safe_to_package"] else 1


def command_closeout(args: argparse.Namespace) -> int:
    agency = load_json(args.agency)
    vendor = load_json(args.vendor)
    tests = load_json(args.tests)
    lesson = load_json(args.lesson)
    ledger = load_json(args.sources)
    errors = cross_validate_lesson(lesson, agency, vendor, tests, ledger)
    scan = scan_sensitive(lesson)
    if errors:
        raise ValueError("lesson closeout is invalid: " + "; ".join(errors))
    if not scan["safe_to_package"]:
        codes = sorted({item["code"] for item in scan["findings"]})
        raise ValueError(f"lesson closeout is blocked by the publication scan: {codes}")
    output: Path = args.out
    if output.is_symlink():
        raise ValueError(f"refusing symbolic-link output path: {output}")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"refusing to overwrite non-empty output path: {output}")
    output.mkdir(parents=True, exist_ok=True)
    files = build_closeout_files(agency, vendor, tests, lesson, ledger)
    files["manifest.json"] = json.dumps(build_closeout_manifest(lesson, files), indent=2) + "\n"
    for name, contents in files.items():
        (output / name).write_text(contents, encoding="utf-8")
    print(f"wrote {len(files)} files to {output}")
    print("The lesson remains bounded, non-comparative, and subject to authorized human review.")
    return 0


def command_verify_closeout(args: argparse.Namespace) -> int:
    directory: Path = args.directory
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("closeout path must be a regular directory")
    manifest = load_json(directory / "manifest.json")
    errors: list[str] = []
    if manifest.get("manifest_version") != LESSON_CLOSEOUT_VERSION:
        errors.append(f"manifest_version must equal {LESSON_CLOSEOUT_VERSION!r}")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        entries = []
        errors.append("manifest.files must be an array")
    expected = set(CLOSEOUT_NAMES) - {"manifest.json"}
    names = [item.get("path") for item in entries if isinstance(item, dict)]
    if len(names) != len(set(names)):
        errors.append("manifest contains duplicate paths")
    if set(names) != expected:
        errors.append(f"manifest file set must equal the 6-file payload: {sorted(expected)}")
    for item in entries:
        if not isinstance(item, dict):
            errors.append("manifest entries must be objects")
            continue
        name = item.get("path")
        if name not in expected:
            continue
        path = directory / name
        if path.is_symlink() or not path.is_file():
            errors.append(f"missing {name}")
            continue
        if path.stat().st_size > MAX_PACK_FILE_BYTES:
            errors.append(f"file exceeds {MAX_PACK_FILE_BYTES} bytes: {name}")
            continue
        contents = path.read_bytes()
        if not SHA256.fullmatch(str(item.get("sha256", ""))):
            errors.append(f"invalid digest: {name}")
        if sha256_bytes(contents) != item.get("sha256"):
            errors.append(f"digest mismatch: {name}")
        if not isinstance(item.get("bytes"), int) or len(contents) != item.get("bytes"):
            errors.append(f"byte-count mismatch: {name}")
    extra = {path.name for path in directory.iterdir()} - set(CLOSEOUT_NAMES)
    if extra:
        errors.append(f"unlisted files: {sorted(extra)}")
    claims = manifest.get("claims") if isinstance(manifest.get("claims"), dict) else {}
    if (
        claims.get("vendor_ranked") is not False
        or claims.get("award_recommendation_made") is not False
        or claims.get("practice_is_universal") is not False
    ):
        errors.append("manifest must preserve non-ranking, non-award, and non-universal boundaries")
    try:
        lesson = load_json(directory / "lesson.json")
        scan = load_json(directory / "privacy-scan.json")
        errors.extend(validate_lesson(lesson))
        if scan != scan_sensitive(lesson):
            errors.append("privacy scan does not match the packaged lesson")
    except ValueError as exc:
        errors.append(str(exc))
    if errors:
        print("LESSON CLOSEOUT INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"LESSON CLOSEOUT VERIFIED — {manifest['lesson_id']} · {len(entries)} hashed files")
    print("Integrity and scanning do not authorize disclosure or prove universal applicability.")
    return 0


def policy_drift_report(
    lesson: dict[str, Any], ledger: dict[str, Any], as_of: date
) -> dict[str, Any]:
    errors = validate_lesson(lesson) + validate_source_ledger(ledger)
    if errors:
        raise ValueError("cannot check policy drift: " + "; ".join(errors))
    sources = {item["source_id"]: item for item in ledger["sources"]}
    rows = []
    for dependency in lesson["policy_dependencies"]:
        source = sources.get(dependency["source_id"])
        if not source:
            rows.append(
                {
                    "source_id": dependency["source_id"],
                    "state": "missing",
                    "review_due": None,
                    "dependency": dependency["dependency"],
                }
            )
            continue
        due = date.fromisoformat(source["review_due"])
        rows.append(
            {
                "source_id": source["source_id"],
                "title": source["title"],
                "state": "review_due" if due <= as_of else "current",
                "last_verified": source["last_verified"],
                "review_due": source["review_due"],
                "dependency": dependency["dependency"],
                "revalidate_on": dependency["revalidate_on"],
            }
        )
    lesson_due = date.fromisoformat(lesson["review_due"]) <= as_of
    return {
        "lesson_id": lesson["lesson_id"],
        "as_of": as_of.isoformat(),
        "lesson_review": "review_due" if lesson_due else "current",
        "sources": rows,
        "summary": {
            "dependencies": len(rows),
            "current": sum(item["state"] == "current" for item in rows),
            "review_due": sum(item["state"] == "review_due" for item in rows),
            "missing": sum(item["state"] == "missing" for item in rows),
        },
        "boundary": "A current source ledger does not establish legal applicability or approve reuse.",
    }


def command_policy_drift(args: argparse.Namespace) -> int:
    lesson = load_json(args.lesson)
    ledger = load_json(args.sources)
    as_of = date.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc).date()
    result = policy_drift_report(lesson, ledger, as_of)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        summary = result["summary"]
        print(
            f"POLICY DEPENDENCY CHECK — {result['lesson_id']} · "
            f"{summary['current']} current · {summary['review_due']} review due · "
            f"{summary['missing']} missing"
        )
        for item in result["sources"]:
            print(f"- {item['source_id']}: {item['state']} ({item.get('review_due') or 'no review date'})")
        print(result["boundary"])
    stale = result["lesson_review"] == "review_due" or any(
        item["state"] != "current" for item in result["sources"]
    )
    return 1 if stale else 0


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
    changed = [
        {"path": key, "before": before.get(key), "after": after.get(key)}
        for key in sorted(set(before) | set(after))
        if before.get(key) != after.get(key)
    ]
    if args.json:
        print(json.dumps(changed, indent=2))
    elif not changed:
        print("NO EXCHANGE CHANGES")
    else:
        print(f"{len(changed)} EXCHANGE CHANGE(S)")
        for item in changed:
            print(f"- {item['path']}: {item['before']!r} -> {item['after']!r}")
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="AAU Federal Pilot Kit evidence tools")
    sub = value.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate one agency, vendor, or test document")
    validate.add_argument("kind", choices=sorted(VALIDATORS))
    validate.add_argument("document", type=Path)
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate)
    assess = sub.add_parser("assess", help="map claims to evidence and exact synthetic tests")
    assess.add_argument("agency", type=Path)
    assess.add_argument("vendor", type=Path)
    assess.add_argument("tests", type=Path)
    assess.add_argument("--json", action="store_true")
    assess.set_defaults(func=command_assess)
    pack = sub.add_parser("pack", help="render an 11-file evidence exchange")
    pack.add_argument("agency", type=Path)
    pack.add_argument("vendor", type=Path)
    pack.add_argument("tests", type=Path)
    pack.add_argument("--out", type=Path, required=True)
    pack.set_defaults(func=command_pack)
    verify = sub.add_parser("verify-pack", help="recompute and compare pack digests")
    verify.add_argument("directory", type=Path)
    verify.set_defaults(func=command_verify_pack)
    diff = sub.add_parser("diff", help="show semantic field changes between documents")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    diff.add_argument("--json", action="store_true")
    diff.set_defaults(func=command_diff)
    scan = sub.add_parser(
        "scan-lesson",
        help="run structural and narrow sensitive-data checks before public packaging",
    )
    scan.add_argument("lesson", type=Path)
    scan.add_argument("--json", action="store_true")
    scan.set_defaults(func=command_scan_lesson)
    closeout = sub.add_parser(
        "closeout",
        help="turn a completed public or synthetic pilot into a verifiable lesson bundle",
    )
    closeout.add_argument("agency", type=Path)
    closeout.add_argument("vendor", type=Path)
    closeout.add_argument("tests", type=Path)
    closeout.add_argument("lesson", type=Path)
    closeout.add_argument(
        "--sources",
        type=Path,
        default=Path(__file__).resolve().parent / "lessons" / "source-ledger.json",
    )
    closeout.add_argument("--out", type=Path, required=True)
    closeout.set_defaults(func=command_closeout)
    verify_closeout = sub.add_parser(
        "verify-closeout",
        help="recompute a lesson closeout's digests and publication scan",
    )
    verify_closeout.add_argument("directory", type=Path)
    verify_closeout.set_defaults(func=command_verify_closeout)
    drift = sub.add_parser(
        "policy-drift",
        help="show source dependencies that are missing or due for revalidation",
    )
    drift.add_argument("lesson", type=Path)
    drift.add_argument(
        "--sources",
        type=Path,
        default=Path(__file__).resolve().parent / "lessons" / "source-ledger.json",
    )
    drift.add_argument("--as-of", help="ISO date; defaults to today")
    drift.add_argument("--json", action="store_true")
    drift.set_defaults(func=command_policy_drift)
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
