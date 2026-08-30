"""Recorded MCP 2026-07-28 authorization delta gate.

This is an offline, synthetic interoperability experiment. It does not perform an
OAuth flow, start an MCP client or server, validate production tokens, or claim
MCP/OAuth conformance, security, compliance, certification, or deployment approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PROFILE_VERSION = "aau-mcp-authorization-2026-profile/1.0"
SUITE_VERSION = "aau-mcp-authorization-2026-suite/1.0"
RECEIPT_VERSION = "aau-mcp-authorization-2026-receipt/1.0"
PROTOCOL_VERSION = "2026-07-28"
MAX_BYTES = 1_000_000
HEX = set("0123456789abcdef")


class McpDeltaError(ValueError):
    """Raised when an MCP delta artifact violates the strict public contract."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def rendered(value: Any) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode()


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(payload).hexdigest()


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise McpDeltaError(f"{label} fields differ from the 1.0 contract")
    return value


def _text(value: Any, label: str, limit: int = 300) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise McpDeltaError(f"{label} must be non-empty bounded text")
    return value


def _strings(value: Any, label: str, *, empty: bool = False) -> list[str]:
    if (
        not isinstance(value, list)
        or (not empty and not value)
        or len(value) > 100
        or len(value) != len(set(value))
    ):
        raise McpDeltaError(f"{label} must be a unique bounded string list")
    for item in value:
        _text(item, label, 160)
    if value != sorted(value):
        raise McpDeltaError(f"{label} must be sorted")
    return value


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise McpDeltaError(f"invalid, oversized, or symbolic-link file: {path}")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise McpDeltaError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise McpDeltaError(f"expected one JSON object: {path}")
    return value


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise McpDeltaError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(rendered(value))


def _https_uri(value: Any, label: str) -> str:
    value = _text(value, label, 500)
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.fragment:
        raise McpDeltaError(f"{label} must be an HTTPS URI without a fragment")
    return value


def validate_profile(profile: dict[str, Any]) -> None:
    _exact(
        profile,
        {
            "profile_version",
            "profile_id",
            "protocol_revision",
            "server_uri",
            "authorization_server_issuer",
            "registration_mode",
            "minimal_scopes",
            "protected_resource_metadata",
            "claim_boundaries",
        },
        "MCP delta profile",
    )
    if profile["profile_version"] != PROFILE_VERSION:
        raise McpDeltaError(f"profile_version must be {PROFILE_VERSION}")
    _text(profile["profile_id"], "profile_id", 160)
    if profile["protocol_revision"] != PROTOCOL_VERSION:
        raise McpDeltaError(f"protocol_revision must be {PROTOCOL_VERSION}")
    _https_uri(profile["server_uri"], "server_uri")
    _https_uri(profile["authorization_server_issuer"], "authorization_server_issuer")
    if profile["registration_mode"] not in {
        "client_id_metadata_document",
        "pre_registered",
        "dynamic_client_registration_deprecated",
    }:
        raise McpDeltaError("registration_mode is unsupported")
    _strings(profile["minimal_scopes"], "minimal_scopes")
    metadata = _exact(
        profile["protected_resource_metadata"],
        {"discovery_verified", "authorization_servers", "scopes_supported"},
        "protected_resource_metadata",
    )
    if metadata["discovery_verified"] is not True:
        raise McpDeltaError("protected resource discovery must be declared verified")
    issuers = _strings(metadata["authorization_servers"], "authorization_servers")
    for issuer in issuers:
        _https_uri(issuer, "authorization server")
    if profile["authorization_server_issuer"] not in issuers:
        raise McpDeltaError("selected issuer is absent from protected resource metadata")
    supported = _strings(metadata["scopes_supported"], "scopes_supported")
    if not set(profile["minimal_scopes"]).issubset(supported):
        raise McpDeltaError("minimal scopes exceed protected resource metadata")
    expected = {
        "synthetic_recorded_inputs_only": True,
        "does_not_execute_authorization_or_tools": True,
        "not_mcp_or_oauth_conformance": True,
        "not_security_compliance_certification_or_approval": True,
    }
    if profile["claim_boundaries"] != expected:
        raise McpDeltaError("claim boundaries were weakened")


