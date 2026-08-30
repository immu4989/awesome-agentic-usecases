"""Portable Agent Assurance Envelope reference verifier.

This module is an offline, dependency-free conformance testbed. It verifies synthetic
HS256 identity fixtures, normalizes recorded MCP and A2A requests, evaluates an
expiring authority envelope, and emits recomputable receipts. It does not operate an
identity provider, trust a production credential, execute a tool, or authorize a live
action.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import hmac
import json
import re
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENVELOPE_VERSION = "aau-agent-assurance-envelope/0.1"
SUITE_VERSION = "aau-agent-assurance-suite/0.1"
RECEIPT_VERSION = "aau-agent-assurance-receipt/0.1"
PACK_VERSION = "aau-agent-assurance-pack/0.1"
OTEL_VERSION = "aau-agent-assurance-otel/0.1"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://immu4989.github.io/awesome-agentic-usecases/agent-assurance/v0.1"
MAX_BYTES = 1_000_000
MAX_CASES = 500
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SPIFFE_ID = re.compile(r"^spiffe://[a-z0-9.-]+(?:/[A-Za-z0-9._-]+)*$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")


class AssuranceError(ValueError):
    """Raised for a malformed or unverifiable public assurance artifact."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(value: Any) -> str:
    return digest_bytes(canonical_bytes(value))


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise AssuranceError("JWT segment must be non-empty text")
    try:
        encoded = value.encode("ascii")
        return base64.b64decode(
            encoded + b"=" * (-len(encoded) % 4), altchars=b"-_", validate=True
        )
    except (UnicodeEncodeError, ValueError, base64.binascii.Error) as exc:
        raise AssuranceError("JWT segment is not valid base64url") from exc


