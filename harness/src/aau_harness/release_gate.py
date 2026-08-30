"""Change-aware, provider-neutral release evidence for tool-using agents.

The gate hashes declared release components, identifies which safety boundaries
changed, runs only the public suites mapped to those changes, and emits a
deterministic evidence pack.  It never deploys an agent and never treats a
structural approval record as verified human identity or operational authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.parse
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .evaluate import (
    AdapterResult,
    command_adapter,
    endpoint_adapter,
    evaluate_suite,
    load_suite,
    mock_adapter,
)


MANIFEST_VERSION = "aau-agent-release-manifest/1.0"
SNAPSHOT_VERSION = "aau-agent-release-snapshot/1.0"
POLICY_VERSION = "aau-agent-release-policy/1.0"
PLAN_VERSION = "aau-agent-release-evidence-plan/1.0"
APPROVAL_VERSION = "aau-agent-release-approval/1.0"
DIFF_VERSION = "aau-agent-release-diff/1.0"
DECISION_VERSION = "aau-agent-release-decision/1.0"
PACK_VERSION = "aau-agent-release-pack/1.0"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = (
    "https://immu4989.github.io/awesome-agentic-usecases/"
    "predicates/agent-release-gate/v1"
)
OSCAL_VERSION = "1.1.3"
MAX_JSON_BYTES = 2_000_000
MAX_COMPONENT_BYTES = 5_000_000
MAX_COMPONENTS = 100
MAX_SUITES = 50
HEX = set("0123456789abcdef")
COMPONENT_KINDS = {
    "model",
    "system_policy",
    "tool_contract",
    "agent_card",
    "identity",
    "authority",
    "dependency",
    "egress",
    "monitoring",
    "rollback",
}
IMPACT_TAGS = {
    "model_behavior",
    "policy",
    "tools",
    "peer_interop",
    "identity",
    "authority",
    "dependencies",
    "egress",
    "monitoring",
    "rollback",
}
SHARING_KEYS = {
    "public_or_synthetic_only",
    "contains_personal_data",
    "contains_credentials",
    "contains_nonpublic_configuration",
    "contains_controlled_information",
}
BOUNDARY_KEYS = {
    "human_release_authority_preserved",
    "mock_cannot_authorize_release",
    "approval_identity_not_cryptographically_verified",
    "not_certification_or_compliance",
    "not_deployment_or_ato",
}


class ReleaseGateError(ValueError):
    """Raised when release evidence violates the public contract."""


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def rendered(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(payload).hexdigest()


def _sha(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in HEX for char in value)
    ):
        raise ReleaseGateError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _text(value: Any, label: str, limit: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ReleaseGateError(
            f"{label} must be non-empty text of at most {limit} characters"
        )
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ReleaseGateError(f"{label} fields differ from the 1.0 contract")
    return value


def _timestamp(value: Any, label: str) -> str:
    value = _text(value, label, 40)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseGateError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ReleaseGateError(f"{label} must include a timezone")
    return value


def _load_bytes(path: Path, limit: int = MAX_JSON_BYTES) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ReleaseGateError(f"invalid or symbolic-link file: {path}")
    if path.stat().st_size > limit:
        raise ReleaseGateError(f"file exceeds {limit} bytes: {path}")
    return path.read_bytes()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_load_bytes(path))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseGateError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReleaseGateError(f"expected one JSON object in {path}")
    return value


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise ReleaseGateError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(rendered(value))


def _safe_component_path(manifest_path: Path, relative: str) -> Path:
    relative = _text(relative, "component source path", 300)
    pure = Path(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise ReleaseGateError("component source path must stay below the manifest directory")
    base = manifest_path.parent.resolve()
    candidate = base / pure
    current = base
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise ReleaseGateError(f"component source path contains a symlink: {relative}")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ReleaseGateError("component source escapes the manifest directory") from exc
    return resolved


def validate_manifest(manifest: dict[str, Any]) -> None:
    _exact(
        manifest,
        {
            "manifest_version",
            "release_id",
            "agent_id",
            "effective_at",
            "environment",
            "components",
            "sharing",
        },
        "release manifest",
    )
    if manifest["manifest_version"] != MANIFEST_VERSION:
        raise ReleaseGateError(f"manifest_version must be {MANIFEST_VERSION}")
    _text(manifest["release_id"], "release_id", 120)
    _text(manifest["agent_id"], "agent_id", 160)
    _timestamp(manifest["effective_at"], "effective_at")
    if manifest["environment"] not in {"public", "synthetic", "public_synthetic"}:
        raise ReleaseGateError("environment must be public, synthetic, or public_synthetic")

    sharing = _exact(manifest["sharing"], SHARING_KEYS, "sharing")
    if sharing["public_or_synthetic_only"] is not True:
        raise ReleaseGateError("sharing.public_or_synthetic_only must be true")
    for key in SHARING_KEYS - {"public_or_synthetic_only"}:
        if sharing[key] is not False:
            raise ReleaseGateError(f"sharing.{key} must be false")

    components = manifest["components"]
    if not isinstance(components, list) or not 1 <= len(components) <= MAX_COMPONENTS:
        raise ReleaseGateError(f"components must contain 1 to {MAX_COMPONENTS} entries")
    seen: set[str] = set()
    for index, component in enumerate(components):
        component = _exact(
            component,
            {"component_id", "kind", "source_path", "impact_tags", "required"},
            f"components[{index}]",
        )
        component_id = _text(component["component_id"], f"components[{index}].component_id", 120)
        if component_id in seen:
            raise ReleaseGateError(f"duplicate component_id: {component_id}")
        seen.add(component_id)
        if component["kind"] not in COMPONENT_KINDS:
            raise ReleaseGateError(f"components[{index}].kind is unsupported")
        _text(component["source_path"], f"components[{index}].source_path", 300)
        tags = component["impact_tags"]
        if (
            not isinstance(tags, list)
            or not tags
            or len(tags) != len(set(tags))
            or not set(tags).issubset(IMPACT_TAGS)
        ):
            raise ReleaseGateError(f"components[{index}].impact_tags are invalid")
        if not isinstance(component["required"], bool):
            raise ReleaseGateError(f"components[{index}].required must be boolean")


def capture_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    validate_manifest(manifest)
    components = []
    for component in sorted(manifest["components"], key=lambda item: item["component_id"]):
        source = _safe_component_path(manifest_path, component["source_path"])
        payload = _load_bytes(source, MAX_COMPONENT_BYTES)
        components.append(
            {
                "component_id": component["component_id"],
                "kind": component["kind"],
                "source_path": Path(component["source_path"]).as_posix(),
                "bytes": len(payload),
                "sha256": digest(payload),
                "impact_tags": sorted(component["impact_tags"]),
                "required": component["required"],
            }
        )
    snapshot = {
        "snapshot_version": SNAPSHOT_VERSION,
        "release_id": manifest["release_id"],
        "agent_id": manifest["agent_id"],
        "effective_at": manifest["effective_at"],
        "environment": manifest["environment"],
        "components": components,
        "sharing": manifest["sharing"],
        "snapshot_sha256": "",
    }
    snapshot["snapshot_sha256"] = digest(
        {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    )
    validate_snapshot(snapshot)
    return snapshot


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    _exact(
        snapshot,
        {
            "snapshot_version",
            "release_id",
            "agent_id",
            "effective_at",
            "environment",
            "components",
            "sharing",
            "snapshot_sha256",
        },
        "release snapshot",
    )
    if snapshot["snapshot_version"] != SNAPSHOT_VERSION:
        raise ReleaseGateError(f"snapshot_version must be {SNAPSHOT_VERSION}")
    _text(snapshot["release_id"], "snapshot release_id", 120)
    _text(snapshot["agent_id"], "snapshot agent_id", 160)
    _timestamp(snapshot["effective_at"], "snapshot effective_at")
    if snapshot["environment"] not in {"public", "synthetic", "public_synthetic"}:
        raise ReleaseGateError("snapshot environment is unsupported")
    sharing = _exact(snapshot["sharing"], SHARING_KEYS, "snapshot sharing")
    if sharing["public_or_synthetic_only"] is not True or any(
        sharing[key] is not False for key in SHARING_KEYS - {"public_or_synthetic_only"}
    ):
        raise ReleaseGateError("snapshot sharing boundary is invalid")
    components = snapshot["components"]
    if not isinstance(components, list) or not 1 <= len(components) <= MAX_COMPONENTS:
        raise ReleaseGateError("snapshot components are invalid")
    ids: set[str] = set()
    for index, component in enumerate(components):
        component = _exact(
            component,
            {
                "component_id",
                "kind",
                "source_path",
                "bytes",
                "sha256",
                "impact_tags",
                "required",
            },
            f"snapshot components[{index}]",
        )
        component_id = _text(component["component_id"], "snapshot component_id", 120)
        if component_id in ids:
            raise ReleaseGateError("snapshot component ids must be unique")
        ids.add(component_id)
        if component["kind"] not in COMPONENT_KINDS:
            raise ReleaseGateError("snapshot component kind is unsupported")
        _text(component["source_path"], "snapshot source_path", 300)
        if not isinstance(component["bytes"], int) or not 0 <= component["bytes"] <= MAX_COMPONENT_BYTES:
            raise ReleaseGateError("snapshot component byte count is invalid")
        _sha(component["sha256"], "snapshot component sha256")
        tags = component["impact_tags"]
        if not isinstance(tags, list) or not tags or not set(tags).issubset(IMPACT_TAGS):
            raise ReleaseGateError("snapshot impact tags are invalid")
        if tags != sorted(set(tags)) or not isinstance(component["required"], bool):
            raise ReleaseGateError("snapshot component normalization is invalid")
    _sha(snapshot["snapshot_sha256"], "snapshot_sha256")
    expected = digest({key: value for key, value in snapshot.items() if key != "snapshot_sha256"})
    if snapshot["snapshot_sha256"] != expected:
        raise ReleaseGateError("snapshot embedded digest mismatch")


def diff_snapshots(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    validate_snapshot(baseline)
    validate_snapshot(candidate)
    if baseline["agent_id"] != candidate["agent_id"]:
        raise ReleaseGateError("baseline and candidate agent_id must match")
    before = {item["component_id"]: item for item in baseline["components"]}
    after = {item["component_id"]: item for item in candidate["components"]}
    changes = []
    impacted: set[str] = set()
    for component_id in sorted(before.keys() | after.keys()):
        old = before.get(component_id)
        new = after.get(component_id)
        if old is None:
            state = "added"
        elif new is None:
            state = "removed"
        elif old["sha256"] != new["sha256"] or old["kind"] != new["kind"]:
            state = "changed"
        else:
            state = "unchanged"
        tags = sorted(set((old or {}).get("impact_tags", [])) | set((new or {}).get("impact_tags", [])))
        if state != "unchanged":
            impacted.update(tags)
            changes.append(
                {
                    "component_id": component_id,
                    "state": state,
                    "before_kind": old["kind"] if old else None,
                    "after_kind": new["kind"] if new else None,
                    "before_sha256": old["sha256"] if old else None,
                    "after_sha256": new["sha256"] if new else None,
                    "impact_tags": tags,
                    "required_before": old["required"] if old else None,
                    "required_after": new["required"] if new else None,
                }
            )
    result = {
        "diff_version": DIFF_VERSION,
        "agent_id": baseline["agent_id"],
        "baseline_release_id": baseline["release_id"],
        "candidate_release_id": candidate["release_id"],
        "baseline_snapshot_sha256": baseline["snapshot_sha256"],
        "candidate_snapshot_sha256": candidate["snapshot_sha256"],
        "changes": changes,
        "impacted_tags": sorted(impacted),
        "diff_sha256": "",
    }
    result["diff_sha256"] = digest(
        {key: value for key, value in result.items() if key != "diff_sha256"}
    )
    return result


def validate_policy(policy: dict[str, Any]) -> None:
    _exact(
        policy,
        {
            "policy_version",
            "policy_id",
            "title",
            "requirements",
            "protected_review_tags",
            "required_component_kinds",
            "boundaries",
        },
        "release policy",
    )
    if policy["policy_version"] != POLICY_VERSION:
        raise ReleaseGateError(f"policy_version must be {POLICY_VERSION}")
    _text(policy["policy_id"], "policy_id", 120)
    _text(policy["title"], "policy title", 240)
    requirements = policy["requirements"]
    if not isinstance(requirements, list) or not requirements:
        raise ReleaseGateError("policy requirements must be non-empty")
    seen: set[tuple[str, str]] = set()
    for index, requirement in enumerate(requirements):
        requirement = _exact(
            requirement,
            {
                "impact_tag",
                "suite_id",
                "minimum_exact_rate",
                "minimum_no_forbidden_execute_rate",
            },
            f"requirements[{index}]",
        )
        if requirement["impact_tag"] not in IMPACT_TAGS:
            raise ReleaseGateError("policy requirement impact_tag is unsupported")
        suite_id = _text(requirement["suite_id"], "requirement suite_id", 160)
        key = (requirement["impact_tag"], suite_id)
        if key in seen:
            raise ReleaseGateError("policy requirements must not be duplicated")
        seen.add(key)
        for field in ("minimum_exact_rate", "minimum_no_forbidden_execute_rate"):
            value = requirement[field]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
                raise ReleaseGateError(f"{field} must be between zero and one")
    protected = policy["protected_review_tags"]
    if not isinstance(protected, list) or protected != sorted(set(protected)) or not set(protected).issubset(IMPACT_TAGS):
        raise ReleaseGateError("protected_review_tags are invalid")
    kinds = policy["required_component_kinds"]
    if not isinstance(kinds, list) or kinds != sorted(set(kinds)) or not set(kinds).issubset(COMPONENT_KINDS):
        raise ReleaseGateError("required_component_kinds are invalid")
    boundaries = _exact(policy["boundaries"], BOUNDARY_KEYS, "policy boundaries")
    if any(boundaries[key] is not True for key in BOUNDARY_KEYS):
        raise ReleaseGateError("all release policy boundaries must be true")


def validate_plan(plan: dict[str, Any]) -> None:
    _exact(plan, {"plan_version", "plan_id", "suites", "boundary"}, "evidence plan")
    if plan["plan_version"] != PLAN_VERSION:
        raise ReleaseGateError(f"plan_version must be {PLAN_VERSION}")
    _text(plan["plan_id"], "plan_id", 120)
    _text(plan["boundary"], "plan boundary")
    suites = plan["suites"]
    if not isinstance(suites, list) or not 1 <= len(suites) <= MAX_SUITES:
        raise ReleaseGateError(f"plan suites must contain 1 to {MAX_SUITES} entries")
    ids: set[str] = set()
    for index, suite in enumerate(suites):
        suite = _exact(suite, {"suite_id", "path", "impact_tags", "clean_twin_count"}, f"suites[{index}]")
        suite_id = _text(suite["suite_id"], "plan suite_id", 160)
        if suite_id in ids:
            raise ReleaseGateError("plan suite ids must be unique")
        ids.add(suite_id)
        _text(suite["path"], "plan suite path", 300)
        tags = suite["impact_tags"]
        if not isinstance(tags, list) or tags != sorted(set(tags)) or not tags or not set(tags).issubset(IMPACT_TAGS):
            raise ReleaseGateError("plan suite impact_tags are invalid")
        if not isinstance(suite["clean_twin_count"], int) or suite["clean_twin_count"] < 1:
            raise ReleaseGateError("every release suite needs at least one declared clean twin")


def validate_approval(approval: dict[str, Any], release_id: str) -> None:
    _exact(
        approval,
        {
            "approval_version",
            "release_id",
            "status",
            "role",
            "recorded_at",
            "evidence_ref",
            "identity_verified",
            "limitations",
        },
        "approval record",
    )
    if approval["approval_version"] != APPROVAL_VERSION:
        raise ReleaseGateError(f"approval_version must be {APPROVAL_VERSION}")
    if approval["release_id"] != release_id or approval["status"] != "approved":
        raise ReleaseGateError("approval must approve the exact candidate release_id")
    if not _text(approval["role"], "approval role", 160).startswith("human:"):
        raise ReleaseGateError("approval role must identify a human role")
    _timestamp(approval["recorded_at"], "approval recorded_at")
    _text(approval["evidence_ref"], "approval evidence_ref", 300)
    if approval["identity_verified"] is not False:
        raise ReleaseGateError("this public approval contract cannot claim verified identity")
    limitations = approval["limitations"]
    if not isinstance(limitations, list) or not limitations:
        raise ReleaseGateError("approval limitations must be non-empty")
    for item in limitations:
        _text(item, "approval limitation", 400)


def run_impacted_suites(
    plan: dict[str, Any],
    plan_path: Path,
    impacted_tags: set[str],
    invoke: Callable[[dict], AdapterResult],
    adapter_kind: str,
) -> dict[str, dict[str, Any]]:
    validate_plan(plan)
    receipts: dict[str, dict[str, Any]] = {}
    for item in plan["suites"]:
        if not impacted_tags.intersection(item["impact_tags"]):
            continue
        suite_path = _safe_component_path(plan_path, item["path"])
        suite = load_suite(suite_path)
        if suite["suite_id"] != item["suite_id"]:
            raise ReleaseGateError(f"plan suite_id does not match {item['path']}")
        receipt, _ = evaluate_suite(suite, invoke, adapter_kind)
        receipt["release_gate"] = {
            "impact_tags": item["impact_tags"],
            "clean_twin_count": item["clean_twin_count"],
            "suite_source_sha256": digest(_load_bytes(suite_path)),
        }
        receipts[item["suite_id"]] = receipt
    return receipts


def assess_release(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    policy: dict[str, Any],
    plan: dict[str, Any],
    receipts: dict[str, dict[str, Any]],
    adapter_kind: str,
    approval: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_snapshot(baseline)
    validate_snapshot(candidate)
    validate_policy(policy)
    validate_plan(plan)
    change = diff_snapshots(baseline, candidate)
    impacted = set(change["impacted_tags"])
    blockers: list[str] = []
    evidence_rows = []

    if not change["changes"]:
        blockers.append("NO_RELEASE_CHANGE")
    mapped_tags = {item["impact_tag"] for item in policy["requirements"]}
    for tag in sorted(impacted - mapped_tags):
        blockers.append(f"UNMAPPED_CHANGE_TAG:{tag}")
    candidate_kinds = {item["kind"] for item in candidate["components"]}
    for kind in sorted(set(policy["required_component_kinds"]) - candidate_kinds):
        blockers.append(f"REQUIRED_COMPONENT_MISSING:{kind}")
    for row in change["changes"]:
        if row["state"] == "removed" and row["required_before"]:
            blockers.append(f"REQUIRED_COMPONENT_REMOVED:{row['component_id']}")

    plan_by_id = {item["suite_id"]: item for item in plan["suites"]}
    for requirement in policy["requirements"]:
        if requirement["impact_tag"] not in impacted:
            continue
        suite_id = requirement["suite_id"]
        planned = plan_by_id.get(suite_id)
        receipt = receipts.get(suite_id)
        if planned is None or requirement["impact_tag"] not in planned["impact_tags"]:
            blockers.append(f"SUITE_NOT_PLANNED:{requirement['impact_tag']}:{suite_id}")
            continue
        if receipt is None:
            blockers.append(f"SUITE_NOT_RUN:{suite_id}")
            continue
        metrics = receipt.get("metrics", {})
        exact_rate = metrics.get("exact_rate")
        no_forbidden = metrics.get("no_forbidden_execute_rate")
        passes = (
            isinstance(exact_rate, (int, float))
            and exact_rate >= requirement["minimum_exact_rate"]
            and isinstance(no_forbidden, (int, float))
            and no_forbidden >= requirement["minimum_no_forbidden_execute_rate"]
            and receipt.get("suite_id") == suite_id
            and receipt.get("release_gate", {}).get("clean_twin_count", 0) >= 1
        )
        evidence_rows.append(
            {
                "impact_tag": requirement["impact_tag"],
                "suite_id": suite_id,
                "suite_sha256": receipt.get("suite_sha256"),
                "exact_rate": exact_rate,
                "minimum_exact_rate": requirement["minimum_exact_rate"],
                "no_forbidden_execute_rate": no_forbidden,
                "minimum_no_forbidden_execute_rate": requirement[
                    "minimum_no_forbidden_execute_rate"
                ],
                "clean_twin_count": receipt.get("release_gate", {}).get("clean_twin_count"),
                "passes": passes,
            }
        )
        if not passes:
            blockers.append(f"SUITE_THRESHOLD_FAILED:{suite_id}:{requirement['impact_tag']}")

    review_tags = sorted(impacted.intersection(policy["protected_review_tags"]))
    approval_present = approval is not None
    if approval is not None:
        validate_approval(approval, candidate["release_id"])
    review_required = bool(review_tags) and not approval_present
    if adapter_kind == "mock":
        review_required = True
    status = "release_blocked" if blockers else "human_review_required" if review_required else "release_ready"
    reason_codes = sorted(set(blockers))
    if not blockers and review_required:
        if adapter_kind == "mock":
            reason_codes.append("MOCK_PROTOCOL_SELF_TEST_ONLY")
        if review_tags and not approval_present:
            reason_codes.append("PROTECTED_HUMAN_APPROVAL_REQUIRED")
    decision = {
        "decision_version": DECISION_VERSION,
        "release_id": candidate["release_id"],
        "agent_id": candidate["agent_id"],
        "effective_at": candidate["effective_at"],
        "status": status,
        "adapter_kind": adapter_kind,
        "baseline_snapshot_sha256": baseline["snapshot_sha256"],
        "candidate_snapshot_sha256": candidate["snapshot_sha256"],
        "diff_sha256": change["diff_sha256"],
        "policy_sha256": digest(policy),
        "plan_sha256": digest(plan),
        "impacted_tags": sorted(impacted),
        "evidence": sorted(evidence_rows, key=lambda item: (item["impact_tag"], item["suite_id"])),
        "review": {
            "required_tags": review_tags,
            "approval_record_present": approval_present,
            "approval_sha256": digest(approval) if approval else None,
            "approval_identity_verified": False,
        },
        "reason_codes": sorted(reason_codes),
        "boundary": {
            "structural_release_evidence_only": True,
            "mock_never_authorizes_release": True,
            "human_identity_not_verified": True,
            "not_production_safety_or_field_effectiveness": True,
            "not_certification_compliance_deployment_or_ato": True,
        },
        "decision_sha256": "",
    }
    decision["decision_sha256"] = digest(
        {key: value for key, value in decision.items() if key != "decision_sha256"}
    )
    return decision, change


def _stable_uuid(namespace: str, value: str) -> str:
    return str(uuid.uuid5(uuid.uuid5(uuid.NAMESPACE_URL, namespace), value))


def oscal_assessment_results(
    decision: dict[str, Any],
    assessment_plan_href: str = "https://example.invalid/aau/assessment-plan.json",
) -> dict[str, Any]:
    """Map one AAU release decision to an OSCAL Assessment Results subset.

    The serialization is intentionally non-certifying and retains the AAU
    boundary in remarks.  Consumers still need their own OSCAL assessment plan,
    catalog/profile binding, authorized assessor, and validation process.
    """

    parsed = urllib.parse.urlparse(assessment_plan_href)
    if parsed.scheme not in {"https", "urn"}:
        raise ReleaseGateError("assessment plan href must use HTTPS or URN")
    seed = decision["decision_sha256"]
    observation_ids: dict[str, str] = {}
    observations = []
    findings = []
    for index, row in enumerate(decision["evidence"], start=1):
        observation_id = _stable_uuid("aau-oscal-observation", f"{seed}:{index}")
        observation_ids[row["impact_tag"]] = observation_id
        observations.append(
            {
                "uuid": observation_id,
                "title": f"AAU release evidence for {row['impact_tag']}",
                "description": (
                    f"Suite {row['suite_id']} measured exact outcome and forbidden execution "
                    "against the declared public or synthetic release change."
                ),
                "methods": ["TEST"],
                "types": ["finding"],
                "collected": decision["effective_at"],
                "relevant-evidence": [
                    {
                        "description": "AAU suite receipt bound by SHA-256.",
                        "href": f"urn:sha256:{row['suite_sha256']}",
                    }
                ],
                "remarks": (
                    f"exact_rate={row['exact_rate']}; no_forbidden_execute_rate="
                    f"{row['no_forbidden_execute_rate']}; passes={str(row['passes']).lower()}."
                ),
            }
        )
        findings.append(
            {
                "uuid": _stable_uuid("aau-oscal-finding", f"{seed}:{index}"),
                "title": f"Release gate {row['impact_tag']}",
                "description": "AAU change-specific evidence result.",
                "target": {
                    "type": "objective-id",
                    "target-id": f"aau-{row['impact_tag']}",
                    "status": {"state": "satisfied" if row["passes"] else "not-satisfied"},
                },
                "related-observations": [{"observation-uuid": observation_id}],
            }
        )
    for index, code in enumerate(decision["reason_codes"], start=1):
        observation_id = _stable_uuid("aau-oscal-gap", f"{seed}:{index}:{code}")
        observations.append(
            {
                "uuid": observation_id,
                "title": f"AAU visible release gap: {code}",
                "description": "A fail-closed release-gate reason remains unresolved.",
                "methods": ["EXAMINE"],
                "types": ["finding"],
                "collected": decision["effective_at"],
                "remarks": code,
            }
        )
    result_uuid = _stable_uuid("aau-oscal-result", seed)
    return {
        "assessment-results": {
            "uuid": _stable_uuid("aau-oscal-document", seed),
            "metadata": {
                "title": f"AAU non-certifying agent release evidence: {decision['release_id']}",
                "last-modified": decision["effective_at"],
                "version": "1.0",
                "oscal-version": OSCAL_VERSION,
                "remarks": (
                    "Experimental AAU mapping. Structural output is not an OSCAL validation, "
                    "control assessment, compliance finding, FedRAMP authorization, or ATO."
                ),
            },
            "import-ap": {"href": assessment_plan_href},
            "results": [
                {
                    "uuid": result_uuid,
                    "title": "AAU agent release gate result",
                    "description": "Change-specific agent evaluation with visible gaps.",
                    "start": decision["effective_at"],
                    "end": decision["effective_at"],
                    "reviewed-controls": {"control-selections": [{"include-all": {}}]},
                    "observations": observations,
                    "findings": findings,
                    "remarks": (
                        f"AAU status={decision['status']}; decision_sha256={seed}. "
                        "The accountable organization retains every authorization decision."
                    ),
                }
            ],
        }
    }


def _pack_readme(decision: dict[str, Any]) -> bytes:
    return (
        "# AAU Agent Release Gate evidence pack\n\n"
        f"Derived status: **{decision['status']}**. This status covers only the declared public "
        "or synthetic components, mapped suites, thresholds, and approval-record structure. "
        "It is not deployment authority, production safety, verified human identity, compliance, "
        "certification, FedRAMP authorization, or an Authority to Operate. Verify the complete "
        "pack before using any individual file.\n"
    ).encode()


def pack_payloads(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    policy: dict[str, Any],
    plan: dict[str, Any],
    receipts: dict[str, dict[str, Any]],
    adapter_kind: str,
    approval: dict[str, Any] | None,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    decision, change = assess_release(
        baseline, candidate, policy, plan, receipts, adapter_kind, approval
    )
    decision_bytes = rendered(decision)
    statement = {
        "_type": STATEMENT_TYPE,
        "subject": [
            {"name": "release-decision.json", "digest": {"sha256": digest(decision_bytes)}}
        ],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "baselineSnapshotSha256": baseline["snapshot_sha256"],
            "candidateSnapshotSha256": candidate["snapshot_sha256"],
            "diffSha256": change["diff_sha256"],
            "policySha256": digest(policy),
            "planSha256": digest(plan),
            "signatureStatus": "unsigned-local-statement",
        },
    }
    payloads: dict[str, bytes] = {
        "README.md": _pack_readme(decision),
        "baseline-snapshot.json": rendered(baseline),
        "candidate-snapshot.json": rendered(candidate),
        "release-diff.json": rendered(change),
        "release-policy.json": rendered(policy),
        "evidence-plan.json": rendered(plan),
        "release-decision.json": decision_bytes,
        "assessment-results.oscal.json": rendered(oscal_assessment_results(decision)),
        "provenance.intoto.json": rendered(statement),
    }
    if approval is not None:
        payloads["approval.json"] = rendered(approval)
    for suite_id, receipt in sorted(receipts.items()):
        payloads[f"receipts/{suite_id}.json"] = rendered(receipt)
    files = [
        {"path": name, "bytes": len(data), "sha256": digest(data)}
        for name, data in sorted(payloads.items())
    ]
    payloads["manifest.json"] = rendered(
        {"manifest_version": PACK_VERSION, "files": files}
    )
    return payloads, decision


def build_pack(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    policy: dict[str, Any],
    plan: dict[str, Any],
    receipts: dict[str, dict[str, Any]],
    adapter_kind: str,
    approval: dict[str, Any] | None,
    out: Path,
) -> dict[str, Any]:
    if out.exists() or out.is_symlink():
        raise ReleaseGateError(f"refusing to overwrite release pack: {out}")
    payloads, decision = pack_payloads(
        baseline, candidate, policy, plan, receipts, adapter_kind, approval
    )
    out.mkdir(parents=True)
    for name, payload in payloads.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return decision


def verify_pack(pack: Path) -> dict[str, Any]:
    if pack.is_symlink() or not pack.is_dir():
        raise ReleaseGateError(f"invalid release pack: {pack}")
    manifest = load_json(pack / "manifest.json")
    if manifest.get("manifest_version") != PACK_VERSION or not isinstance(manifest.get("files"), list):
        raise ReleaseGateError("release manifest is invalid")
    entries = manifest["files"]
    declared: set[str] = set()
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
            raise ReleaseGateError("release manifest entry is invalid")
        name = _text(item["path"], "manifest path", 300)
        pure = Path(name)
        if pure.is_absolute() or ".." in pure.parts or name in declared:
            raise ReleaseGateError("release manifest path is unsafe or duplicated")
        declared.add(name)
        if not isinstance(item["bytes"], int) or item["bytes"] < 0:
            raise ReleaseGateError("release manifest byte count is invalid")
        _sha(item["sha256"], "release manifest sha256")
        target = pack / pure
        if target.is_symlink() or not target.is_file():
            raise ReleaseGateError(f"missing or symbolic-link pack file: {name}")
        data = _load_bytes(target, MAX_COMPONENT_BYTES)
        if len(data) != item["bytes"] or digest(data) != item["sha256"]:
            raise ReleaseGateError(f"release pack integrity mismatch: {name}")
    actual = {
        path.relative_to(pack).as_posix()
        for path in pack.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if actual != declared | {"manifest.json"}:
        raise ReleaseGateError("release pack has unmanifested, missing, or symbolic-link files")
    required = {
        "README.md",
        "baseline-snapshot.json",
        "candidate-snapshot.json",
        "release-diff.json",
        "release-policy.json",
        "evidence-plan.json",
        "release-decision.json",
        "assessment-results.oscal.json",
        "provenance.intoto.json",
    }
    if not required.issubset(declared):
        raise ReleaseGateError("release pack is missing required evidence files")
    baseline = load_json(pack / "baseline-snapshot.json")
    candidate = load_json(pack / "candidate-snapshot.json")
    policy = load_json(pack / "release-policy.json")
    plan = load_json(pack / "evidence-plan.json")
    approval = load_json(pack / "approval.json") if "approval.json" in declared else None
    receipt_names = sorted(name for name in declared if name.startswith("receipts/") and name.endswith(".json"))
    receipts = {
        Path(name).stem: load_json(pack / name)
        for name in receipt_names
    }
    stored = load_json(pack / "release-decision.json")
    adapter_kind = stored.get("adapter_kind")
    expected, change = assess_release(
        baseline, candidate, policy, plan, receipts, adapter_kind, approval
    )
    if stored != expected or load_json(pack / "release-diff.json") != change:
        raise ReleaseGateError("release decision or diff does not recompute")
    if load_json(pack / "assessment-results.oscal.json") != oscal_assessment_results(expected):
        raise ReleaseGateError("OSCAL assessment mapping does not recompute")
    statement = load_json(pack / "provenance.intoto.json")
    if statement.get("_type") != STATEMENT_TYPE or statement.get("predicateType") != PREDICATE_TYPE:
        raise ReleaseGateError("release provenance statement is invalid")
    if statement.get("subject") != [
        {
            "name": "release-decision.json",
            "digest": {"sha256": digest(_load_bytes(pack / "release-decision.json"))},
        }
    ]:
        raise ReleaseGateError("release provenance subject does not bind decision bytes")
    return expected


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="aau release",
        description="Capture, test, and verify change-specific agent release evidence.",
    )
    sub = root.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("capture", help="hash every declared release component")
    capture.add_argument("manifest", type=Path)
    capture.add_argument("--out", type=Path, required=True)
    compare = sub.add_parser("diff", help="compare two captured release snapshots")
    compare.add_argument("baseline", type=Path)
    compare.add_argument("candidate", type=Path)
    compare.add_argument("--out", type=Path, required=True)
    assess = sub.add_parser("assess", help="run impacted suites and build a release evidence pack")
    assess.add_argument("baseline_manifest", type=Path)
    assess.add_argument("candidate_manifest", type=Path)
    assess.add_argument("policy", type=Path)
    assess.add_argument("plan", type=Path)
    adapter = assess.add_mutually_exclusive_group(required=True)
    adapter.add_argument("--command", dest="adapter_command")
    adapter.add_argument("--endpoint")
    adapter.add_argument("--mock", action="store_true")
    assess.add_argument("--timeout", type=float, default=30.0)
    assess.add_argument("--approval", type=Path)
    assess.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify", help="recompute a complete release evidence pack")
    verify.add_argument("pack", type=Path)
    oscal = sub.add_parser("export-oscal", help="export a non-certifying OSCAL Assessment Results mapping")
    oscal.add_argument("decision", type=Path)
    oscal.add_argument("--assessment-plan", default="https://example.invalid/aau/assessment-plan.json")
    oscal.add_argument("--out", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "capture":
            snapshot = capture_manifest(args.manifest)
            write_json(snapshot, args.out)
            print(f"OK: captured {len(snapshot['components'])} release components in {args.out}.")
        elif args.command == "diff":
            result = diff_snapshots(load_json(args.baseline), load_json(args.candidate))
            write_json(result, args.out)
            print(f"OK: {len(result['changes'])} changed components affect {len(result['impacted_tags'])} tags.")
        elif args.command == "assess":
            baseline = capture_manifest(args.baseline_manifest)
            candidate = capture_manifest(args.candidate_manifest)
            policy = load_json(args.policy)
            plan = load_json(args.plan)
            validate_policy(policy)
            change = diff_snapshots(baseline, candidate)
            if args.adapter_command:
                invoke = command_adapter(args.adapter_command, args.timeout)
                adapter_kind = "command"
            elif args.endpoint:
                invoke = endpoint_adapter(args.endpoint, args.timeout)
                adapter_kind = "endpoint"
            else:
                invoke = mock_adapter
                adapter_kind = "mock"
            receipts = run_impacted_suites(
                plan, args.plan, set(change["impacted_tags"]), invoke, adapter_kind
            )
            approval = load_json(args.approval) if args.approval else None
            decision = build_pack(
                baseline,
                candidate,
                policy,
                plan,
                receipts,
                adapter_kind,
                approval,
                args.out,
            )
            print(f"OK: {decision['status']} evidence pack written to {args.out}.")
        elif args.command == "verify":
            decision = verify_pack(args.pack)
            print(f"OK: release pack verified with status {decision['status']}.")
        else:
            decision = load_json(args.decision)
            _sha(decision.get("decision_sha256"), "decision_sha256")
            write_json(oscal_assessment_results(decision, args.assessment_plan), args.out)
            print(f"OK: non-certifying OSCAL Assessment Results mapping written to {args.out}.")
        return 0
    except (ReleaseGateError, ValueError) as exc:
        print(f"aau release: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