def evaluate_case(profile: dict[str, Any], request: dict[str, Any]) -> tuple[str, list[str]]:
    validate_profile(profile)
    _exact(
        request,
        {
            "protocol_revision",
            "mcp_method_header",
            "mcp_name_header",
            "jsonrpc_method",
            "tool_name",
            "authorization_response_issuer",
            "issuer_parameter_advertised",
            "credential_issuer",
            "authorization_resource",
            "token_resource",
            "token_audience",
            "requested_scopes",
            "prior_scopes",
            "challenge_scopes",
            "insufficient_scope",
            "step_up_attempted",
            "token_passthrough",
            "token_in_query",
        },
        "MCP delta request",
    )
    for key in (
        "protocol_revision",
        "mcp_method_header",
        "mcp_name_header",
        "jsonrpc_method",
        "tool_name",
        "credential_issuer",
        "authorization_resource",
        "token_resource",
        "token_audience",
    ):
        _text(request[key], key, 500)
    if request["authorization_response_issuer"] is not None:
        _text(request["authorization_response_issuer"], "authorization_response_issuer", 500)
    for key in (
        "issuer_parameter_advertised",
        "insufficient_scope",
        "step_up_attempted",
        "token_passthrough",
        "token_in_query",
    ):
        if not isinstance(request[key], bool):
            raise McpDeltaError(f"{key} must be boolean")
    requested = _strings(request["requested_scopes"], "requested_scopes")
    prior = _strings(request["prior_scopes"], "prior_scopes", empty=True)
    challenge = _strings(request["challenge_scopes"], "challenge_scopes", empty=True)
    expected_issuer = profile["authorization_server_issuer"]
    server = profile["server_uri"]
    reasons = []
    if request["protocol_revision"] != PROTOCOL_VERSION:
        reasons.append("PROTOCOL_REVISION_MISMATCH")
    if request["mcp_method_header"] != request["jsonrpc_method"]:
        reasons.append("MCP_METHOD_HEADER_MISMATCH")
    if request["mcp_name_header"] != request["tool_name"]:
        reasons.append("MCP_NAME_HEADER_MISMATCH")
    response_issuer = request["authorization_response_issuer"]
    if request["issuer_parameter_advertised"] and response_issuer is None:
        reasons.append("AUTHORIZATION_RESPONSE_ISSUER_MISSING")
    elif response_issuer is not None and response_issuer != expected_issuer:
        reasons.append("AUTHORIZATION_RESPONSE_ISSUER_MISMATCH")
    if request["credential_issuer"] != expected_issuer:
        reasons.append("CLIENT_CREDENTIAL_ISSUER_MISMATCH")
    if request["authorization_resource"] != server:
        reasons.append("AUTHORIZATION_RESOURCE_MISMATCH")
    if request["token_resource"] != server:
        reasons.append("TOKEN_RESOURCE_MISMATCH")
    if request["token_audience"] != server:
        reasons.append("TOKEN_AUDIENCE_MISMATCH")
    if not request["insufficient_scope"] and not set(requested).issubset(
        profile["minimal_scopes"]
    ):
        reasons.append("INITIAL_SCOPE_NOT_MINIMAL")
    if request["insufficient_scope"]:
        if not request["step_up_attempted"]:
            reasons.append("STEP_UP_NOT_ATTEMPTED")
        elif not set(prior).union(challenge).issubset(requested):
            reasons.append("SCOPE_UNION_INCOMPLETE")
    if request["token_passthrough"]:
        reasons.append("TOKEN_PASSTHROUGH_FORBIDDEN")
    if request["token_in_query"]:
        reasons.append("TOKEN_QUERY_TRANSPORT_FORBIDDEN")
    return ("allow" if not reasons else "block"), sorted(reasons)


def _base(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_revision": PROTOCOL_VERSION,
        "mcp_method_header": "tools/call",
        "mcp_name_header": "records.search",
        "jsonrpc_method": "tools/call",
        "tool_name": "records.search",
        "authorization_response_issuer": profile["authorization_server_issuer"],
        "issuer_parameter_advertised": True,
        "credential_issuer": profile["authorization_server_issuer"],
        "authorization_resource": profile["server_uri"],
        "token_resource": profile["server_uri"],
        "token_audience": profile["server_uri"],
        "requested_scopes": ["records:read"],
        "prior_scopes": [],
        "challenge_scopes": [],
        "insufficient_scope": False,
        "step_up_attempted": False,
        "token_passthrough": False,
        "token_in_query": False,
    }


