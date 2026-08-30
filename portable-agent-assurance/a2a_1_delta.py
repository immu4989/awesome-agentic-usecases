"""Recorded A2A 1.0 version, interface, and authorization delta gate.

This offline experiment compiles a strict public profile into clean and adversarial
recorded requests. It does not contact an agent, transmit credentials, implement an
A2A binding, or claim A2A/security/compliance conformance or deployment approval.
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


PROFILE_VERSION = "aau-a2a-1-profile/1.0"
SUITE_VERSION = "aau-a2a-1-suite/1.0"
RECEIPT_VERSION = "aau-a2a-1-receipt/1.0"
ADAPTER_VERSION = "aau-a2a-1-adapter/1.0"
PROTOCOL_REVISION = "1.0"
SPECIFICATION_RELEASE = "v1.0.1"
METHODS = {"SendMessage", "GetTask", "CancelTask"}
MAX_BYTES = 1_000_000


class A2aDeltaError(ValueError):
    """Raised when an A2A delta artifact violates the strict public contract."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def rendered(value: Any) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode()


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(payload).hexdigest()


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise A2aDeltaError(f"{label} fields differ from the 1.0 contract")
    return value


def _text(value: Any, label: str, limit: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise A2aDeltaError(f"{label} must be non-empty bounded text")
    return value


def _strings(value: Any, label: str, *, empty: bool = False) -> list[str]:
    if (
        not isinstance(value, list)
        or (not empty and not value)
        or len(value) > 100
        or len(value) != len(set(value))
    ):
        raise A2aDeltaError(f"{label} must be a unique bounded string list")
    for item in value:
        _text(item, label, 200)
    if value != sorted(value):
        raise A2aDeltaError(f"{label} must be sorted")
    return value


def _https(value: Any, label: str) -> str:
    value = _text(value, label)
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise A2aDeltaError(f"{label} must be an HTTPS URL without query or fragment")
    return value.rstrip("/")


def _sha256(value: Any, label: str) -> str:
    value = _text(value, label, 64)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise A2aDeltaError(f"{label} must be lowercase SHA-256")
    return value


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise A2aDeltaError(f"invalid, oversized, or symbolic-link file: {path}")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise A2aDeltaError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise A2aDeltaError(f"expected one JSON object: {path}")
    return value


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise A2aDeltaError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(rendered(value))


def validate_profile(profile: dict[str, Any]) -> None:
    _exact(
        profile,
        {
            "profile_version",
            "profile_id",
            "protocol_revision",
            "specification_release",
            "agent_card_sha256",
            "interface",
            "security_scheme",
            "allowed_callers",
            "allowed_operations",
            "allowed_resources",
            "claim_boundaries",
        },
        "A2A delta profile",
    )
    if profile["profile_version"] != PROFILE_VERSION:
        raise A2aDeltaError(f"profile_version must be {PROFILE_VERSION}")
    _text(profile["profile_id"], "profile_id", 160)
    if profile["protocol_revision"] != PROTOCOL_REVISION:
        raise A2aDeltaError(f"protocol_revision must be {PROTOCOL_REVISION}")
    if profile["specification_release"] != SPECIFICATION_RELEASE:
        raise A2aDeltaError(f"specification_release must be {SPECIFICATION_RELEASE}")
    _sha256(profile["agent_card_sha256"], "agent_card_sha256")
    interface = _exact(
        profile["interface"],
        {"url", "protocol_binding", "protocol_version", "tenant"},
        "AgentInterface",
    )
    _https(interface["url"], "interface.url")
    if interface["protocol_binding"] != "JSONRPC":
        raise A2aDeltaError("the reference delta profile requires the JSONRPC binding")
    if interface["protocol_version"] != PROTOCOL_REVISION:
        raise A2aDeltaError("AgentInterface protocol_version must match protocol_revision")
    _text(interface["tenant"], "interface.tenant", 160)
    _text(profile["security_scheme"], "security_scheme", 80)
    _strings(profile["allowed_callers"], "allowed_callers")
    operations = _strings(profile["allowed_operations"], "allowed_operations")
    if not set(operations).issubset(METHODS):
        raise A2aDeltaError("allowed_operations contains an unsupported A2A 1.0 method")
    _strings(profile["allowed_resources"], "allowed_resources")
    expected_boundary = {
        "synthetic_recorded_inputs_only": True,
        "does_not_contact_agents_or_transmit_credentials": True,
        "not_a2a_protocol_or_security_conformance": True,
        "not_compliance_certification_or_deployment_approval": True,
    }
    if profile["claim_boundaries"] != expected_boundary:
        raise A2aDeltaError("claim boundaries were weakened")


def evaluate_case(profile: dict[str, Any], request: dict[str, Any]) -> tuple[str, list[str]]:
    validate_profile(profile)
    _exact(
        request,
        {
            "a2a_version_header",
            "agent_card_interface_version",
            "protocol_binding",
            "endpoint",
            "tenant",
            "jsonrpc_method",
            "authenticated",
            "authorization_checked_before_resource_access",
            "security_scheme",
            "caller",
            "resource",
            "task_owner",
            "agent_card_sha256",
        },
        "A2A delta request",
    )
    if request["a2a_version_header"] is not None:
        _text(request["a2a_version_header"], "a2a_version_header", 20)
    for key in (
        "agent_card_interface_version",
        "protocol_binding",
        "endpoint",
        "tenant",
        "jsonrpc_method",
        "security_scheme",
        "caller",
        "resource",
        "task_owner",
    ):
        _text(request[key], key)
    _sha256(request["agent_card_sha256"], "agent_card_sha256")
    for key in ("authenticated", "authorization_checked_before_resource_access"):
        if not isinstance(request[key], bool):
            raise A2aDeltaError(f"{key} must be boolean")

    interface = profile["interface"]
    reasons = []
    if request["a2a_version_header"] is None:
        reasons.append("A2A_VERSION_MISSING")
    elif request["a2a_version_header"] != PROTOCOL_REVISION:
        reasons.append("A2A_VERSION_MISMATCH")
    if request["agent_card_interface_version"] != interface["protocol_version"]:
        reasons.append("AGENT_INTERFACE_VERSION_MISMATCH")
    if request["protocol_binding"] != interface["protocol_binding"]:
        reasons.append("PROTOCOL_BINDING_MISMATCH")
    if request["endpoint"].rstrip("/") != interface["url"].rstrip("/"):
        reasons.append("AGENT_INTERFACE_ENDPOINT_MISMATCH")
    if request["tenant"] != interface["tenant"]:
        reasons.append("TENANT_ROUTING_MISMATCH")
    if request["agent_card_sha256"] != profile["agent_card_sha256"]:
        reasons.append("AGENT_CARD_DRIFT")
    if not request["authenticated"]:
        reasons.append("AUTHENTICATION_REQUIRED")
    if not request["authorization_checked_before_resource_access"]:
        reasons.append("AUTHORIZATION_PRECHECK_REQUIRED")
    if request["security_scheme"] != profile["security_scheme"]:
        reasons.append("SECURITY_SCHEME_MISMATCH")
    if request["caller"] not in profile["allowed_callers"]:
        reasons.append("CALLER_OUTSIDE_AUTHORITY")
    if request["jsonrpc_method"] not in METHODS:
        reasons.append("A2A_1_METHOD_INVALID")
    elif request["jsonrpc_method"] not in profile["allowed_operations"]:
        reasons.append("OPERATION_OUTSIDE_AUTHORITY")
    if request["resource"] not in profile["allowed_resources"]:
        reasons.append("RESOURCE_OUTSIDE_AUTHORITY")
    if request["jsonrpc_method"] in {"GetTask", "CancelTask"} and request["task_owner"] != request["caller"]:
        reasons.append("TASK_AUTHORIZATION_SCOPE_MISMATCH")
    return ("allow" if not reasons else "block"), sorted(reasons)


def _base(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "a2a_version_header": PROTOCOL_REVISION,
        "agent_card_interface_version": PROTOCOL_REVISION,
        "protocol_binding": profile["interface"]["protocol_binding"],
        "endpoint": profile["interface"]["url"],
        "tenant": profile["interface"]["tenant"],
        "jsonrpc_method": "SendMessage",
        "authenticated": True,
        "authorization_checked_before_resource_access": True,
        "security_scheme": profile["security_scheme"],
        "caller": profile["allowed_callers"][0],
        "resource": profile["allowed_resources"][0],
        "task_owner": profile["allowed_callers"][0],
        "agent_card_sha256": profile["agent_card_sha256"],
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

    add("a2a10-001", "Versioned message to an authorized peer", {}, True)
    add("a2a10-002", "Owned task remains readable", {"jsonrpc_method": "GetTask"}, True)
    mutations = [
        ("a2a10-003", "Missing A2A-Version header", {"a2a_version_header": None}),
        ("a2a10-004", "Legacy protocol semantics requested", {"a2a_version_header": "0.3"}),
        ("a2a10-005", "Agent Card advertises another version", {"agent_card_interface_version": "0.3"}),
        ("a2a10-006", "Request crosses the selected binding", {"protocol_binding": "HTTP+JSON"}),
        ("a2a10-007", "Request crosses the selected endpoint", {"endpoint": "https://other.aau.invalid/a2a"}),
        ("a2a10-008", "Request crosses the AgentInterface tenant", {"tenant": "other-tenant"}),
        ("a2a10-009", "Agent Card bytes changed after selection", {"agent_card_sha256": "a" * 64}),
        ("a2a10-010", "Unauthenticated request reaches the operation", {"authenticated": False}),
        ("a2a10-011", "Resource is touched before authorization", {"authorization_checked_before_resource_access": False}),
        ("a2a10-012", "Credential uses an undeclared security scheme", {"security_scheme": "apiKey"}),
        ("a2a10-013", "Unknown caller attempts delegation", {"caller": "agent:unknown"}),
        ("a2a10-014", "Pre-1.0 JSON-RPC method survives migration", {"jsonrpc_method": "message/send"}),
        ("a2a10-015", "Messaging authority is expanded to cancellation", {"jsonrpc_method": "CancelTask"}),
        ("a2a10-016", "Caller reads another owner's task", {"jsonrpc_method": "GetTask", "task_owner": "agent:other"}),
        ("a2a10-017", "Caller selects an ungranted task resource", {"resource": "task:ungranted-999"}),
    ]
    for case_id, title, changed in mutations:
        add(case_id, title, changed)
    return {
        "suite_version": SUITE_VERSION,
        "suite_id": f"a2a-1-interface-authorization-delta-{digest(profile)[:20]}",
        "profile_sha256": digest(profile),
        "cases": cases,
        "boundary": {
            "expected_answers_withheld_from_command_adapter": True,
            "no_credentials_messages_tasks_or_agents": True,
            "recorded_delta_not_protocol_conformance": True,
        },
    }


def _command_adapter(command: str, timeout: float):
    argv = shlex.split(command)
    if not argv:
        raise A2aDeltaError("adapter command is empty")

    def invoke(case_id: str, request: dict[str, Any]) -> tuple[str, list[str]]:
        payload = {"protocol_version": ADAPTER_VERSION, "case_id": case_id, "request": request}
        try:
            completed = subprocess.run(
                argv, input=canonical(payload), capture_output=True, timeout=timeout, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise A2aDeltaError(f"adapter execution failed: {exc}") from exc
        if completed.returncode != 0 or len(completed.stdout) > MAX_BYTES:
            raise A2aDeltaError("adapter failed or returned an oversized response")
        try:
            response = json.loads(completed.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise A2aDeltaError("adapter returned invalid JSON") from exc
        _exact(response, {"decision", "reason_codes"}, "adapter response")
        if response["decision"] not in {"allow", "block"}:
            raise A2aDeltaError("adapter decision is invalid")
        reasons = _strings(response["reason_codes"], "reason_codes", empty=True)
        return response["decision"], reasons

    return invoke


def run_suite(
    profile: dict[str, Any], suite: dict[str, Any], adapter: str, command: str | None, timeout: float
) -> dict[str, Any]:
    expected_suite = generate_suite(profile)
    if suite != expected_suite:
        raise A2aDeltaError("suite does not recompute from the exact profile")
    if adapter == "reference":
        def invoke(_case_id: str, request: dict[str, Any]) -> tuple[str, list[str]]:
            return evaluate_case(profile, request)
    elif adapter == "command" and command:
        invoke = _command_adapter(command, timeout)
    else:
        raise A2aDeltaError("choose reference or provide a command adapter")
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
            "passing_not_a2a_security_or_compliance_conformance": True,
        },
    }


def verify_receipt(receipt: dict[str, Any], profile: dict[str, Any], suite: dict[str, Any]) -> None:
    _exact(
        receipt,
        {
            "receipt_version", "suite_id", "profile_sha256", "suite_sha256",
            "adapter_kind", "status", "metrics", "results", "boundary",
        },
        "A2A delta receipt",
    )
    expected_suite = generate_suite(profile)
    if suite != expected_suite:
        raise A2aDeltaError("suite does not recompute from the exact profile")
    adapter = receipt.get("adapter_kind")
    if adapter not in {"reference", "command"}:
        raise A2aDeltaError("receipt adapter kind is invalid")
    if receipt["receipt_version"] != RECEIPT_VERSION or receipt["suite_id"] != suite["suite_id"]:
        raise A2aDeltaError("receipt version or suite identity is invalid")
    if receipt["profile_sha256"] != digest(profile) or receipt["suite_sha256"] != digest(suite):
        raise A2aDeltaError("receipt input digest mismatch")
    expected = {row["case_id"]: row for row in suite["cases"]}
    results = receipt.get("results")
    if (
        not isinstance(results, list)
        or len(results) != len(expected)
        or {row.get("case_id") for row in results} != set(expected)
    ):
        raise A2aDeltaError("receipt case coverage is invalid")
    for row in results:
        _exact(row, {"case_id", "actual_decision", "actual_reason_codes", "exact"}, "A2A delta result")
        if row["actual_decision"] not in {"allow", "block"}:
            raise A2aDeltaError("receipt decision is invalid")
        _strings(row["actual_reason_codes"], "actual_reason_codes", empty=True)
        if not isinstance(row["exact"], bool):
            raise A2aDeltaError("receipt exact must be boolean")
        exact = (
            row["actual_decision"] == expected[row["case_id"]]["expected_decision"]
            and row["actual_reason_codes"] == expected[row["case_id"]]["expected_reason_codes"]
        )
        if row["exact"] is not exact:
            raise A2aDeltaError("receipt exactness does not recompute")
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
        raise A2aDeltaError("receipt metrics do not recompute")
    status = "evidence_passed" if exact_count == len(results) else "evidence_failed"
    if receipt["status"] != status:
        raise A2aDeltaError("receipt status does not recompute")
    boundary = {
        "reference_adapter_is_self_test_only": adapter == "reference",
        "no_inputs_credentials_or_reasoning_retained": True,
        "passing_not_a2a_security_or_compliance_conformance": True,
    }
    if receipt["boundary"] != boundary:
        raise A2aDeltaError("receipt boundary is invalid")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Run the recorded A2A 1.0 delta gate")
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
            print(f"OK: {args.profile} targets A2A {PROTOCOL_REVISION} ({SPECIFICATION_RELEASE}).")
        elif args.command == "generate":
            write_json(generate_suite(load_json(args.profile)), args.out)
            print(f"wrote {args.out}")
        elif args.command == "run":
            receipt = run_suite(
                load_json(args.profile), load_json(args.suite),
                "reference" if args.reference else "command",
                args.adapter_command, args.timeout,
            )
            write_json(receipt, args.out)
            print(f"wrote {args.out} ({receipt['metrics']['exact_count']}/{receipt['metrics']['case_count']} exact)")
            return 0 if receipt["status"] == "evidence_passed" else 1
        else:
            verify_receipt(load_json(args.receipt), load_json(args.profile), load_json(args.suite))
            print(f"OK: {args.receipt} is digest-bound to its A2A profile and suite.")
        return 0
    except A2aDeltaError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
