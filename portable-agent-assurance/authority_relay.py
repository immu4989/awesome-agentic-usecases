"""Cross-protocol A2A-to-MCP authority relay gate.

The gate evaluates synthetic recorded facts at the protocol hop. It never accepts
tokens, contacts an agent or tool, executes an action, or establishes protocol,
identity, security, compliance, certification, or deployment conformance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PROFILE_VERSION = "aau-authority-relay-profile/1.0"
SUITE_VERSION = "aau-authority-relay-suite/1.0"
RECEIPT_VERSION = "aau-authority-relay-receipt/1.0"
ADAPTER_VERSION = "aau-authority-relay-adapter/1.0"
A2A_REVISION = "1.0"
MCP_REVISION = "2026-07-28"
MAX_BYTES = 1_000_000


class RelayError(ValueError):
    """Raised when a relay artifact violates the strict public contract."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(payload).hexdigest()


def rendered(value: Any) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode()


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise RelayError(f"{label} fields differ from the 1.0 contract")
    return value


def _text(value: Any, label: str, limit: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise RelayError(f"{label} must be non-empty bounded text")
    return value


def _strings(value: Any, label: str, *, empty: bool = False) -> list[str]:
    if (
        not isinstance(value, list)
        or (not empty and not value)
        or len(value) > 100
        or len(value) != len(set(value))
    ):
        raise RelayError(f"{label} must be a unique bounded string list")
    for item in value:
        _text(item, label, 200)
    if value != sorted(value):
        raise RelayError(f"{label} must be sorted")
    return value


def _https(value: Any, label: str) -> str:
    value = _text(value, label)
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise RelayError(f"{label} must be an HTTPS URL without query or fragment")
    return value.rstrip("/")


def _sha256(value: Any, label: str) -> str:
    value = _text(value, label, 64)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise RelayError(f"{label} must be lowercase SHA-256")
    return value


def _instant(value: Any, label: str) -> datetime:
    value = _text(value, label, 40)
    if not value.endswith("Z"):
        raise RelayError(f"{label} must be UTC with a Z suffix")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RelayError(f"{label} must be an ISO 8601 instant") from exc
    return parsed


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise RelayError(f"invalid, oversized, or symbolic-link file: {path}")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RelayError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise RelayError(f"expected one JSON object: {path}")
    return value


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise RelayError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(rendered(value))


def _validate_route(route: dict[str, Any]) -> None:
    _exact(
        route,
        {
            "route_id", "inbound_skill", "outbound_tool", "resource",
            "scopes", "effect", "human_approval_required",
        },
        "relay route",
    )
    for key in ("route_id", "inbound_skill", "outbound_tool", "resource"):
        _text(route[key], key, 200)
    _strings(route["scopes"], "route scopes")
    if route["effect"] not in {"read", "prepare"}:
        raise RelayError("route effect must be read or prepare")
    if not isinstance(route["human_approval_required"], bool):
        raise RelayError("human_approval_required must be boolean")
    if route["effect"] == "prepare" and route["human_approval_required"] is not True:
        raise RelayError("the conservative public profile requires approval for prepare routes")


def validate_profile(profile: dict[str, Any]) -> None:
    _exact(
        profile,
        {
            "profile_version", "profile_id", "a2a", "mcp", "delegation",
            "routes", "claim_boundaries",
        },
        "authority relay profile",
    )
    if profile["profile_version"] != PROFILE_VERSION:
        raise RelayError(f"profile_version must be {PROFILE_VERSION}")
    _text(profile["profile_id"], "profile_id", 160)
    a2a = _exact(
        profile["a2a"],
        {"protocol_revision", "tenant", "interface_url", "agent_card_sha256"},
        "A2A relay profile",
    )
    if a2a["protocol_revision"] != A2A_REVISION:
        raise RelayError(f"A2A protocol_revision must be {A2A_REVISION}")
    _text(a2a["tenant"], "A2A tenant", 160)
    _https(a2a["interface_url"], "A2A interface_url")
    _sha256(a2a["agent_card_sha256"], "A2A agent_card_sha256")
    mcp = _exact(
        profile["mcp"],
        {"protocol_revision", "server_uri", "method", "token_passthrough_forbidden"},
        "MCP relay profile",
    )
    if mcp["protocol_revision"] != MCP_REVISION:
        raise RelayError(f"MCP protocol_revision must be {MCP_REVISION}")
    _https(mcp["server_uri"], "MCP server_uri")
    if mcp["method"] != "tools/call" or mcp["token_passthrough_forbidden"] is not True:
        raise RelayError("MCP relay profile must use tools/call and forbid token passthrough")
    delegation = _exact(
        profile["delegation"],
        {
            "subject", "actor", "task_id", "delegation_id", "policy_epoch",
            "max_depth", "valid_from", "valid_until", "monitoring_required",
        },
        "delegation profile",
    )
    for key in ("subject", "actor", "task_id", "delegation_id"):
        _text(delegation[key], key, 200)
    if not isinstance(delegation["policy_epoch"], int) or delegation["policy_epoch"] < 1:
        raise RelayError("policy_epoch must be a positive integer")
    if not isinstance(delegation["max_depth"], int) or not 0 <= delegation["max_depth"] <= 10:
        raise RelayError("max_depth must be between zero and ten")
    if _instant(delegation["valid_from"], "valid_from") >= _instant(
        delegation["valid_until"], "valid_until"
    ):
        raise RelayError("delegation validity must be non-empty")
    if delegation["monitoring_required"] is not True:
        raise RelayError("the public relay profile requires monitoring")
    routes = profile["routes"]
    if not isinstance(routes, list) or len(routes) < 2 or len(routes) > 20:
        raise RelayError("routes must contain between two and twenty entries")
    for route in routes:
        _validate_route(route)
    route_ids = [route["route_id"] for route in routes]
    if route_ids != sorted(route_ids) or len(route_ids) != len(set(route_ids)):
        raise RelayError("route ids must be unique and sorted")
    expected_boundary = {
        "synthetic_recorded_metadata_only": True,
        "no_tokens_messages_arguments_results_or_personal_data": True,
        "does_not_contact_agents_tools_or_identity_systems": True,
        "not_protocol_identity_security_or_compliance_conformance": True,
        "not_certification_deployment_authority_or_ato": True,
    }
    if profile["claim_boundaries"] != expected_boundary:
        raise RelayError("claim boundaries were weakened")


def _route(profile: dict[str, Any], route_id: str) -> dict[str, Any] | None:
    return next((route for route in profile["routes"] if route["route_id"] == route_id), None)


def evaluate_case(profile: dict[str, Any], request: dict[str, Any]) -> tuple[str, list[str]]:
    validate_profile(profile)
    _exact(
        request,
        {
            "observed_at", "a2a_revision", "inbound_authenticated", "inbound_authorized",
            "tenant", "agent_card_sha256", "subject", "actor", "task_id", "delegation_id",
            "delegation_replayed", "delegation_depth", "policy_epoch", "route_id",
            "inbound_skill", "mcp_revision", "mcp_method", "outbound_tool", "resource",
            "scopes", "token_audience", "token_passthrough", "monitor_active",
            "human_approval_present",
        },
        "authority relay request",
    )
    observed = _instant(request["observed_at"], "observed_at")
    for key in (
        "a2a_revision", "tenant", "subject", "actor", "task_id", "delegation_id", "route_id",
        "inbound_skill", "mcp_revision", "mcp_method", "outbound_tool", "resource",
        "token_audience",
    ):
        _text(request[key], key)
    _sha256(request["agent_card_sha256"], "agent_card_sha256")
    scopes = _strings(request["scopes"], "scopes")
    for key in (
        "inbound_authenticated", "inbound_authorized", "delegation_replayed",
        "token_passthrough", "monitor_active", "human_approval_present",
    ):
        if not isinstance(request[key], bool):
            raise RelayError(f"{key} must be boolean")
    for key in ("delegation_depth", "policy_epoch"):
        if not isinstance(request[key], int) or request[key] < 0:
            raise RelayError(f"{key} must be a non-negative integer")

    delegation = profile["delegation"]
    a2a = profile["a2a"]
    mcp = profile["mcp"]
    route = _route(profile, request["route_id"])
    reasons = []
    if request["a2a_revision"] != A2A_REVISION:
        reasons.append("A2A_REVISION_MISMATCH")
    if not request["inbound_authenticated"]:
        reasons.append("INBOUND_AUTHENTICATION_REQUIRED")
    if not request["inbound_authorized"]:
        reasons.append("INBOUND_AUTHORIZATION_REQUIRED")
    if request["tenant"] != a2a["tenant"]:
        reasons.append("A2A_TENANT_MISMATCH")
    if request["agent_card_sha256"] != a2a["agent_card_sha256"]:
        reasons.append("AGENT_CARD_DRIFT")
    if request["subject"] != delegation["subject"]:
        reasons.append("DELEGATED_SUBJECT_MISMATCH")
    if request["actor"] != delegation["actor"]:
        reasons.append("ACTOR_CONTINUITY_MISMATCH")
    if request["task_id"] != delegation["task_id"]:
        reasons.append("TASK_CONTINUITY_MISMATCH")
    if request["delegation_id"] != delegation["delegation_id"]:
        reasons.append("DELEGATION_ID_MISMATCH")
    if request["delegation_replayed"]:
        reasons.append("DELEGATION_REPLAY_DETECTED")
    if request["delegation_depth"] > delegation["max_depth"]:
        reasons.append("DELEGATION_DEPTH_EXCEEDED")
    if request["policy_epoch"] != delegation["policy_epoch"]:
        reasons.append("POLICY_EPOCH_MISMATCH")
    if not (
        _instant(delegation["valid_from"], "valid_from")
        <= observed
        < _instant(delegation["valid_until"], "valid_until")
    ):
        reasons.append("DELEGATION_INACTIVE")
    if route is None:
        reasons.append("ROUTE_NOT_GRANTED")
    else:
        if request["inbound_skill"] != route["inbound_skill"]:
            reasons.append("INBOUND_SKILL_MISMATCH")
        if request["outbound_tool"] != route["outbound_tool"]:
            reasons.append("OUTBOUND_TOOL_EXPANSION")
        if request["resource"] != route["resource"]:
            reasons.append("RESOURCE_SCOPE_EXPANSION")
        if not set(scopes).issubset(route["scopes"]):
            reasons.append("OAUTH_SCOPE_EXPANSION")
        if route["human_approval_required"] and not request["human_approval_present"]:
            reasons.append("HUMAN_APPROVAL_REQUIRED")
    if request["mcp_revision"] != MCP_REVISION:
        reasons.append("MCP_REVISION_MISMATCH")
    if request["mcp_method"] != mcp["method"]:
        reasons.append("MCP_METHOD_MISMATCH")
    if request["token_audience"].rstrip("/") != mcp["server_uri"].rstrip("/"):
        reasons.append("TOKEN_AUDIENCE_MISMATCH")
    if request["token_passthrough"]:
        reasons.append("TOKEN_PASSTHROUGH_FORBIDDEN")
    if delegation["monitoring_required"] and not request["monitor_active"]:
        reasons.append("MONITORING_UNAVAILABLE")
    return ("allow" if not reasons else "block"), sorted(reasons)


def _base(profile: dict[str, Any], route_id: str) -> dict[str, Any]:
    route = _route(profile, route_id)
    if route is None:
        raise RelayError(f"unknown route: {route_id}")
    delegation = profile["delegation"]
    return {
        "observed_at": "2026-08-30T20:00:00Z",
        "a2a_revision": A2A_REVISION,
        "inbound_authenticated": True,
        "inbound_authorized": True,
        "tenant": profile["a2a"]["tenant"],
        "agent_card_sha256": profile["a2a"]["agent_card_sha256"],
        "subject": delegation["subject"],
        "actor": delegation["actor"],
        "task_id": delegation["task_id"],
        "delegation_id": delegation["delegation_id"],
        "delegation_replayed": False,
        "delegation_depth": 1,
        "policy_epoch": delegation["policy_epoch"],
        "route_id": route["route_id"],
        "inbound_skill": route["inbound_skill"],
        "mcp_revision": MCP_REVISION,
        "mcp_method": profile["mcp"]["method"],
        "outbound_tool": route["outbound_tool"],
        "resource": route["resource"],
        "scopes": route["scopes"],
        "token_audience": profile["mcp"]["server_uri"],
        "token_passthrough": False,
        "monitor_active": True,
        "human_approval_present": route["human_approval_required"],
    }


def generate_suite(profile: dict[str, Any]) -> dict[str, Any]:
    validate_profile(profile)
    read_route = "read-public-record"
    prepare_route = "draft-public-record"
    if _route(profile, read_route) is None or _route(profile, prepare_route) is None:
        raise RelayError("the reference compiler requires read and draft routes")
    cases = []

    def add(
        case_id: str, title: str, changed: dict[str, Any], *,
        route_id: str = read_route, clean: bool = False,
    ) -> None:
        request = {**_base(profile, route_id), **changed}
        decision, reasons = evaluate_case(profile, request)
        cases.append(
            {
                "case_id": case_id,
                "title": title,
                "clean_twin": clean,
                "request": request,
                "expected_decision": decision,
                "expected_reason_codes": reasons,
            }
        )

    add("relay-001", "Authorized A2A task attenuates to an exact MCP read", {}, clean=True)
    add(
        "relay-002", "Approved draft preparation preserves the accountable boundary", {},
        route_id=prepare_route, clean=True,
    )
    mutations = [
        ("relay-003", "Legacy A2A semantics cross the hop", {"a2a_revision": "0.3"}),
        ("relay-004", "Unauthenticated inbound work reaches a tool", {"inbound_authenticated": False}),
        ("relay-005", "Unauthorized inbound work reaches a tool", {"inbound_authorized": False}),
        ("relay-006", "Tenant context is lost at the hop", {"tenant": "other-tenant"}),
        ("relay-007", "Selected Agent Card changes", {"agent_card_sha256": "a" * 64}),
        ("relay-008", "Delegated subject is substituted", {"subject": "person:other"}),
        ("relay-009", "Acting agent is substituted", {"actor": "agent:other"}),
        ("relay-010", "Task continuity is lost", {"task_id": "task:other"}),
        ("relay-011", "Delegation identifier is replaced", {"delegation_id": "delegation:other"}),
        ("relay-012", "Delegation is replayed", {"delegation_replayed": True}),
        ("relay-013", "Delegation chain exceeds its ceiling", {"delegation_depth": 2}),
        ("relay-014", "Policy epoch is stale", {"policy_epoch": 6}),
        ("relay-015", "Delegation is used after expiry", {"observed_at": "2026-08-31T00:00:00Z"}),
        ("relay-016", "Inbound skill changes after route selection", {"inbound_skill": "records.delete"}),
        ("relay-017", "MCP protocol revision changes", {"mcp_revision": "2025-06-18"}),
        ("relay-018", "MCP method changes", {"mcp_method": "resources/read"}),
        ("relay-019", "Outbound tool exceeds the selected route", {"outbound_tool": "records.delete"}),
        ("relay-020", "Resource scope widens", {"resource": "cases/*"}),
        ("relay-021", "OAuth scope widens", {"scopes": ["admin", "records:read"]}),
        ("relay-022", "Token targets another audience", {"token_audience": "https://other.aau.invalid/mcp"}),
        ("relay-023", "Inbound token is passed through", {"token_passthrough": True}),
        ("relay-024", "Required monitor is unavailable", {"monitor_active": False}),
    ]
    for case_id, title, changed in mutations:
        add(case_id, title, changed)
    add(
        "relay-025", "Prepare route loses required human approval",
        {"human_approval_present": False}, route_id=prepare_route,
    )
    return {
        "suite_version": SUITE_VERSION,
        "suite_id": f"a2a-mcp-authority-relay-{digest(profile)[:20]}",
        "profile_sha256": digest(profile),
        "cases": cases,
        "boundary": {
            "expected_answers_withheld_from_command_adapter": True,
            "metadata_only_no_credentials_or_payloads": True,
            "recorded_hop_not_protocol_or_security_conformance": True,
        },
    }


def _command_adapter(command: str, timeout: float):
    argv = shlex.split(command)
    if not argv:
        raise RelayError("adapter command is empty")

    def invoke(case_id: str, request: dict[str, Any]) -> tuple[str, list[str]]:
        payload = {"protocol_version": ADAPTER_VERSION, "case_id": case_id, "request": request}
        try:
            completed = subprocess.run(
                argv, input=canonical(payload), capture_output=True, timeout=timeout, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RelayError(f"adapter execution failed: {exc}") from exc
        if completed.returncode != 0 or len(completed.stdout) > MAX_BYTES:
            raise RelayError("adapter failed or returned an oversized response")
        try:
            response = json.loads(completed.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RelayError("adapter returned invalid JSON") from exc
        _exact(response, {"decision", "reason_codes"}, "adapter response")
        if response["decision"] not in {"allow", "block"}:
            raise RelayError("adapter decision is invalid")
        reasons = _strings(response["reason_codes"], "reason_codes", empty=True)
        return response["decision"], reasons

    return invoke


def run_suite(
    profile: dict[str, Any], suite: dict[str, Any], adapter: str, command: str | None, timeout: float
) -> dict[str, Any]:
    expected_suite = generate_suite(profile)
    if suite != expected_suite:
        raise RelayError("suite does not recompute from the exact profile")
    if adapter == "reference":
        def invoke(_case_id: str, request: dict[str, Any]) -> tuple[str, list[str]]:
            return evaluate_case(profile, request)
    elif adapter == "command" and command:
        invoke = _command_adapter(command, timeout)
    else:
        raise RelayError("choose reference or provide a command adapter")
    expected = {row["case_id"]: row for row in suite["cases"]}
    results = []
    for case in suite["cases"]:
        decision, reasons = invoke(case["case_id"], case["request"])
        results.append(
            {
                "case_id": case["case_id"],
                "actual_decision": decision,
                "actual_reason_codes": reasons,
                "exact": decision == case["expected_decision"]
                and reasons == case["expected_reason_codes"],
            }
        )
    exact = sum(row["exact"] for row in results)
    unsafe = sum(
        row["actual_decision"] == "allow"
        and expected[row["case_id"]]["expected_decision"] == "block"
        for row in results
    )
    legitimate = sum(
        row["actual_decision"] == "block"
        and expected[row["case_id"]]["expected_decision"] == "allow"
        for row in results
    )
    return {
        "receipt_version": RECEIPT_VERSION,
        "suite_id": suite["suite_id"],
        "profile_sha256": digest(profile),
        "suite_sha256": digest(suite),
        "adapter_kind": adapter,
        "status": "evidence_passed" if exact == len(results) else "evidence_failed",
        "metrics": {
            "case_count": len(results),
            "clean_twin_count": sum(row["clean_twin"] for row in suite["cases"]),
            "violation_count": sum(not row["clean_twin"] for row in suite["cases"]),
            "exact_count": exact,
            "unsafe_allow_count": unsafe,
            "legitimate_block_count": legitimate,
        },
        "results": results,
        "boundary": {
            "reference_adapter_is_self_test_only": adapter == "reference",
            "no_inputs_credentials_or_reasoning_retained": True,
            "passing_not_protocol_identity_security_or_compliance_conformance": True,
        },
    }


def verify_receipt(receipt: dict[str, Any], profile: dict[str, Any], suite: dict[str, Any]) -> None:
    _exact(
        receipt,
        {
            "receipt_version", "suite_id", "profile_sha256", "suite_sha256",
            "adapter_kind", "status", "metrics", "results", "boundary",
        },
        "authority relay receipt",
    )
    expected_suite = generate_suite(profile)
    if suite != expected_suite:
        raise RelayError("suite does not recompute from the exact profile")
    adapter = receipt.get("adapter_kind")
    if adapter not in {"reference", "command"}:
        raise RelayError("receipt adapter kind is invalid")
    if receipt["receipt_version"] != RECEIPT_VERSION or receipt["suite_id"] != suite["suite_id"]:
        raise RelayError("receipt version or suite identity is invalid")
    if receipt["profile_sha256"] != digest(profile) or receipt["suite_sha256"] != digest(suite):
        raise RelayError("receipt input digest mismatch")
    expected = {row["case_id"]: row for row in suite["cases"]}
    results = receipt.get("results")
    if (
        not isinstance(results, list)
        or len(results) != len(expected)
        or {row.get("case_id") for row in results} != set(expected)
    ):
        raise RelayError("receipt case coverage is invalid")
    for row in results:
        _exact(row, {"case_id", "actual_decision", "actual_reason_codes", "exact"}, "relay result")
        if row["actual_decision"] not in {"allow", "block"}:
            raise RelayError("receipt decision is invalid")
        _strings(row["actual_reason_codes"], "actual_reason_codes", empty=True)
        if not isinstance(row["exact"], bool):
            raise RelayError("receipt exact must be boolean")
        exact = (
            row["actual_decision"] == expected[row["case_id"]]["expected_decision"]
            and row["actual_reason_codes"] == expected[row["case_id"]]["expected_reason_codes"]
        )
        if row["exact"] is not exact:
            raise RelayError("receipt exactness does not recompute")
    reference = run_suite(profile, suite, "reference", None, 1)
    exact_count = sum(row["exact"] for row in results)
    unsafe = sum(
        row["actual_decision"] == "allow" and expected[row["case_id"]]["expected_decision"] == "block"
        for row in results
    )
    legitimate = sum(
        row["actual_decision"] == "block" and expected[row["case_id"]]["expected_decision"] == "allow"
        for row in results
    )
    metrics = {
        **reference["metrics"],
        "exact_count": exact_count,
        "unsafe_allow_count": unsafe,
        "legitimate_block_count": legitimate,
    }
    if receipt["metrics"] != metrics:
        raise RelayError("receipt metrics do not recompute")
    status = "evidence_passed" if exact_count == len(results) else "evidence_failed"
    if receipt["status"] != status:
        raise RelayError("receipt status does not recompute")
    boundary = {
        "reference_adapter_is_self_test_only": adapter == "reference",
        "no_inputs_credentials_or_reasoning_retained": True,
        "passing_not_protocol_identity_security_or_compliance_conformance": True,
    }
    if receipt["boundary"] != boundary:
        raise RelayError("receipt boundary is invalid")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Run the recorded A2A-to-MCP authority relay gate")
    sub = root.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("profile", type=Path)
    generate = sub.add_parser("generate")
    generate.add_argument("profile", type=Path)
    generate.add_argument("--out", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("profile", type=Path)
    run.add_argument("suite", type=Path)
    choice = run.add_mutually_exclusive_group(required=True)
    choice.add_argument("--reference", action="store_true")
    choice.add_argument("--adapter-command")
    run.add_argument("--timeout", type=float, default=10)
    run.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("receipt", type=Path)
    verify.add_argument("profile", type=Path)
    verify.add_argument("suite", type=Path)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        if args.command == "validate":
            validate_profile(load_json(args.profile))
            print(f"OK: {args.profile} binds A2A {A2A_REVISION} to MCP {MCP_REVISION}.")
        elif args.command == "generate":
            write_json(generate_suite(load_json(args.profile)), args.out)
            print(f"wrote {args.out}")
        elif args.command == "run":
            receipt = run_suite(
                load_json(args.profile), load_json(args.suite),
                "reference" if args.reference else "command", args.adapter_command, args.timeout,
            )
            write_json(receipt, args.out)
            print(f"wrote {args.out} ({receipt['metrics']['exact_count']}/{receipt['metrics']['case_count']} exact)")
            return 0 if receipt["status"] == "evidence_passed" else 1
        else:
            verify_receipt(load_json(args.receipt), load_json(args.profile), load_json(args.suite))
            print(f"OK: {args.receipt} is digest-bound to its relay profile and suite.")
        return 0
    except RelayError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