def generate_suite(profile: dict[str, Any]) -> dict[str, Any]:
    validate_profile(profile)
    cases = []

    def add(case_id: str, title: str, changed: dict[str, Any], clean: bool = False) -> None:
        request = {**_base(profile), **changed}
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

    add("mcp26-001", "Legitimate resource-bound read", {}, True)
    add(
        "mcp26-002",
        "Legitimate scope step-up preserves prior grants",
        {
            "requested_scopes": ["records:prepare", "records:read"],
            "prior_scopes": ["records:read"],
            "challenge_scopes": ["records:prepare"],
            "insufficient_scope": True,
            "step_up_attempted": True,
        },
        True,
    )
    mutations = [
        ("mcp26-003", "Old protocol revision", {"protocol_revision": "2025-06-18"}),
        ("mcp26-004", "Method header collision", {"mcp_method_header": "resources/read"}),
        ("mcp26-005", "Tool-name header collision", {"mcp_name_header": "records.delete"}),
        ("mcp26-006", "Advertised issuer omitted", {"authorization_response_issuer": None}),
        ("mcp26-007", "Authorization issuer mix-up", {"authorization_response_issuer": "https://other.aau.invalid"}),
        ("mcp26-008", "Client credentials reused across issuers", {"credential_issuer": "https://other.aau.invalid"}),
        ("mcp26-009", "Authorization resource collision", {"authorization_resource": "https://other.aau.invalid/mcp"}),
        ("mcp26-010", "Token resource collision", {"token_resource": "https://other.aau.invalid/mcp"}),
        ("mcp26-011", "Token audience collision", {"token_audience": "https://other.aau.invalid/mcp"}),
        ("mcp26-012", "Initial request asks for excess scope", {"requested_scopes": ["admin", "records:read"]}),
        ("mcp26-013", "Insufficient scope does not trigger step-up", {"insufficient_scope": True, "challenge_scopes": ["records:prepare"]}),
        ("mcp26-014", "Step-up drops the prior grant", {"requested_scopes": ["records:prepare"], "prior_scopes": ["records:read"], "challenge_scopes": ["records:prepare"], "insufficient_scope": True, "step_up_attempted": True}),
        ("mcp26-015", "Upstream token passthrough", {"token_passthrough": True}),
        ("mcp26-016", "Bearer token placed in query", {"token_in_query": True}),
    ]
    for case_id, title, changed in mutations:
        add(case_id, title, changed)
    return {
        "suite_version": SUITE_VERSION,
        "suite_id": f"mcp-2026-authorization-delta-{digest(profile)[:20]}",
        "profile_sha256": digest(profile),
        "cases": cases,
        "boundary": {
            "expected_answers_withheld_from_command_adapter": True,
            "no_credentials_payloads_or_tools": True,
            "recorded_delta_not_protocol_conformance": True,
        },
    }


def _command_adapter(command: str, timeout: float):
    argv = shlex.split(command)
    if not argv:
        raise McpDeltaError("adapter command is empty")

    def invoke(case_id: str, request: dict[str, Any]) -> tuple[str, list[str]]:
        payload = {"protocol_version": "aau-mcp-2026-adapter/1.0", "case_id": case_id, "request": request}
        try:
            completed = subprocess.run(
                argv, input=canonical(payload), capture_output=True, timeout=timeout, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise McpDeltaError(f"adapter execution failed: {exc}") from exc
        if completed.returncode != 0 or len(completed.stdout) > MAX_BYTES:
            raise McpDeltaError("adapter failed or returned an oversized response")
        try:
            response = json.loads(completed.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise McpDeltaError("adapter returned invalid JSON") from exc
        _exact(response, {"decision", "reason_codes"}, "adapter response")
        if response["decision"] not in {"allow", "block"}:
            raise McpDeltaError("adapter decision is invalid")
        reasons = _strings(response["reason_codes"], "reason_codes", empty=True)
        return response["decision"], reasons

    return invoke


def run_suite(
    profile: dict[str, Any], suite: dict[str, Any], adapter: str, command: str | None, timeout: float
) -> dict[str, Any]:
    expected_suite = generate_suite(profile)
    if suite != expected_suite:
        raise McpDeltaError("suite does not recompute from the exact profile")
    if adapter == "reference":
        def invoke(_case_id: str, request: dict[str, Any]) -> tuple[str, list[str]]:
            return evaluate_case(profile, request)
    elif adapter == "command" and command:
        invoke = _command_adapter(command, timeout)
    else:
        raise McpDeltaError("choose reference or provide a command adapter")
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
            "passing_not_mcp_oauth_security_or_compliance_conformance": True,
        },
    }