def _timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise AssuranceError(f"{label} must be an RFC 3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise AssuranceError(f"{label} must be an RFC 3339 UTC timestamp") from exc
    if parsed.tzinfo != timezone.utc:
        raise AssuranceError(f"{label} must use UTC")
    return parsed


def _text(value: Any, label: str, limit: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise AssuranceError(f"{label} must be non-empty text no longer than {limit} characters")
    return value.strip()


def _identifier(value: Any, label: str) -> str:
    text = _text(value, label, 160)
    if not SAFE_ID.fullmatch(text):
        raise AssuranceError(f"{label} contains unsupported characters")
    return text


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AssuranceError(f"refusing non-regular JSON file: {path}")
    if path.stat().st_size > MAX_BYTES:
        raise AssuranceError(f"JSON file exceeds {MAX_BYTES} bytes: {path}")
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssuranceError(f"cannot read JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise AssuranceError(f"JSON root must be an object: {path}")
    return value


def _exact_keys(value: dict[str, Any], required: set[str], optional: set[str], label: str) -> None:
    missing = sorted(required - set(value))
    extra = sorted(set(value) - required - optional)
    if missing or extra:
        raise AssuranceError(f"{label} keys differ; missing={missing}, unexpected={extra}")


def validate_envelope(envelope: dict[str, Any]) -> None:
    _exact_keys(
        envelope,
        {
            "envelope_version",
            "envelope_id",
            "issued_at",
            "expires_at",
            "classification",
            "subject",
            "authority",
            "protocols",
            "evidence",
            "telemetry",
            "claim_boundaries",
        },
        set(),
        "envelope",
    )
    if envelope["envelope_version"] != ENVELOPE_VERSION:
        raise AssuranceError(f"envelope_version must be {ENVELOPE_VERSION}")
    _identifier(envelope["envelope_id"], "envelope_id")
    issued = _timestamp(envelope["issued_at"], "issued_at")
    expires = _timestamp(envelope["expires_at"], "expires_at")
    if expires <= issued:
        raise AssuranceError("expires_at must follow issued_at")
    classification = envelope["classification"]
    if classification != {
        "data": "synthetic",
        "live_system": False,
        "test_credentials_only": True,
    }:
        raise AssuranceError("the reference verifier accepts only explicit synthetic test fixtures")

    subject = envelope["subject"]
    if not isinstance(subject, dict):
        raise AssuranceError("subject must be an object")
    _exact_keys(
        subject,
        {"agent_id", "operator_ref", "workload_identity", "identity_verifier"},
        set(),
        "subject",
    )
    _identifier(subject["agent_id"], "subject.agent_id")
    _identifier(subject["operator_ref"], "subject.operator_ref")
    workload = subject["workload_identity"]
    if not isinstance(workload, dict):
        raise AssuranceError("subject.workload_identity must be an object")
    _exact_keys(workload, {"kind", "identifier"}, set(), "subject.workload_identity")
    if workload["kind"] != "spiffe":
        raise AssuranceError("reference workload_identity.kind must be spiffe")
    if not isinstance(workload["identifier"], str) or not SPIFFE_ID.fullmatch(workload["identifier"]):
        raise AssuranceError("workload identity must be a normalized SPIFFE ID")
    verifier = subject["identity_verifier"]
    if not isinstance(verifier, dict):
        raise AssuranceError("subject.identity_verifier must be an object")
    _exact_keys(
        verifier,
        {"mode", "algorithm", "issuer", "audience", "key_id", "test_only_shared_secret"},
        set(),
        "subject.identity_verifier",
    )
    if verifier["mode"] != "synthetic_local_fixture" or verifier["algorithm"] != "HS256":
        raise AssuranceError("reference identity verifier must be the synthetic HS256 fixture")
    for key in ("issuer", "audience", "key_id", "test_only_shared_secret"):
        _text(verifier[key], f"subject.identity_verifier.{key}", 300)
    if len(verifier["test_only_shared_secret"].encode()) < 32:
        raise AssuranceError("test_only_shared_secret must contain at least 32 bytes")

    authority = envelope["authority"]
    if not isinstance(authority, dict):
        raise AssuranceError("authority must be an object")
    _exact_keys(
        authority,
        {
            "lease_id",
            "task_id",
            "policy_epoch",
            "valid_from",
            "valid_until",
            "revocation_state",
            "human_owner_ref",
            "allowed_actions",
            "allowed_peers",
            "delegation",
            "monitoring_required",
        },
        set(),
        "authority",
    )
    _identifier(authority["lease_id"], "authority.lease_id")
    _identifier(authority["task_id"], "authority.task_id")
    _identifier(authority["human_owner_ref"], "authority.human_owner_ref")
    if type(authority["policy_epoch"]) is not int or authority["policy_epoch"] < 1:
        raise AssuranceError("authority.policy_epoch must be a positive integer")
    valid_from = _timestamp(authority["valid_from"], "authority.valid_from")
    valid_until = _timestamp(authority["valid_until"], "authority.valid_until")
    if valid_from < issued or valid_until > expires or valid_until <= valid_from:
        raise AssuranceError("authority validity must be a non-empty subset of envelope validity")
    if authority["revocation_state"] not in {"active", "revoked"}:
        raise AssuranceError("authority.revocation_state must be active or revoked")
    if authority["monitoring_required"] is not True:
        raise AssuranceError("reference authority must require monitoring")
    actions = authority["allowed_actions"]
    if not isinstance(actions, list) or not actions or len(actions) > 100:
        raise AssuranceError("authority.allowed_actions must be a non-empty bounded list")
    seen_actions: set[tuple[str, str, str, str]] = set()
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            raise AssuranceError(f"allowed_actions[{index}] must be an object")
        _exact_keys(action, {"protocol", "operation", "resource", "destination"}, set(), f"allowed_actions[{index}]")
        if action["protocol"] not in {"mcp", "a2a"}:
            raise AssuranceError("allowed action protocol must be mcp or a2a")
        row = (
            action["protocol"],
            _text(action["operation"], "allowed action operation", 160),
            _text(action["resource"], "allowed action resource", 300),
            _text(action["destination"], "allowed action destination", 300),
        )
        if row in seen_actions:
            raise AssuranceError("allowed action entries must be unique")
        seen_actions.add(row)
    peers = authority["allowed_peers"]
    if not isinstance(peers, list) or len(peers) > 50:
        raise AssuranceError("authority.allowed_peers must be a unique bounded list")
    for peer in peers:
        _identifier(peer, "allowed peer")
    if len(set(peers)) != len(peers):
        raise AssuranceError("authority.allowed_peers must be a unique bounded list")
    delegation = authority["delegation"]
    if not isinstance(delegation, dict):
        raise AssuranceError("authority.delegation must be an object")
    _exact_keys(delegation, {"allowed", "max_depth", "operations"}, set(), "authority.delegation")
    if delegation["allowed"] is not True or delegation["max_depth"] != 1:
        raise AssuranceError("reference delegation permits exactly one level")
    operations = delegation["operations"]
    if not isinstance(operations, list) or not operations or len(operations) > 100:
        raise AssuranceError("delegation.operations must be a non-empty list")
    for operation in operations:
        _text(operation, "delegation operation", 160)
    if len(set(operations)) != len(operations):
        raise AssuranceError("delegation.operations must be unique")
    if not set(operations).issubset({row[1] for row in seen_actions}):
        raise AssuranceError("delegation.operations must be granted allowed-action operations")

    protocols = envelope["protocols"]
    if not isinstance(protocols, dict):
        raise AssuranceError("protocols must be an object")
    _exact_keys(protocols, {"mcp", "a2a"}, set(), "protocols")
    if protocols["mcp"].get("authorization_profile") != "oauth-resource-bound-recorded-fixture":
        raise AssuranceError("MCP authorization profile is invalid")
    if protocols["mcp"].get("token_passthrough_forbidden") is not True:
        raise AssuranceError("MCP token passthrough must be forbidden")
    if protocols["a2a"].get("authorization_per_request") is not True:
        raise AssuranceError("A2A authorization must be required per request")
    card_digest = protocols["a2a"].get("agent_card_sha256")
    if not isinstance(card_digest, str) or not HEX64.fullmatch(card_digest):
        raise AssuranceError("A2A agent card digest must be lowercase SHA-256")

    evidence = envelope["evidence"]
    if not isinstance(evidence, dict):
        raise AssuranceError("evidence must be an object")
    _exact_keys(
        evidence,
        {"boundary_profile_sha256", "evaluation_receipt_sha256", "independent_reproduction"},
        set(),
        "evidence",
    )
    for key in ("boundary_profile_sha256", "evaluation_receipt_sha256"):
        if evidence[key] is not None and (not isinstance(evidence[key], str) or not HEX64.fullmatch(evidence[key])):
            raise AssuranceError(f"evidence.{key} must be null or lowercase SHA-256")
    reproduction = evidence["independent_reproduction"]
    if reproduction not in {"not_provided", "protocol_demonstration", "independence_reviewed"}:
        raise AssuranceError("independent reproduction state is invalid")

    telemetry = envelope["telemetry"]
    if telemetry != {
        "format": "opentelemetry-compatible-json",
        "include_prompts": False,
        "include_credentials": False,
        "include_personal_data": False,
    }:
        raise AssuranceError("telemetry must remain metadata-only and privacy bounded")
    boundaries = envelope["claim_boundaries"]
    expected_boundaries = {
        "not_certification": True,
        "not_compliance_finding": True,
        "not_authorization_to_operate": True,
        "not_government_endorsement": True,
        "production_identity_not_verified": True,
        "no_live_action_authorized": True,
    }
    if boundaries != expected_boundaries:
        raise AssuranceError("claim_boundaries must preserve every non-claim")


def mint_test_token(envelope: dict[str, Any], *, jti: str, issued_at: str, expires_at: str) -> str:
    """Mint an explicitly synthetic token for committed conformance fixtures."""

    validate_envelope(envelope)
    verifier = envelope["subject"]["identity_verifier"]
    authority = envelope["authority"]
    header = {"alg": "HS256", "kid": verifier["key_id"], "typ": "JWT"}
    claims = {
        "iss": verifier["issuer"],
        "aud": verifier["audience"],
        "sub": envelope["subject"]["workload_identity"]["identifier"],
        "agent_id": envelope["subject"]["agent_id"],
        "operator_ref": envelope["subject"]["operator_ref"],
        "authority_ref": authority["lease_id"],
        "task_id": authority["task_id"],
        "policy_epoch": authority["policy_epoch"],
        "jti": _identifier(jti, "jti"),
        "iat": int(_timestamp(issued_at, "issued_at").timestamp()),
        "exp": int(_timestamp(expires_at, "expires_at").timestamp()),
        "synthetic_fixture": True,
    }
    signing_input = f"{_b64url(canonical_bytes(header))}.{_b64url(canonical_bytes(claims))}"
    signature = hmac.new(
        verifier["test_only_shared_secret"].encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    return f"{signing_input}.{_b64url(signature)}"


def verify_test_token(envelope: dict[str, Any], token: Any, occurred_at: Any) -> tuple[dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    if not isinstance(token, str) or token.count(".") != 2:
        return None, ["IDENTITY_TOKEN_MALFORMED"]
    encoded_header, encoded_claims, encoded_signature = token.split(".")
    try:
        header = json.loads(_b64decode(encoded_header))
        claims = json.loads(_b64decode(encoded_claims))
        signature = _b64decode(encoded_signature)
    except (AssuranceError, UnicodeDecodeError, json.JSONDecodeError):
        return None, ["IDENTITY_TOKEN_MALFORMED"]
    if not isinstance(header, dict) or not isinstance(claims, dict):
        return None, ["IDENTITY_TOKEN_MALFORMED"]
    verifier = envelope["subject"]["identity_verifier"]
    expected = hmac.new(
        verifier["test_only_shared_secret"].encode(),
        f"{encoded_header}.{encoded_claims}".encode(),
        hashlib.sha256,
    ).digest()
    if header != {"alg": "HS256", "kid": verifier["key_id"], "typ": "JWT"}:
        reasons.append("IDENTITY_TOKEN_HEADER_INVALID")
    if not hmac.compare_digest(signature, expected):
        reasons.append("IDENTITY_SIGNATURE_INVALID")
    now = int(_timestamp(occurred_at, "request.occurred_at").timestamp())
    expected_claims = {
        "iss": verifier["issuer"],
        "aud": verifier["audience"],
        "sub": envelope["subject"]["workload_identity"]["identifier"],
        "agent_id": envelope["subject"]["agent_id"],
        "operator_ref": envelope["subject"]["operator_ref"],
        "authority_ref": envelope["authority"]["lease_id"],
        "task_id": envelope["authority"]["task_id"],
        "policy_epoch": envelope["authority"]["policy_epoch"],
        "synthetic_fixture": True,
    }
    claim_codes = {
        "iss": "IDENTITY_ISSUER_MISMATCH",
        "aud": "TOKEN_AUDIENCE_MISMATCH",
        "sub": "WORKLOAD_IDENTITY_MISMATCH",
        "agent_id": "AGENT_IDENTITY_MISMATCH",
        "operator_ref": "OPERATOR_BINDING_MISMATCH",
        "authority_ref": "TOKEN_AUTHORITY_MISMATCH",
        "task_id": "TOKEN_TASK_MISMATCH",
        "policy_epoch": "TOKEN_POLICY_EPOCH_MISMATCH",
        "synthetic_fixture": "TOKEN_FIXTURE_MARKER_MISSING",
    }
    for key, expected_value in expected_claims.items():
        if claims.get(key) != expected_value:
            reasons.append(claim_codes[key])
    required_claims = set(expected_claims) | {"jti", "iat", "exp"}
    if set(claims) != required_claims:
        reasons.append("IDENTITY_TOKEN_CLAIMS_INVALID")
    if not isinstance(claims.get("jti"), str) or not claims["jti"]:
        reasons.append("TOKEN_JTI_MISSING")
    issued = claims.get("iat")
    expires = claims.get("exp")
    if type(issued) is not int or issued > now:
        reasons.append("TOKEN_NOT_YET_VALID")
    if type(expires) is not int or expires <= now:
        reasons.append("TOKEN_EXPIRED")
    if type(issued) is int and type(expires) is int:
        if expires <= issued:
            reasons.append("TOKEN_INTERVAL_INVALID")
        envelope_start = int(_timestamp(envelope["issued_at"], "issued_at").timestamp())
        envelope_end = int(_timestamp(envelope["expires_at"], "expires_at").timestamp())
        if issued < envelope_start or expires > envelope_end:
            reasons.append("TOKEN_INTERVAL_OUTSIDE_ENVELOPE")
    return claims, sorted(set(reasons))


def validate_suite(suite: dict[str, Any]) -> None:
    _exact_keys(suite, {"suite_version", "suite_id", "title", "envelope_sha256", "cases"}, set(), "suite")
    if suite["suite_version"] != SUITE_VERSION:
        raise AssuranceError(f"suite_version must be {SUITE_VERSION}")
    _identifier(suite["suite_id"], "suite_id")
    _text(suite["title"], "suite.title", 300)
    if not isinstance(suite["envelope_sha256"], str) or not HEX64.fullmatch(suite["envelope_sha256"]):
        raise AssuranceError("suite.envelope_sha256 must be lowercase SHA-256")
    cases = suite["cases"]
    if not isinstance(cases, list) or not cases or len(cases) > MAX_CASES:
        raise AssuranceError("suite.cases must be a non-empty bounded list")
    ids: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise AssuranceError(f"cases[{index}] must be an object")
        _exact_keys(case, {"case_id", "title", "clean_twin", "record", "expected"}, set(), f"cases[{index}]")
        case_id = _identifier(case["case_id"], f"cases[{index}].case_id")
        if case_id in ids:
            raise AssuranceError("case ids must be unique")
        ids.add(case_id)
        _text(case["title"], f"cases[{index}].title", 300)
        if not isinstance(case["clean_twin"], bool):
            raise AssuranceError("clean_twin must be boolean")
        if not isinstance(case["record"], dict):
            raise AssuranceError("case.record must be an object")
        expected = case["expected"]
        if not isinstance(expected, dict) or set(expected) != {"outcome", "reason_codes"}:
            raise AssuranceError("case.expected keys must be outcome and reason_codes")
        if expected["outcome"] not in {"allow", "block", "pause"}:
            raise AssuranceError("expected outcome must be allow, block, or pause")
        reason_codes = expected["reason_codes"]
        if not isinstance(reason_codes, list) or any(not isinstance(code, str) for code in reason_codes):
            raise AssuranceError("expected reason_codes must be a sorted unique list")
        if reason_codes != sorted(set(reason_codes)):
            raise AssuranceError("expected reason_codes must be a sorted unique list")
        if case["clean_twin"] and (expected["outcome"] != "allow" or reason_codes):
            raise AssuranceError("clean twins must precommit allow with no reason codes")
    twin_count = sum(1 for case in cases if case["clean_twin"])
    if twin_count < 2:
        raise AssuranceError("suite must preserve at least two clean twins")


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    if set(record) != {"protocol", "context", "request"}:
        raise AssuranceError("record has missing or unexpected fields")
    protocol = record.get("protocol")
    context = record.get("context")
    request = record.get("request")
    if protocol not in {"mcp", "a2a"} or not isinstance(context, dict) or not isinstance(request, dict):
        raise AssuranceError("record requires protocol, context, and request objects")
    required_context = {
        "occurred_at",
        "agent_id",
        "authority_ref",
        "task_id",
        "policy_epoch",
        "token",
        "monitoring_active",
        "delegation_depth",
        "delegated_operations",
    }
    if set(context) != required_context:
        raise AssuranceError("record.context has missing or unexpected fields")
    normalized = copy.deepcopy(context)
    normalized["protocol"] = protocol
    if protocol == "mcp":
        if set(request) != {"jsonrpc", "method", "params"}:
            raise AssuranceError("MCP request has missing or unexpected fields")
        if request.get("jsonrpc") != "2.0" or request.get("method") != "tools/call":
            raise AssuranceError("MCP record must be one recorded JSON-RPC tools/call")
        params = request.get("params")
        if not isinstance(params, dict) or not isinstance(params.get("arguments"), dict):
            raise AssuranceError("MCP request params and arguments must be objects")
        if set(params) != {"name", "arguments"}:
            raise AssuranceError("MCP params have missing or unexpected fields")
        if set(params["arguments"]) - {"resource", "destination", "peer", "token_passthrough"}:
            raise AssuranceError("MCP arguments contain unsupported fields")
        name = _text(params.get("name"), "MCP tool name", 160)
        if "." not in name:
            raise AssuranceError("MCP tool name must use <tool>.<operation>")
        tool, operation = name.rsplit(".", 1)
        arguments = params["arguments"]
        normalized.update(
            {
                "operation": f"{tool}.{operation}",
                "resource": str(arguments.get("resource", "")),
                "destination": str(arguments.get("destination", "")),
                "peer": str(arguments.get("peer", "")),
                "token_passthrough": arguments.get("token_passthrough", False),
                "agent_card_sha256": None,
            }
        )
    else:
        if set(request) != {"method", "params"}:
            raise AssuranceError("A2A request has missing or unexpected fields")
        if request.get("method") not in {"message/send", "tasks/get", "tasks/cancel"}:
            raise AssuranceError("A2A record method is unsupported")
        params = request.get("params")
        if not isinstance(params, dict):
            raise AssuranceError("A2A request params must be an object")
        if set(params) != {
            "resource",
            "destination",
            "peer",
            "agent_card_sha256",
            "token_passthrough",
        }:
            raise AssuranceError("A2A params have missing or unexpected fields")
        normalized.update(
            {
                "operation": request["method"],
                "resource": str(params.get("resource", "")),
                "destination": str(params.get("destination", "")),
                "peer": str(params.get("peer", "")),
                "token_passthrough": params.get("token_passthrough", False),
                "agent_card_sha256": params.get("agent_card_sha256"),
            }
        )
    return normalized


def evaluate_record(envelope: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_record(record)
    authority = envelope["authority"]
    reasons: list[str] = []
    _, token_reasons = verify_test_token(envelope, normalized["token"], normalized["occurred_at"])
    reasons.extend(token_reasons)
    occurred = _timestamp(normalized["occurred_at"], "request.occurred_at")
    if occurred < _timestamp(authority["valid_from"], "authority.valid_from") or occurred >= _timestamp(authority["valid_until"], "authority.valid_until"):
        reasons.append("AUTHORITY_LEASE_INACTIVE")
    if authority["revocation_state"] == "revoked":
        reasons.append("AUTHORITY_REVOKED")
    if normalized["agent_id"] != envelope["subject"]["agent_id"]:
        reasons.append("AGENT_IDENTITY_MISMATCH")
    if normalized["authority_ref"] != authority["lease_id"]:
        reasons.append("AUTHORITY_REF_INVALID")
    if normalized["task_id"] != authority["task_id"]:
        reasons.append("TASK_MISMATCH")
    if normalized["policy_epoch"] != authority["policy_epoch"]:
        reasons.append("STALE_POLICY_EPOCH")
    if not isinstance(normalized["monitoring_active"], bool):
        reasons.append("MONITORING_STATE_INVALID")
    elif not normalized["monitoring_active"]:
        reasons.append("MONITORING_UNAVAILABLE")
    if normalized["token_passthrough"] is not False:
        reasons.append("TOKEN_PASSTHROUGH_FORBIDDEN")
    if normalized["protocol"] == "a2a" and normalized["agent_card_sha256"] != envelope["protocols"]["a2a"]["agent_card_sha256"]:
        reasons.append("AGENT_CARD_DRIFT")
    if normalized["protocol"] == "a2a" and normalized["peer"] not in authority["allowed_peers"]:
        reasons.append("UNAUTHORIZED_PEER")

    allowed = {
        (item["protocol"], item["operation"], item["resource"], item["destination"])
        for item in authority["allowed_actions"]
    }
    requested = (
        normalized["protocol"],
        normalized["operation"],
        normalized["resource"],
        normalized["destination"],
    )
    if requested not in allowed:
        reasons.append("ACTION_OUTSIDE_AUTHORITY")
    depth = normalized["delegation_depth"]
    delegated = normalized["delegated_operations"]
    if type(depth) is not int or depth < 0:
        reasons.append("DELEGATION_DEPTH_INVALID")
    elif depth > authority["delegation"]["max_depth"]:
        reasons.append("DELEGATION_DEPTH_EXCEEDED")
    if not isinstance(delegated, list) or any(not isinstance(item, str) for item in delegated):
        reasons.append("DELEGATION_SCOPE_INVALID")
    elif not set(delegated).issubset(set(authority["delegation"]["operations"])):
        reasons.append("DELEGATION_SCOPE_WIDENED")

    reasons = sorted(set(reasons))
    if reasons == ["MONITORING_UNAVAILABLE"]:
        outcome = "pause"
    elif reasons:
        outcome = "block"
    else:
        outcome = "allow"
    return {
        "outcome": outcome,
        "reason_codes": reasons,
        "normalized_request": {
            key: value
            for key, value in normalized.items()
            if key not in {"token"}
        },
        "identity_fixture_verified": not token_reasons,
        "production_identity_verified": False,
    }


def evaluate_suite(envelope: dict[str, Any], suite: dict[str, Any]) -> dict[str, Any]:
    validate_envelope(envelope)
    validate_suite(suite)
    envelope_sha = digest(envelope)
    if suite["envelope_sha256"] != envelope_sha:
        raise AssuranceError("suite is not bound to the supplied envelope")
    results = []
    previous = "0" * 64
    for case in suite["cases"]:
        observed = evaluate_record(envelope, case["record"])
        exact = observed["outcome"] == case["expected"]["outcome"] and observed["reason_codes"] == case["expected"]["reason_codes"]
        row = {
            "case_id": case["case_id"],
            "clean_twin": case["clean_twin"],
            "expected": copy.deepcopy(case["expected"]),
            "observed": observed,
            "exact": exact,
            "previous_result_sha256": previous,
        }
        row["result_sha256"] = digest(row)
        previous = row["result_sha256"]
        results.append(row)
    exact_count = sum(1 for row in results if row["exact"])
    clean_twins = [row for row in results if row["clean_twin"]]
    receipt = {
        "receipt_version": RECEIPT_VERSION,
        "envelope_id": envelope["envelope_id"],
        "envelope_sha256": envelope_sha,
        "suite_id": suite["suite_id"],
        "suite_sha256": digest(suite),
        "summary": {
            "case_count": len(results),
            "exact_count": exact_count,
            "exact_rate": round(exact_count / len(results), 6),
            "clean_twin_count": len(clean_twins),
            "clean_twin_allow_count": sum(1 for row in clean_twins if row["observed"]["outcome"] == "allow"),
            "identity_fixture_verified_count": sum(1 for row in results if row["observed"]["identity_fixture_verified"]),
            "production_identity_verified_count": 0,
        },
        "results": results,
        "result_chain_head_sha256": previous,
        "claim_boundaries": copy.deepcopy(envelope["claim_boundaries"]),
    }
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def verify_receipt(receipt: dict[str, Any], envelope: dict[str, Any], suite: dict[str, Any]) -> None:
    expected = evaluate_suite(envelope, suite)
    if receipt != expected:
        raise AssuranceError("receipt differs from deterministic recomputation")


def export_otel(receipt: dict[str, Any]) -> dict[str, Any]:
    events = []
    for row in receipt["results"]:
        observed = row["observed"]
        normalized = observed["normalized_request"]
        events.append(
            {
                "name": "aau.agent.authority.decision",
                "time_unix_nano": str(int(_timestamp(normalized["occurred_at"], "occurred_at").timestamp()) * 1_000_000_000),
                "attributes": {
                    "gen_ai.agent.id": normalized["agent_id"],
                    "aau.assurance.envelope_id": receipt["envelope_id"],
                    "aau.assurance.case_id": row["case_id"],
                    "aau.assurance.protocol": normalized["protocol"],
                    "aau.assurance.operation": normalized["operation"],
                    "aau.assurance.decision": observed["outcome"],
                    "aau.assurance.reason_codes": observed["reason_codes"],
                    "aau.assurance.production_identity_verified": False,
                },
            }
        )
    return {
        "format_version": OTEL_VERSION,
        "scope": {"name": "org.aau.agent-assurance", "version": "0.1"},
        "privacy": {"prompts_included": False, "credentials_included": False, "personal_data_included": False},
        "events": events,
    }


def in_toto_statement(receipt: dict[str, Any]) -> dict[str, Any]:
    subject_bytes = canonical_bytes(receipt)
    return {
        "_type": STATEMENT_TYPE,
        "subject": [{"name": "receipt.json", "digest": {"sha256": digest_bytes(subject_bytes)}}],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "envelope_sha256": receipt["envelope_sha256"],
            "suite_sha256": receipt["suite_sha256"],
            "result_chain_head_sha256": receipt["result_chain_head_sha256"],
            "production_identity_verified": False,
            "signature_status": "unsigned_local_statement",
        },
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n")


def build_pack(envelope_path: Path, suite_path: Path, out: Path) -> dict[str, Any]:
    if out.exists():
        raise AssuranceError(f"refusing to overwrite existing path: {out}")
    envelope = load_json(envelope_path)
    suite = load_json(suite_path)
    receipt = evaluate_suite(envelope, suite)
    otel = export_otel(receipt)
    statement = in_toto_statement(receipt)
    out.mkdir(parents=False)
    try:
        _write_json(out / "envelope.json", envelope)
        _write_json(out / "suite.json", suite)
        _write_json(out / "receipt.json", receipt)
        _write_json(out / "otel-events.json", otel)
        _write_json(out / "statement.intoto.json", statement)
        readme = (
            "# Portable Agent Assurance pack\n\n"
            f"Envelope: `{envelope['envelope_id']}`\n\n"
            f"Cases: **{receipt['summary']['case_count']}** · exact: **{receipt['summary']['exact_count']}**\n\n"
            "This is an offline synthetic conformance result. The HS256 credential is a public test "
            "fixture. It does not verify a production identity, certify a system, establish compliance, "
            "authorize a live action, or represent government endorsement.\n"
        )
        (out / "README.md").write_text(readme)
        names = ["README.md", "envelope.json", "otel-events.json", "receipt.json", "statement.intoto.json", "suite.json"]
        files = []
        for name in names:
            data = (out / name).read_bytes()
            files.append({"path": name, "sha256": digest_bytes(data), "size": len(data)})
        manifest = {"pack_version": PACK_VERSION, "files": files}
        _write_json(out / "manifest.json", manifest)
        return {"pack": str(out), "receipt_sha256": receipt["receipt_sha256"], "case_count": receipt["summary"]["case_count"]}
    except Exception:
        shutil.rmtree(out)
        raise


def verify_pack(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_dir():
        raise AssuranceError("pack must be a regular directory")
    expected_names = {
        "README.md",
        "envelope.json",
        "manifest.json",
        "otel-events.json",
        "receipt.json",
        "statement.intoto.json",
        "suite.json",
    }
    actual_names = {item.name for item in path.iterdir()}
    if actual_names != expected_names:
        raise AssuranceError(f"pack file set differs; missing={sorted(expected_names-actual_names)}, unexpected={sorted(actual_names-expected_names)}")
    for item in path.iterdir():
        mode = item.lstat().st_mode
        if item.is_symlink() or not stat.S_ISREG(mode):
            raise AssuranceError(f"pack entry is not a regular file: {item.name}")
        if item.stat().st_size > MAX_BYTES:
            raise AssuranceError(f"pack entry exceeds {MAX_BYTES} bytes: {item.name}")
    manifest = load_json(path / "manifest.json")
    if manifest.get("pack_version") != PACK_VERSION or not isinstance(manifest.get("files"), list):
        raise AssuranceError("manifest is malformed")
    rows = manifest["files"]
    if any(not isinstance(row, dict) for row in rows):
        raise AssuranceError("manifest file entries must be objects")
    if [row.get("path") for row in rows] != sorted(expected_names - {"manifest.json"}):
        raise AssuranceError("manifest must list every non-manifest file exactly once in sorted order")
    for row in rows:
        name = row["path"]
        data = (path / name).read_bytes()
        if row != {"path": name, "sha256": digest_bytes(data), "size": len(data)}:
            raise AssuranceError(f"manifest binding differs for {name}")
    envelope = load_json(path / "envelope.json")
    suite = load_json(path / "suite.json")
    receipt = load_json(path / "receipt.json")
    verify_receipt(receipt, envelope, suite)
    if load_json(path / "otel-events.json") != export_otel(receipt):
        raise AssuranceError("OpenTelemetry export differs from recomputation")
    if load_json(path / "statement.intoto.json") != in_toto_statement(receipt):
        raise AssuranceError("in-toto statement differs from recomputation")
    return {
        "status": "verified_synthetic_conformance",
        "envelope_id": envelope["envelope_id"],
        "case_count": receipt["summary"]["case_count"],
        "exact_count": receipt["summary"]["exact_count"],
        "production_identity_verified": False,
    }


def _emit(value: Any, out: Path | None = None) -> None:
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if out is None:
        sys.stdout.write(rendered)
    else:
        if out.exists():
            raise AssuranceError(f"refusing to overwrite existing path: {out}")
        out.write_text(rendered)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate one assurance envelope")
    validate.add_argument("envelope", type=Path)
    mint = commands.add_parser("mint-test-token", help="Mint a public synthetic conformance token")
    mint.add_argument("envelope", type=Path)
    mint.add_argument("--jti", required=True)
    mint.add_argument("--issued-at", required=True)
    mint.add_argument("--expires-at", required=True)
    evaluate = commands.add_parser("evaluate", help="Evaluate a recorded MCP/A2A suite")
    evaluate.add_argument("envelope", type=Path)
    evaluate.add_argument("suite", type=Path)
    evaluate.add_argument("--out", type=Path)
    verify = commands.add_parser("verify", help="Recompute and verify a receipt")
    verify.add_argument("receipt", type=Path)
    verify.add_argument("--envelope", required=True, type=Path)
    verify.add_argument("--suite", required=True, type=Path)
    pack = commands.add_parser("pack", help="Build a non-overwriting portable assurance pack")
    pack.add_argument("envelope", type=Path)
    pack.add_argument("suite", type=Path)
    pack.add_argument("--out", required=True, type=Path)
    verify_pack_command = commands.add_parser("verify-pack", help="Verify an assurance pack")
    verify_pack_command.add_argument("path", type=Path)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "validate":
            envelope = load_json(args.envelope)
            validate_envelope(envelope)
            _emit({"status": "valid_synthetic_envelope", "envelope_sha256": digest(envelope)})
        elif args.command == "mint-test-token":
            _emit({"token": mint_test_token(load_json(args.envelope), jti=args.jti, issued_at=args.issued_at, expires_at=args.expires_at)})
        elif args.command == "evaluate":
            _emit(evaluate_suite(load_json(args.envelope), load_json(args.suite)), args.out)
        elif args.command == "verify":
            verify_receipt(load_json(args.receipt), load_json(args.envelope), load_json(args.suite))
            _emit({"status": "verified"})
        elif args.command == "pack":
            _emit(build_pack(args.envelope, args.suite, args.out))
        elif args.command == "verify-pack":
            _emit(verify_pack(args.path))
    except AssuranceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
