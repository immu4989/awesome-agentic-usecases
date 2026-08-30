"""Agent Capability & Authority Bill of Materials (AABOM).

This module inventories the operational authority around an agent, validates
cross-references, identifies authority widening between releases, and emits a
conservative CycloneDX 1.7 projection.  It never grants authority or establishes
identity, compliance, certification, safety, or deployment approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


BOM_VERSION = "aau-agent-capability-bom/1.0"
DIFF_VERSION = "aau-agent-capability-diff/1.0"
REVIEW_VERSION = "aau-agent-capability-review/1.0"
PACK_VERSION = "aau-agent-capability-pack/1.0"
OBSERVATION_VERSION = "aau-agent-authority-observation/1.0"
REDUCTION_PLAN_VERSION = "aau-agent-authority-reduction-plan/1.0"
CONFORMANCE_SUITE_VERSION = "aau-agent-authority-conformance-suite/1.0"
CONFORMANCE_RECEIPT_VERSION = "aau-agent-authority-conformance-receipt/1.0"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = (
    "https://immu4989.github.io/awesome-agentic-usecases/"
    "predicates/agent-capability-bom/v1"
)
MAX_JSON_BYTES = 2_000_000
MAX_ITEMS = 200
HEX = set("0123456789abcdef")
SIDE_EFFECT_RANK = {"read": 0, "prepare": 1, "write": 2, "irreversible": 3}
PROTOCOLS = {"MCP", "A2A", "HTTP", "CLI", "other"}
EVIDENCE_KINDS = {
    "evaluation_receipt",
    "release_pack",
    "incident_regression",
    "reproduction",
    "monitoring",
    "rollback_test",
    "other",
}
OBSERVATION_DECISIONS = {"allowed", "blocked", "error"}
SHARING_KEYS = {
    "public_or_synthetic_only",
    "contains_personal_data",
    "contains_credentials",
    "contains_nonpublic_configuration",
    "contains_controlled_information",
}


class AgentBomError(ValueError):
    """Raised when an AABOM violates the strict public contract."""


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def rendered(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(payload).hexdigest()


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise AgentBomError(f"{label} fields differ from the 1.0 contract")
    return value


def _text(value: Any, label: str, limit: int = 300) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise AgentBomError(
            f"{label} must be non-empty text of at most {limit} characters"
        )
    return value


def _string_list(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or len(value) > MAX_ITEMS
        or len(value) != len(set(value))
    ):
        raise AgentBomError(f"{label} must be a unique bounded string list")
    for index, item in enumerate(value):
        _text(item, f"{label}[{index}]", 200)
    return value


def _timestamp(value: Any, label: str) -> datetime:
    value = _text(value, label, 40)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AgentBomError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise AgentBomError(f"{label} must include a timezone")
    return parsed


def _sha(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in HEX for char in value)
    ):
        raise AgentBomError(f"{label} must be a lowercase SHA-256 digest")
    return value


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AgentBomError(f"invalid or symbolic-link file: {path}")
    if path.stat().st_size > MAX_JSON_BYTES:
        raise AgentBomError(f"file exceeds {MAX_JSON_BYTES} bytes: {path}")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AgentBomError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AgentBomError(f"expected one JSON object in {path}")
    return value


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise AgentBomError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(rendered(value))


def validate_bom(bom: dict[str, Any]) -> None:
    _exact(
        bom,
        {
            "bom_version",
            "bom_id",
            "agent_id",
            "release_id",
            "generated_at",
            "generation_context",
            "accountability",
            "models",
            "tools",
            "authorities",
            "data_routes",
            "controls",
            "evidence",
            "sharing",
        },
        "agent capability BOM",
    )
    if bom["bom_version"] != BOM_VERSION:
        raise AgentBomError(f"bom_version must be {BOM_VERSION}")
    for key in ("bom_id", "agent_id", "release_id"):
        _text(bom[key], key, 160)
    _timestamp(bom["generated_at"], "generated_at")
    if bom["generation_context"] not in {"design", "source", "build", "deployed"}:
        raise AgentBomError("generation_context is unsupported")

    accountability = _exact(
        bom["accountability"],
        {"owner_role", "human_release_authority_preserved", "production_identity_verified"},
        "accountability",
    )
    _text(accountability["owner_role"], "accountability.owner_role", 160)
    if accountability["human_release_authority_preserved"] is not True:
        raise AgentBomError("human release authority must remain preserved")
    if accountability["production_identity_verified"] is not False:
        raise AgentBomError(
            "the public profile cannot claim verified production identity"
        )

    models = bom["models"]
    if not isinstance(models, list) or not 1 <= len(models) <= MAX_ITEMS:
        raise AgentBomError("models must contain 1 to 200 entries")
    component_ids: set[str] = set()
    for index, model in enumerate(models):
        model = _exact(
            model,
            {"component_id", "provider", "model_ref", "digest", "role"},
            f"models[{index}]",
        )
        component_id = _text(model["component_id"], f"models[{index}].component_id", 120)
        if component_id in component_ids:
            raise AgentBomError(f"duplicate component_id: {component_id}")
        component_ids.add(component_id)
        for key in ("provider", "model_ref", "role"):
            _text(model[key], f"models[{index}].{key}", 200)
        _sha(model["digest"], f"models[{index}].digest")

    tools = bom["tools"]
    if not isinstance(tools, list) or not 1 <= len(tools) <= MAX_ITEMS:
        raise AgentBomError("tools must contain 1 to 200 entries")
    tool_map: dict[str, dict[str, Any]] = {}
    for index, tool in enumerate(tools):
        tool = _exact(
            tool,
            {"component_id", "protocol", "operations", "side_effect", "resource_scopes"},
            f"tools[{index}]",
        )
        component_id = _text(tool["component_id"], f"tools[{index}].component_id", 120)
        if component_id in component_ids:
            raise AgentBomError(f"duplicate component_id: {component_id}")
        component_ids.add(component_id)
        tool_map[component_id] = tool
        if tool["protocol"] not in PROTOCOLS:
            raise AgentBomError(f"tools[{index}].protocol is unsupported")
        _string_list(tool["operations"], f"tools[{index}].operations")
        _string_list(tool["resource_scopes"], f"tools[{index}].resource_scopes")
        if tool["side_effect"] not in SIDE_EFFECT_RANK:
            raise AgentBomError(f"tools[{index}].side_effect is unsupported")

    authorities = bom["authorities"]
    if not isinstance(authorities, list) or not 1 <= len(authorities) <= MAX_ITEMS:
        raise AgentBomError("authorities must contain 1 to 200 entries")
    authority_ids: set[str] = set()
    for index, authority in enumerate(authorities):
        authority = _exact(
            authority,
            {
                "authority_id",
                "subject",
                "tool_ids",
                "operations",
                "resource_scopes",
                "delegation_depth",
                "not_before",
                "expires_at",
                "revocation_channel",
                "human_approval_required",
            },
            f"authorities[{index}]",
        )
        authority_id = _text(
            authority["authority_id"], f"authorities[{index}].authority_id", 120
        )
        if authority_id in authority_ids:
            raise AgentBomError(f"duplicate authority_id: {authority_id}")
        authority_ids.add(authority_id)
        _text(authority["subject"], f"authorities[{index}].subject", 200)
        tool_ids = _string_list(authority["tool_ids"], f"authorities[{index}].tool_ids")
        operations = set(
            _string_list(authority["operations"], f"authorities[{index}].operations")
        )
        scopes = set(
            _string_list(authority["resource_scopes"], f"authorities[{index}].resource_scopes")
        )
        unknown = set(tool_ids) - set(tool_map)
        if unknown:
            raise AgentBomError(f"authority {authority_id} references unknown tools: {sorted(unknown)}")
        allowed_operations = {item for tool_id in tool_ids for item in tool_map[tool_id]["operations"]}
        allowed_scopes = {item for tool_id in tool_ids for item in tool_map[tool_id]["resource_scopes"]}
        if not operations.issubset(allowed_operations):
            raise AgentBomError(f"authority {authority_id} exceeds declared tool operations")
        if not scopes.issubset(allowed_scopes):
            raise AgentBomError(f"authority {authority_id} exceeds declared resource scopes")
        depth = authority["delegation_depth"]
        if not isinstance(depth, int) or isinstance(depth, bool) or not 0 <= depth <= 20:
            raise AgentBomError(f"authorities[{index}].delegation_depth must be 0 to 20")
        starts = _timestamp(authority["not_before"], f"authorities[{index}].not_before")
        expires = _timestamp(authority["expires_at"], f"authorities[{index}].expires_at")
        if expires <= starts:
            raise AgentBomError(f"authority {authority_id} must expire after it begins")
        _text(authority["revocation_channel"], f"authorities[{index}].revocation_channel", 300)
        if not isinstance(authority["human_approval_required"], bool):
            raise AgentBomError(f"authorities[{index}].human_approval_required must be boolean")

    routes = bom["data_routes"]
    if not isinstance(routes, list) or len(routes) > MAX_ITEMS:
        raise AgentBomError("data_routes must contain 0 to 200 entries")
    route_ids: set[str] = set()
    for index, route in enumerate(routes):
        route = _exact(
            route,
            {"route_id", "source", "destination", "data_classes", "egress_allowed", "retention_days"},
            f"data_routes[{index}]",
        )
        route_id = _text(route["route_id"], f"data_routes[{index}].route_id", 120)
        if route_id in route_ids:
            raise AgentBomError(f"duplicate route_id: {route_id}")
        route_ids.add(route_id)
        _text(route["source"], f"data_routes[{index}].source", 200)
        _text(route["destination"], f"data_routes[{index}].destination", 200)
        _string_list(route["data_classes"], f"data_routes[{index}].data_classes")
        if not isinstance(route["egress_allowed"], bool):
            raise AgentBomError(f"data_routes[{index}].egress_allowed must be boolean")
        days = route["retention_days"]
        if not isinstance(days, int) or isinstance(days, bool) or not 0 <= days <= 36500:
            raise AgentBomError(f"data_routes[{index}].retention_days is invalid")

    controls = _exact(
        bom["controls"],
        {"monitor_ids", "safe_stop", "restart_authority", "rollback"},
        "controls",
    )
    _string_list(controls["monitor_ids"], "controls.monitor_ids")
    for key in ("safe_stop", "restart_authority", "rollback"):
        _text(controls[key], f"controls.{key}", 300)

    evidence = bom["evidence"]
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= MAX_ITEMS:
        raise AgentBomError("evidence must contain 1 to 200 entries")
    evidence_ids: set[str] = set()
    for index, item in enumerate(evidence):
        item = _exact(item, {"evidence_id", "kind", "sha256", "uri"}, f"evidence[{index}]")
        evidence_id = _text(item["evidence_id"], f"evidence[{index}].evidence_id", 120)
        if evidence_id in evidence_ids:
            raise AgentBomError(f"duplicate evidence_id: {evidence_id}")
        evidence_ids.add(evidence_id)
        if item["kind"] not in EVIDENCE_KINDS:
            raise AgentBomError(f"evidence[{index}].kind is unsupported")
        _sha(item["sha256"], f"evidence[{index}].sha256")
        uri = _text(item["uri"], f"evidence[{index}].uri", 500)
        if uri.startswith(("file:", "/")) or ".." in Path(uri).parts:
            raise AgentBomError(f"evidence[{index}].uri must be public-safe and relative or HTTPS")

    sharing = _exact(bom["sharing"], SHARING_KEYS, "sharing")
    if sharing["public_or_synthetic_only"] is not True:
        raise AgentBomError("sharing.public_or_synthetic_only must be true")
    for key in SHARING_KEYS - {"public_or_synthetic_only"}:
        if sharing[key] is not False:
            raise AgentBomError(f"sharing.{key} must be false")


def _by_id(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {row[key]: row for row in rows}


def diff_boms(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    validate_bom(before)
    validate_bom(after)
    if before["agent_id"] != after["agent_id"]:
        raise AgentBomError("cannot diff BOMs for different agents")
    findings: list[dict[str, str]] = []

    def add(code: str, subject: str, detail: str, severity: str = "review") -> None:
        findings.append({"code": code, "subject": subject, "severity": severity, "detail": detail})

    old_tools = _by_id(before["tools"], "component_id")
    new_tools = _by_id(after["tools"], "component_id")
    for tool_id in sorted(set(new_tools) - set(old_tools)):
        add("TOOL_ADDED", tool_id, "A callable tool entered the deployment inventory.")
    for tool_id in sorted(set(old_tools) & set(new_tools)):
        old, new = old_tools[tool_id], new_tools[tool_id]
        if SIDE_EFFECT_RANK[new["side_effect"]] > SIDE_EFFECT_RANK[old["side_effect"]]:
            add("TOOL_SIDE_EFFECT_INCREASED", tool_id, f"{old['side_effect']} → {new['side_effect']}")
        for operation in sorted(set(new["operations"]) - set(old["operations"])):
            add("TOOL_OPERATION_ADDED", tool_id, operation)
        for scope in sorted(set(new["resource_scopes"]) - set(old["resource_scopes"])):
            add("TOOL_SCOPE_ADDED", tool_id, scope)

    old_auth = _by_id(before["authorities"], "authority_id")
    new_auth = _by_id(after["authorities"], "authority_id")
    for authority_id in sorted(set(new_auth) - set(old_auth)):
        add("AUTHORITY_ADDED", authority_id, "A new authority lease entered the inventory.")
    for authority_id in sorted(set(old_auth) & set(new_auth)):
        old, new = old_auth[authority_id], new_auth[authority_id]
        for operation in sorted(set(new["operations"]) - set(old["operations"])):
            add("AUTHORITY_OPERATION_ADDED", authority_id, operation)
        for scope in sorted(set(new["resource_scopes"]) - set(old["resource_scopes"])):
            add("AUTHORITY_SCOPE_ADDED", authority_id, scope)
        if new["delegation_depth"] > old["delegation_depth"]:
            add("DELEGATION_DEPTH_INCREASED", authority_id, f"{old['delegation_depth']} → {new['delegation_depth']}")
        old_window = _timestamp(old["expires_at"], "expires_at") - _timestamp(
            old["not_before"], "not_before"
        )
        new_window = _timestamp(new["expires_at"], "expires_at") - _timestamp(
            new["not_before"], "not_before"
        )
        if new_window > old_window:
            add(
                "AUTHORITY_WINDOW_EXTENDED",
                authority_id,
                f"{old_window.total_seconds():g}s → {new_window.total_seconds():g}s",
            )
        if old["human_approval_required"] and not new["human_approval_required"]:
            add("HUMAN_APPROVAL_REMOVED", authority_id, "Protected human approval was removed.", "block")

    old_routes = _by_id(before["data_routes"], "route_id")
    new_routes = _by_id(after["data_routes"], "route_id")
    for route_id in sorted(set(new_routes) - set(old_routes)):
        add("DATA_ROUTE_ADDED", route_id, "A new data route entered the inventory.")
    for route_id in sorted(set(old_routes) & set(new_routes)):
        old, new = old_routes[route_id], new_routes[route_id]
        if not old["egress_allowed"] and new["egress_allowed"]:
            add("EGRESS_ENABLED", route_id, new["destination"])
        if old["destination"] != new["destination"]:
            add("DESTINATION_CHANGED", route_id, f"{old['destination']} → {new['destination']}")
        for data_class in sorted(set(new["data_classes"]) - set(old["data_classes"])):
            add("DATA_CLASS_ADDED", route_id, data_class)

    if before["controls"] != after["controls"]:
        add("CONTROL_PLANE_CHANGED", "controls", "Monitor, stop, restart, or rollback declarations changed.")
    blocking = sum(row["severity"] == "block" for row in findings)
    status = "blocking_boundary_loss" if blocking else ("review_required" if findings else "unchanged")
    result = {
        "diff_version": DIFF_VERSION,
        "agent_id": before["agent_id"],
        "before_release_id": before["release_id"],
        "after_release_id": after["release_id"],
        "status": status,
        "finding_count": len(findings),
        "blocking_count": blocking,
        "findings": findings,
        "boundary": {
            "inventory_not_authorization": True,
            "human_review_required_for_widening": True,
            "no_safety_or_compliance_claim": True,
        },
    }
    return result


def review_bom(bom: dict[str, Any]) -> dict[str, Any]:
    validate_bom(bom)
    tool_map = _by_id(bom["tools"], "component_id")
    findings: list[dict[str, str]] = []
    for authority in bom["authorities"]:
        consequential = any(
            SIDE_EFFECT_RANK[tool_map[tool_id]["side_effect"]] >= SIDE_EFFECT_RANK["write"]
            for tool_id in authority["tool_ids"]
        )
        if consequential and not authority["human_approval_required"]:
            findings.append(
                {
                    "code": "CONSEQUENTIAL_AUTHORITY_WITHOUT_HUMAN_APPROVAL",
                    "subject": authority["authority_id"],
                    "severity": "block",
                }
            )
    status = "boundary_violation" if findings else "human_review_required"
    return {
        "review_version": REVIEW_VERSION,
        "bom_id": bom["bom_id"],
        "agent_id": bom["agent_id"],
        "release_id": bom["release_id"],
        "status": status,
        "inventory": {
            "models": len(bom["models"]),
            "tools": len(bom["tools"]),
            "authorities": len(bom["authorities"]),
            "data_routes": len(bom["data_routes"]),
            "evidence_bindings": len(bom["evidence"]),
        },
        "findings": findings,
        "reason_codes": ["OWNER_REVIEW_REQUIRED"] + [row["code"] for row in findings],
        "boundary": {
            "valid_inventory_not_live_authorization": True,
            "production_identity_not_verified": True,
            "not_deployment_approval_or_certification": True,
        },
    }


def to_cyclonedx(bom: dict[str, Any]) -> dict[str, Any]:
    """Return a conservative CycloneDX 1.7 JSON projection.

    Agent-only fields are namespaced properties so ordinary CycloneDX consumers
    can preserve them without pretending they are standardized CycloneDX fields.
    """
    validate_bom(bom)
    components: list[dict[str, Any]] = []
    for model in bom["models"]:
        components.append(
            {
                "type": "machine-learning-model",
                "bom-ref": model["component_id"],
                "name": model["model_ref"],
                "version": bom["release_id"],
                "supplier": {"name": model["provider"]},
                "hashes": [{"alg": "SHA-256", "content": model["digest"]}],
                "properties": [{"name": "aau:agent:model:role", "value": model["role"]}],
            }
        )
    for tool in bom["tools"]:
        properties = [
            {"name": "aau:agent:tool:protocol", "value": tool["protocol"]},
            {"name": "aau:agent:tool:side-effect", "value": tool["side_effect"]},
            {"name": "aau:agent:tool:operations", "value": ",".join(sorted(tool["operations"]))},
            {"name": "aau:agent:tool:resource-scopes", "value": ",".join(sorted(tool["resource_scopes"]))},
        ]
        components.append(
            {
                "type": "application",
                "bom-ref": tool["component_id"],
                "name": tool["component_id"],
                "version": bom["release_id"],
                "properties": properties,
            }
        )
    root_ref = f"agent:{bom['agent_id']}"
    serial = uuid.uuid5(uuid.NAMESPACE_URL, f"{BOM_VERSION}:{digest(bom)}")
    return {
        "$schema": "https://cyclonedx.org/schema/bom-1.7.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "timestamp": bom["generated_at"],
            "component": {
                "type": "application",
                "bom-ref": root_ref,
                "name": bom["agent_id"],
                "version": bom["release_id"],
                "properties": [
                    {"name": "aau:agent:bom-version", "value": BOM_VERSION},
                    {"name": "aau:agent:owner-role", "value": bom["accountability"]["owner_role"]},
                    {"name": "aau:agent:generation-context", "value": bom["generation_context"]},
                ],
            },
        },
        "components": components,
        "dependencies": [
            {"ref": root_ref, "dependsOn": sorted(item["bom-ref"] for item in components)}
        ],
        "properties": [
            {"name": "aau:agent:authority-count", "value": str(len(bom["authorities"]))},
            {"name": "aau:agent:data-route-count", "value": str(len(bom["data_routes"]))},
            {"name": "aau:agent:evidence-binding-count", "value": str(len(bom["evidence"]))},
            {"name": "aau:agent:inventory-is-not-authorization", "value": "true"},
        ],
    }


def build_pack(bom: dict[str, Any], out: Path) -> dict[str, Any]:
    validate_bom(bom)
    if out.exists() or out.is_symlink():
        raise AgentBomError(f"refusing to overwrite: {out}")
    out.mkdir(parents=True)
    review = review_bom(bom)
    artifacts = {
        "agent-capability-bom.json": bom,
        "authority-review.json": review,
        "cyclonedx-1.7.json": to_cyclonedx(bom),
    }
    for name, value in artifacts.items():
        (out / name).write_bytes(rendered(value))
    statement = {
        "_type": STATEMENT_TYPE,
        "subject": [
            {"name": name, "digest": {"sha256": digest((out / name).read_bytes())}}
            for name in sorted(artifacts)
        ],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "pack_version": PACK_VERSION,
            "bom_id": bom["bom_id"],
            "status": review["status"],
            "unsigned": True,
            "boundary": "Integrity binding only; not identity, authorization, or deployment approval.",
        },
    }
    (out / "provenance.intoto.json").write_bytes(rendered(statement))
    names = sorted([*artifacts, "provenance.intoto.json"])
    manifest = {
        "pack_version": PACK_VERSION,
        "bom_id": bom["bom_id"],
        "files": [
            {
                "path": name,
                "bytes": (out / name).stat().st_size,
                "sha256": digest((out / name).read_bytes()),
            }
            for name in names
        ],
    }
    (out / "manifest.json").write_bytes(rendered(manifest))
    return review


def verify_pack(pack: Path) -> dict[str, Any]:
    if pack.is_symlink() or not pack.is_dir():
        raise AgentBomError(f"invalid or symbolic-link pack: {pack}")
    manifest = load_json(pack / "manifest.json")
    _exact(manifest, {"pack_version", "bom_id", "files"}, "pack manifest")
    if manifest["pack_version"] != PACK_VERSION:
        raise AgentBomError(f"pack_version must be {PACK_VERSION}")
    expected = {row["path"] for row in manifest["files"]} | {"manifest.json"}
    actual = {path.name for path in pack.iterdir()}
    if actual != expected:
        raise AgentBomError("pack file set differs from its manifest")
    for row in manifest["files"]:
        _exact(row, {"path", "bytes", "sha256"}, "manifest file")
        if Path(row["path"]).name != row["path"]:
            raise AgentBomError("manifest paths must be plain filenames")
        path = pack / row["path"]
        if path.is_symlink() or not path.is_file():
            raise AgentBomError(f"invalid pack artifact: {row['path']}")
        payload = path.read_bytes()
        if len(payload) != row["bytes"] or digest(payload) != row["sha256"]:
            raise AgentBomError(f"integrity mismatch: {row['path']}")
    bom = load_json(pack / "agent-capability-bom.json")
    review = load_json(pack / "authority-review.json")
    if review != review_bom(bom):
        raise AgentBomError("authority review does not recompute")
    if load_json(pack / "cyclonedx-1.7.json") != to_cyclonedx(bom):
        raise AgentBomError("CycloneDX projection does not recompute")
    statement = load_json(pack / "provenance.intoto.json")
    if statement["predicateType"] != PREDICATE_TYPE or statement["predicate"]["unsigned"] is not True:
        raise AgentBomError("provenance boundary is invalid")
    subjects = {row["name"]: row["digest"]["sha256"] for row in statement["subject"]}
    for name in ("agent-capability-bom.json", "authority-review.json", "cyclonedx-1.7.json"):
        if subjects.get(name) != digest((pack / name).read_bytes()):
            raise AgentBomError(f"provenance subject mismatch: {name}")
    return review


def validate_observation(observation: dict[str, Any], bom: dict[str, Any]) -> None:
    """Validate a privacy-bounded authority-use observation against one AABOM."""
    validate_bom(bom)
    _exact(
        observation,
        {
            "observation_version",
            "observation_id",
            "agent_id",
            "release_id",
            "window",
            "events",
            "sharing",
        },
        "authority observation",
    )
    if observation["observation_version"] != OBSERVATION_VERSION:
        raise AgentBomError(f"observation_version must be {OBSERVATION_VERSION}")
    _text(observation["observation_id"], "observation_id", 160)
    if observation["agent_id"] != bom["agent_id"]:
        raise AgentBomError("observation agent_id does not match the BOM")
    if observation["release_id"] != bom["release_id"]:
        raise AgentBomError("observation release_id does not match the BOM")
    window = _exact(
        observation["window"],
        {
            "starts_at",
            "ends_at",
            "environment",
            "scenario_set_sha256",
            "scenario_count",
            "run_count",
            "coverage_basis",
        },
        "observation window",
    )
    starts = _timestamp(window["starts_at"], "window.starts_at")
    ends = _timestamp(window["ends_at"], "window.ends_at")
    if ends <= starts:
        raise AgentBomError("observation window must end after it starts")
    if window["environment"] not in {"public", "synthetic", "public_synthetic"}:
        raise AgentBomError("observation environment is unsupported")
    _sha(window["scenario_set_sha256"], "window.scenario_set_sha256")
    if window["coverage_basis"] not in {
        "reviewed_synthetic",
        "public_replay",
        "authorized_aggregate",
    }:
        raise AgentBomError("observation coverage_basis is unsupported")
    for key in ("scenario_count", "run_count"):
        value = window[key]
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 100000:
            raise AgentBomError(f"window.{key} must be an integer from 1 to 100000")

    events = observation["events"]
    if not isinstance(events, list) or not 1 <= len(events) <= 100000:
        raise AgentBomError("events must contain 1 to 100000 entries")
    tools = _by_id(bom["tools"], "component_id")
    authorities = _by_id(bom["authorities"], "authority_id")
    event_ids: set[str] = set()
    run_sequences: dict[str, set[int]] = {}
    run_ids: set[str] = set()
    scenario_ids: set[str] = set()
    for index, event in enumerate(events):
        event = _exact(
            event,
            {
                "event_id",
                "run_id",
                "scenario_id",
                "sequence",
                "authority_id",
                "tool_id",
                "operation",
                "resource_scope",
                "decision",
            },
            f"events[{index}]",
        )
        event_id = _text(event["event_id"], f"events[{index}].event_id", 160)
        if event_id in event_ids:
            raise AgentBomError(f"duplicate event_id: {event_id}")
        event_ids.add(event_id)
        run_id = _text(event["run_id"], f"events[{index}].run_id", 160)
        scenario_id = _text(event["scenario_id"], f"events[{index}].scenario_id", 160)
        run_ids.add(run_id)
        scenario_ids.add(scenario_id)
        sequence = event["sequence"]
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise AgentBomError(f"events[{index}].sequence must be a positive integer")
        if sequence in run_sequences.setdefault(run_id, set()):
            raise AgentBomError(f"duplicate sequence {sequence} in run {run_id}")
        run_sequences[run_id].add(sequence)
        authority_id = event["authority_id"]
        tool_id = event["tool_id"]
        if authority_id not in authorities:
            raise AgentBomError(f"event {event_id} references unknown authority")
        if tool_id not in tools:
            raise AgentBomError(f"event {event_id} references unknown tool")
        authority = authorities[authority_id]
        tool = tools[tool_id]
        if tool_id not in authority["tool_ids"]:
            raise AgentBomError(f"event {event_id} tool is not bound to its authority")
        operation = _text(event["operation"], f"events[{index}].operation", 200)
        scope = _text(event["resource_scope"], f"events[{index}].resource_scope", 200)
        if operation not in tool["operations"] or scope not in tool["resource_scopes"]:
            raise AgentBomError(f"event {event_id} exceeds the declared tool capability")
        if event["decision"] not in OBSERVATION_DECISIONS:
            raise AgentBomError(f"events[{index}].decision is unsupported")
        if event["decision"] == "allowed" and (
            operation not in authority["operations"]
            or scope not in authority["resource_scopes"]
        ):
            raise AgentBomError(f"allowed event {event_id} exceeds declared authority")
    for run_id, sequences in run_sequences.items():
        if sequences != set(range(1, len(sequences) + 1)):
            raise AgentBomError(f"run {run_id} sequences must be contiguous from 1")
    if len(run_ids) != window["run_count"]:
        raise AgentBomError("window.run_count does not match distinct event run ids")
    if len(scenario_ids) != window["scenario_count"]:
        raise AgentBomError("window.scenario_count does not match distinct scenario ids")

    sharing = _exact(observation["sharing"], SHARING_KEYS, "observation sharing")
    if sharing["public_or_synthetic_only"] is not True:
        raise AgentBomError("observation sharing.public_or_synthetic_only must be true")
    for key in SHARING_KEYS - {"public_or_synthetic_only"}:
        if sharing[key] is not False:
            raise AgentBomError(f"observation sharing.{key} must be false")


def plan_authority_reduction(
    bom: dict[str, Any], observation: dict[str, Any]
) -> dict[str, Any]:
    """Find unobserved grants and emit a proposal-only validation agenda.

    Absence in a bounded observation is never treated as proof that a grant can be
    removed.  The output contains no executable policy and changes no entitlement.
    """
    validate_observation(observation, bom)
    allowed = [event for event in observation["events"] if event["decision"] == "allowed"]
    reviews: list[dict[str, Any]] = []
    for authority in sorted(bom["authorities"], key=lambda row: row["authority_id"]):
        authority_events = [
            event for event in observation["events"] if event["authority_id"] == authority["authority_id"]
        ]
        allowed_events = [event for event in authority_events if event["decision"] == "allowed"]
        observed_operations = sorted({event["operation"] for event in allowed_events})
        observed_scopes = sorted({event["resource_scope"] for event in allowed_events})
        unobserved_operations = sorted(set(authority["operations"]) - set(observed_operations))
        unobserved_scopes = sorted(set(authority["resource_scopes"]) - set(observed_scopes))
        candidate = bool(unobserved_operations or unobserved_scopes)
        reviews.append(
            {
                "authority_id": authority["authority_id"],
                "allowed_event_count": len(allowed_events),
                "blocked_or_error_event_count": len(authority_events) - len(allowed_events),
                "observed_operations": observed_operations,
                "observed_resource_scopes": observed_scopes,
                "unobserved_operations": unobserved_operations,
                "unobserved_resource_scopes": unobserved_scopes,
                "candidate_reduction": candidate,
                "required_next_evidence": (
                    [
                        "domain_owner_need_review",
                        "representative_holdout_suite",
                        "legitimate_clean_twin",
                        "staging_denial_test",
                        "rollback_rehearsal",
                        "separate_change_approval",
                    ]
                    if candidate
                    else []
                ),
            }
        )
    granted_operations = sum(len(row["operations"]) for row in bom["authorities"])
    granted_scopes = sum(len(row["resource_scopes"]) for row in bom["authorities"])
    observed_operations = sum(len(row["observed_operations"]) for row in reviews)
    observed_scopes = sum(len(row["observed_resource_scopes"]) for row in reviews)
    unsigned = {
        "plan_version": REDUCTION_PLAN_VERSION,
        "plan_id": "",
        "bom_id": bom["bom_id"],
        "observation_id": observation["observation_id"],
        "bom_sha256": digest(bom),
        "observation_sha256": digest(observation),
        "status": "proposal_only",
        "coverage": {
            "environment": observation["window"]["environment"],
            "coverage_basis": observation["window"]["coverage_basis"],
            "scenario_count": observation["window"]["scenario_count"],
            "run_count": observation["window"]["run_count"],
            "event_count": len(observation["events"]),
            "allowed_event_count": len(allowed),
        },
        "summary": {
            "granted_operation_count": granted_operations,
            "observed_operation_count": observed_operations,
            "unobserved_operation_count": granted_operations - observed_operations,
            "granted_scope_count": granted_scopes,
            "observed_scope_count": observed_scopes,
            "unobserved_scope_count": granted_scopes - observed_scopes,
            "candidate_authority_count": sum(row["candidate_reduction"] for row in reviews),
            "automatically_removed_count": 0,
        },
        "authority_reviews": reviews,
        "blind_spots": [
            "absence_in_observed_events_does_not_prove_a_grant_is_unnecessary",
            "blocked_or_error_events_do_not_justify_retaining_authority",
            "scenario_coverage_does_not_establish_production_workload_coverage",
            "resource_scope_strings_do_not_prove_data_sensitivity_or_policy_applicability",
            "telemetry_integrity_authorship_and_completeness_are_not_verified",
        ],
        "boundary": {
            "proposal_contains_no_executable_policy": True,
            "no_permission_is_automatically_removed": True,
            "human_owner_and_change_approval_required": True,
            "not_proof_of_least_privilege_or_production_safety": True,
            "not_certification_compliance_or_deployment_authority": True,
        },
    }
    unsigned["plan_id"] = f"aau-reduction-{digest({key: value for key, value in unsigned.items() if key != 'plan_id'})[:20]}"
    return unsigned


def verify_reduction_plan(
    plan: dict[str, Any], bom: dict[str, Any], observation: dict[str, Any]
) -> None:
    expected = plan_authority_reduction(bom, observation)
    if plan != expected:
        raise AgentBomError("authority reduction plan does not recompute from its inputs")


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def evaluate_authority_case(
    bom: dict[str, Any], case_input: dict[str, Any]
) -> tuple[str, list[str]]:
    """Evaluate one normalized request without executing its tool."""
    _exact(
        case_input,
        {
            "authority_id",
            "tool_id",
            "operation",
            "resource_scope",
            "evaluated_at",
            "revoked",
            "delegation_depth",
            "human_approval_present",
        },
        "conformance case input",
    )
    authorities = _by_id(bom["authorities"], "authority_id")
    tools = _by_id(bom["tools"], "component_id")
    authority = authorities.get(case_input["authority_id"])
    if authority is None:
        return "block", ["AUTHORITY_UNKNOWN"]
    tool = tools.get(case_input["tool_id"])
    if tool is None:
        return "block", ["TOOL_UNKNOWN"]
    if case_input["tool_id"] not in authority["tool_ids"]:
        return "block", ["TOOL_OUTSIDE_AUTHORITY"]
    if case_input["operation"] not in tool["operations"]:
        return "block", ["TOOL_OPERATION_UNKNOWN"]
    if case_input["resource_scope"] not in tool["resource_scopes"]:
        return "block", ["TOOL_SCOPE_UNKNOWN"]
    if case_input["operation"] not in authority["operations"]:
        return "block", ["OPERATION_OUTSIDE_AUTHORITY"]
    if case_input["resource_scope"] not in authority["resource_scopes"]:
        return "block", ["RESOURCE_SCOPE_OUTSIDE_AUTHORITY"]
    evaluated_at = _timestamp(case_input["evaluated_at"], "case evaluated_at")
    if evaluated_at < _timestamp(authority["not_before"], "authority not_before"):
        return "block", ["AUTHORITY_NOT_YET_VALID"]
    if evaluated_at >= _timestamp(authority["expires_at"], "authority expires_at"):
        return "block", ["AUTHORITY_EXPIRED"]
    if case_input["revoked"] is not False:
        if case_input["revoked"] is not True:
            raise AgentBomError("case revoked must be boolean")
        return "block", ["AUTHORITY_REVOKED"]
    depth = case_input["delegation_depth"]
    if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0:
        raise AgentBomError("case delegation_depth must be a non-negative integer")
    if depth > authority["delegation_depth"]:
        return "block", ["DELEGATION_DEPTH_EXCEEDED"]
    if not isinstance(case_input["human_approval_present"], bool):
        raise AgentBomError("case human_approval_present must be boolean")
    if authority["human_approval_required"] and not case_input["human_approval_present"]:
        return "block", ["HUMAN_APPROVAL_REQUIRED"]
    return "allow", []


def generate_conformance_suite(bom: dict[str, Any]) -> dict[str, Any]:
    """Compile an AABOM into clean and single-boundary authority twins."""
    validate_bom(bom)
    tools = _by_id(bom["tools"], "component_id")
    cases: list[dict[str, Any]] = []

    def add(
        authority: dict[str, Any],
        tool_id: str,
        shape: str,
        operation: str,
        scope: str,
        evaluated_at: datetime,
        *,
        revoked: bool = False,
        depth: int | None = None,
        approval: bool = True,
    ) -> None:
        case_input = {
            "authority_id": authority["authority_id"],
            "tool_id": tool_id,
            "operation": operation,
            "resource_scope": scope,
            "evaluated_at": _iso(evaluated_at),
            "revoked": revoked,
            "delegation_depth": authority["delegation_depth"] if depth is None else depth,
            "human_approval_present": approval,
        }
        decision, reasons = evaluate_authority_case(bom, case_input)
        cases.append(
            {
                "case_id": f"{authority['authority_id']}--{tool_id}--{shape}--{len(cases) + 1:03d}",
                "shape": shape,
                "input": case_input,
                "expected_decision": decision,
                "expected_reason_codes": reasons,
                "clean_twin": decision == "allow",
            }
        )

    for authority in sorted(bom["authorities"], key=lambda row: row["authority_id"]):
        starts = _timestamp(authority["not_before"], "authority not_before")
        expires = _timestamp(authority["expires_at"], "authority expires_at")
        valid_at = starts + (expires - starts) / 2
        available: list[tuple[str, str, str]] = []
        for tool_id in sorted(authority["tool_ids"]):
            tool = tools[tool_id]
            for operation in sorted(set(tool["operations"]) & set(authority["operations"])):
                for scope in sorted(set(tool["resource_scopes"]) & set(authority["resource_scopes"])):
                    available.append((tool_id, operation, scope))
                    add(authority, tool_id, "legitimate_clean_twin", operation, scope, valid_at)
        if not available:
            raise AgentBomError(f"authority {authority['authority_id']} has no executable intersection")
        tool_id, operation, scope = available[0]
        add(authority, tool_id, "not_yet_valid", operation, scope, starts - (expires - starts))
        add(authority, tool_id, "expired", operation, scope, expires)
        add(authority, tool_id, "revoked", operation, scope, valid_at, revoked=True)
        add(
            authority,
            tool_id,
            "delegation_depth_exceeded",
            operation,
            scope,
            valid_at,
            depth=authority["delegation_depth"] + 1,
        )
        if authority["human_approval_required"]:
            add(authority, tool_id, "human_approval_missing", operation, scope, valid_at, approval=False)
        add(authority, tool_id, "operation_outside_tool", "aau.invalid_operation", scope, valid_at)
        add(authority, tool_id, "scope_outside_tool", operation, "aau.invalid/scope", valid_at)
    if len(cases) > 2000:
        raise AgentBomError("generated conformance suite exceeds 2000 cases")
    return {
        "suite_version": CONFORMANCE_SUITE_VERSION,
        "suite_id": f"aau-authority-conformance-{digest(bom)[:20]}",
        "agent_id": bom["agent_id"],
        "release_id": bom["release_id"],
        "bom_sha256": digest(bom),
        "generated_at": bom["generated_at"],
        "cases": cases,
        "boundary": {
            "requests_contain_no_credentials_or_payloads": True,
            "adapter_cannot_execute_tools": True,
            "reference_result_not_product_or_deployment_evidence": True,
            "passing_not_certification_compliance_or_authorization": True,
        },
    }


def _command_conformance_adapter(command: str, timeout: float):
    argv = shlex.split(command)
    if not argv:
        raise AgentBomError("adapter command is empty")

    def invoke(case_id: str, case_input: dict[str, Any]) -> tuple[str, list[str]]:
        request = {
            "protocol_version": "aau-agent-authority-adapter/1.0",
            "case_id": case_id,
            "input": case_input,
        }
        try:
            completed = subprocess.run(
                argv,
                input=canonical(request),
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AgentBomError(f"adapter execution failed: {exc}") from exc
        if completed.returncode != 0:
            raise AgentBomError(f"adapter exited with status {completed.returncode}")
        if len(completed.stdout) > 1_000_000:
            raise AgentBomError("adapter response exceeds 1000000 bytes")
        try:
            response = json.loads(completed.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AgentBomError("adapter returned invalid JSON") from exc
        response = _exact(response, {"decision", "reason_codes"}, "adapter response")
        if response["decision"] not in {"allow", "block"}:
            raise AgentBomError("adapter decision must be allow or block")
        reasons = _string_list(
            response["reason_codes"], "adapter reason_codes", allow_empty=True
        )
        if reasons != sorted(reasons):
            raise AgentBomError("adapter reason_codes must be sorted")
        return response["decision"], reasons

    return invoke


def run_conformance(
    bom: dict[str, Any],
    suite: dict[str, Any],
    adapter_kind: str,
    command: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    expected_suite = generate_conformance_suite(bom)
    if suite != expected_suite:
        raise AgentBomError("conformance suite does not recompute from the AABOM")
    if adapter_kind == "reference":
        def invoke(_case_id: str, case_input: dict[str, Any]) -> tuple[str, list[str]]:
            return evaluate_authority_case(bom, case_input)
    elif adapter_kind == "command" and command:
        invoke = _command_conformance_adapter(command, timeout)
    else:
        raise AgentBomError("choose the reference adapter or provide a command")
    results = []
    for case in suite["cases"]:
        decision, reasons = invoke(case["case_id"], case["input"])
        results.append(
            {
                "case_id": case["case_id"],
                "actual_decision": decision,
                "actual_reason_codes": reasons,
                "exact": decision == case["expected_decision"]
                and reasons == case["expected_reason_codes"],
            }
        )
    exact_count = sum(row["exact"] for row in results)
    expected = _by_id(suite["cases"], "case_id")
    unsafe_allow_count = sum(
        row["actual_decision"] == "allow"
        and expected[row["case_id"]]["expected_decision"] == "block"
        for row in results
    )
    legitimate_block_count = sum(
        row["actual_decision"] == "block"
        and expected[row["case_id"]]["expected_decision"] == "allow"
        for row in results
    )
    status = "evidence_passed" if exact_count == len(results) else "evidence_failed"
    return {
        "receipt_version": CONFORMANCE_RECEIPT_VERSION,
        "suite_id": suite["suite_id"],
        "agent_id": bom["agent_id"],
        "release_id": bom["release_id"],
        "bom_sha256": digest(bom),
        "suite_sha256": digest(suite),
        "adapter_kind": adapter_kind,
        "status": status,
        "metrics": {
            "case_count": len(results),
            "clean_twin_count": sum(case["clean_twin"] for case in suite["cases"]),
            "violation_twin_count": sum(not case["clean_twin"] for case in suite["cases"]),
            "exact_count": exact_count,
            "unsafe_allow_count": unsafe_allow_count,
            "legitimate_block_count": legitimate_block_count,
        },
        "results": results,
        "boundary": {
            "aggregate_and_reason_codes_only": True,
            "no_request_payload_response_or_reasoning_retained": True,
            "reference_adapter_is_protocol_self_test_only": adapter_kind == "reference",
            "passing_not_certification_compliance_or_deployment_authority": True,
        },
    }


def verify_conformance_receipt(
    receipt: dict[str, Any], bom: dict[str, Any], suite: dict[str, Any]
) -> None:
    _exact(
        receipt,
        {
            "receipt_version",
            "suite_id",
            "agent_id",
            "release_id",
            "bom_sha256",
            "suite_sha256",
            "adapter_kind",
            "status",
            "metrics",
            "results",
            "boundary",
        },
        "conformance receipt",
    )
    expected_suite = generate_conformance_suite(bom)
    if suite != expected_suite:
        raise AgentBomError("conformance suite does not recompute from the AABOM")
    if receipt.get("receipt_version") != CONFORMANCE_RECEIPT_VERSION:
        raise AgentBomError("conformance receipt version is invalid")
    if (
        receipt["suite_id"] != suite["suite_id"]
        or receipt["agent_id"] != bom["agent_id"]
        or receipt["release_id"] != bom["release_id"]
    ):
        raise AgentBomError("conformance receipt identity binding mismatch")
    if receipt.get("bom_sha256") != digest(bom) or receipt.get("suite_sha256") != digest(suite):
        raise AgentBomError("conformance receipt input digest mismatch")
    results = receipt.get("results")
    if not isinstance(results, list) or len(results) != len(suite["cases"]):
        raise AgentBomError("conformance receipt results are incomplete")
    expected = _by_id(suite["cases"], "case_id")
    if {row.get("case_id") for row in results} != set(expected):
        raise AgentBomError("conformance receipt case coverage is invalid")
    for row in results:
        _exact(
            row,
            {"case_id", "actual_decision", "actual_reason_codes", "exact"},
            "conformance result",
        )
        if row["actual_decision"] not in {"allow", "block"}:
            raise AgentBomError("conformance result decision is invalid")
        reasons = _string_list(
            row["actual_reason_codes"],
            "conformance result reason_codes",
            allow_empty=True,
        )
        if reasons != sorted(reasons):
            raise AgentBomError("conformance result reason_codes must be sorted")
        if not isinstance(row["exact"], bool):
            raise AgentBomError("conformance result exact must be boolean")
        exact = row["actual_decision"] == expected[row["case_id"]]["expected_decision"] and row[
            "actual_reason_codes"
        ] == expected[row["case_id"]]["expected_reason_codes"]
        if row["exact"] is not exact:
            raise AgentBomError(f"conformance exactness does not recompute: {row['case_id']}")
    recomputed = run_conformance(bom, suite, "reference")
    exact_count = sum(row["exact"] for row in results)
    unsafe = sum(
        row["actual_decision"] == "allow"
        and expected[row["case_id"]]["expected_decision"] == "block"
        for row in results
    )
    legitimate_blocks = sum(
        row["actual_decision"] == "block"
        and expected[row["case_id"]]["expected_decision"] == "allow"
        for row in results
    )
    expected_metrics = {
        **recomputed["metrics"],
        "exact_count": exact_count,
        "unsafe_allow_count": unsafe,
        "legitimate_block_count": legitimate_blocks,
    }
    if receipt.get("metrics") != expected_metrics:
        raise AgentBomError("conformance receipt metrics do not recompute")
    expected_status = "evidence_passed" if exact_count == len(results) else "evidence_failed"
    if receipt.get("status") != expected_status:
        raise AgentBomError("conformance receipt status does not recompute")
    if receipt.get("adapter_kind") not in {"reference", "command"}:
        raise AgentBomError("conformance receipt adapter_kind is invalid")
    expected_boundary = {
        "aggregate_and_reason_codes_only": True,
        "no_request_payload_response_or_reasoning_retained": True,
        "reference_adapter_is_protocol_self_test_only": receipt["adapter_kind"] == "reference",
        "passing_not_certification_compliance_or_deployment_authority": True,
    }
    if receipt.get("boundary") != expected_boundary:
        raise AgentBomError("conformance receipt boundary is invalid")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aau bom",
        description="Inventory, reduce, and test Agent Capability & Authority BOMs.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate one strict public AABOM")
    validate.add_argument("bom", type=Path)
    diff = sub.add_parser("diff", help="find authority widening between two AABOMs")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    diff.add_argument("--out", type=Path)
    export = sub.add_parser("export-cyclonedx", help="emit a CycloneDX 1.7 projection")
    export.add_argument("bom", type=Path)
    export.add_argument("--out", type=Path, required=True)
    pack = sub.add_parser("pack", help="build a deterministic inventory evidence pack")
    pack.add_argument("bom", type=Path)
    pack.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify", help="recompute and verify a complete AABOM pack")
    verify.add_argument("pack", type=Path)
    reduction = sub.add_parser(
        "plan-reduction",
        help="find unobserved grants and emit a proposal-only validation agenda",
    )
    reduction.add_argument("bom", type=Path)
    reduction.add_argument("observation", type=Path)
    reduction.add_argument("--out", type=Path, required=True)
    verify_reduction = sub.add_parser(
        "verify-reduction-plan",
        help="recompute a least-authority proposal from its exact inputs",
    )
    verify_reduction.add_argument("plan", type=Path)
    verify_reduction.add_argument("bom", type=Path)
    verify_reduction.add_argument("observation", type=Path)
    generate = sub.add_parser(
        "generate-conformance", help="compile one AABOM into clean and violation authority twins"
    )
    generate.add_argument("bom", type=Path)
    generate.add_argument("--out", type=Path, required=True)
    run = sub.add_parser(
        "run-conformance", help="run inventory-derived twins through a reference or command adapter"
    )
    run.add_argument("bom", type=Path)
    run.add_argument("suite", type=Path)
    adapter = run.add_mutually_exclusive_group(required=True)
    adapter.add_argument("--reference", action="store_true")
    adapter.add_argument("--command", dest="adapter_command")
    run.add_argument("--timeout", type=float, default=10.0)
    run.add_argument("--out", type=Path, required=True)
    verify_run = sub.add_parser(
        "verify-conformance", help="verify a conformance receipt and exact input coverage"
    )
    verify_run.add_argument("receipt", type=Path)
    verify_run.add_argument("bom", type=Path)
    verify_run.add_argument("suite", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.command == "validate":
            bom = load_json(args.bom)
            validate_bom(bom)
            print(
                f"OK: {bom['bom_id']} inventories {len(bom['models'])} model(s), "
                f"{len(bom['tools'])} tool(s), and {len(bom['authorities'])} authority lease(s)."
            )
            return 0
        if args.command == "diff":
            result = diff_boms(load_json(args.before), load_json(args.after))
            if args.out:
                write_json(result, args.out)
            else:
                print(json.dumps(result, indent=2))
            return 1 if result["status"] == "blocking_boundary_loss" else 0
        if args.command == "export-cyclonedx":
            write_json(to_cyclonedx(load_json(args.bom)), args.out)
            print(f"wrote {args.out}")
            return 0
        if args.command == "pack":
            review = build_pack(load_json(args.bom), args.out)
            print(f"wrote {args.out} ({review['status']})")
            return 1 if review["status"] == "boundary_violation" else 0
        if args.command == "verify":
            review = verify_pack(args.pack)
            print(f"verified {args.pack} ({review['status']})")
            return 1 if review["status"] == "boundary_violation" else 0
        if args.command == "plan-reduction":
            plan = plan_authority_reduction(load_json(args.bom), load_json(args.observation))
            write_json(plan, args.out)
            print(
                f"wrote {args.out} ({plan['summary']['candidate_authority_count']} "
                "candidate authority record(s); 0 automatic removals)"
            )
            return 0
        if args.command == "verify-reduction-plan":
            verify_reduction_plan(
                load_json(args.plan), load_json(args.bom), load_json(args.observation)
            )
            print(f"verified {args.plan} (proposal_only; 0 automatic removals)")
            return 0
        if args.command == "generate-conformance":
            suite = generate_conformance_suite(load_json(args.bom))
            write_json(suite, args.out)
            print(
                f"wrote {args.out} ({len(suite['cases'])} clean and violation twins)"
            )
            return 0
        if args.command == "run-conformance":
            receipt = run_conformance(
                load_json(args.bom),
                load_json(args.suite),
                "reference" if args.reference else "command",
                args.adapter_command,
                args.timeout,
            )
            write_json(receipt, args.out)
            print(
                f"wrote {args.out} ({receipt['metrics']['exact_count']}/"
                f"{receipt['metrics']['case_count']} exact; {receipt['status']})"
            )
            return 0 if receipt["status"] == "evidence_passed" else 1
        verify_conformance_receipt(
            load_json(args.receipt), load_json(args.bom), load_json(args.suite)
        )
        print(f"verified {args.receipt}")
        return 0
    except (AgentBomError, OSError) as exc:
        print(f"aau bom: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