def verify_receipt(
    receipt: dict[str, Any], profile: dict[str, Any], suite: dict[str, Any]
) -> None:
    _exact(
        receipt,
        {
            "receipt_version",
            "suite_id",
            "profile_sha256",
            "suite_sha256",
            "adapter_kind",
            "status",
            "metrics",
            "results",
            "boundary",
        },
        "MCP delta receipt",
    )
    expected_suite = generate_suite(profile)
    if suite != expected_suite:
        raise McpDeltaError("suite does not recompute from the exact profile")
    adapter = receipt.get("adapter_kind")
    if adapter not in {"reference", "command"}:
        raise McpDeltaError("receipt adapter kind is invalid")
    if receipt["receipt_version"] != RECEIPT_VERSION or receipt["suite_id"] != suite["suite_id"]:
        raise McpDeltaError("receipt version or suite identity is invalid")
    if receipt.get("profile_sha256") != digest(profile) or receipt.get("suite_sha256") != digest(suite):
        raise McpDeltaError("receipt input digest mismatch")
    expected = {row["case_id"]: row for row in suite["cases"]}
    results = receipt.get("results")
    if (
        not isinstance(results, list)
        or len(results) != len(expected)
        or {row.get("case_id") for row in results} != set(expected)
    ):
        raise McpDeltaError("receipt case coverage is invalid")
    for row in results:
        _exact(
            row,
            {"case_id", "actual_decision", "actual_reason_codes", "exact"},
            "MCP delta result",
        )
        if row["actual_decision"] not in {"allow", "block"}:
            raise McpDeltaError("receipt decision is invalid")
        _strings(row["actual_reason_codes"], "actual_reason_codes", empty=True)
        if not isinstance(row["exact"], bool):
            raise McpDeltaError("receipt exact must be boolean")
        exact = row.get("actual_decision") == expected[row["case_id"]]["expected_decision"] and row.get(
            "actual_reason_codes"
        ) == expected[row["case_id"]]["expected_reason_codes"]
        if row.get("exact") is not exact:
            raise McpDeltaError("receipt exactness does not recompute")
    recomputed = run_suite(profile, suite, "reference", None, 1)
    exact_count = sum(row["exact"] for row in results)
    unsafe = sum(row["actual_decision"] == "allow" and expected[row["case_id"]]["expected_decision"] == "block" for row in results)
    legitimate = sum(row["actual_decision"] == "block" and expected[row["case_id"]]["expected_decision"] == "allow" for row in results)
    metrics = {**recomputed["metrics"], "exact_count": exact_count, "unsafe_allow_count": unsafe, "legitimate_block_count": legitimate}
    if receipt.get("metrics") != metrics:
        raise McpDeltaError("receipt metrics do not recompute")
    status = "evidence_passed" if exact_count == len(results) else "evidence_failed"
    if receipt.get("status") != status:
        raise McpDeltaError("receipt status does not recompute")
    expected_boundary = {
        "reference_adapter_is_self_test_only": adapter == "reference",
        "no_inputs_credentials_or_reasoning_retained": True,
        "passing_not_mcp_oauth_security_or_compliance_conformance": True,
    }
    if receipt["boundary"] != expected_boundary:
        raise McpDeltaError("receipt boundary is invalid")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Run the recorded MCP 2026 authorization delta gate")
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
            print(f"OK: {args.profile} targets MCP {PROTOCOL_VERSION}.")
        elif args.command == "generate":
            write_json(generate_suite(load_json(args.profile)), args.out)
            print(f"wrote {args.out}")
        elif args.command == "run":
            receipt = run_suite(
                load_json(args.profile),
                load_json(args.suite),
                "reference" if args.reference else "command",
                args.adapter_command,
                args.timeout,
            )
            write_json(receipt, args.out)
            print(f"wrote {args.out} ({receipt['metrics']['exact_count']}/{receipt['metrics']['case_count']} exact)")
            return 0 if receipt["status"] == "evidence_passed" else 1
        else:
            verify_receipt(load_json(args.receipt), load_json(args.profile), load_json(args.suite))
            print(f"verified {args.receipt}")
        return 0
    except (McpDeltaError, OSError) as exc:
        print(f"mcp 2026 delta: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
