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
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


BOM_VERSION = "aau-agent-capability-bom/1.0"
DIFF_VERSION = "aau-agent-capability-diff/1.0"
REVIEW_VERSION = "aau-agent-capability-review/1.0"
PACK_VERSION = "aau-agent-capability-pack/1.0"
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aau bom",
        description="Validate, diff, project, and pack an Agent Capability & Authority BOM.",
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
        review = verify_pack(args.pack)
        print(f"verified {args.pack} ({review['status']})")
        return 1 if review["status"] == "boundary_violation" else 0
    except (AgentBomError, OSError) as exc:
        print(f"aau bom: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
