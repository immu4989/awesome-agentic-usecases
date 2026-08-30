"""Privacy-bounded cross-protocol authority trace export.

The export is deterministic synthetic evidence, not live OpenTelemetry capture,
production observability, protocol conformance, or proof that an action occurred.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import authority_relay


EXPORT_VERSION = "aau-authority-trace-export/1.0"
SEMCONV_BASIS = "opentelemetry-semantic-conventions/1.44.0"
MAX_BYTES = 2_000_000
MAX_ATTRIBUTES = 16
MAX_VALUE_LENGTH = 160
FORBIDDEN_FRAGMENTS = {
    "argument", "authorization", "baggage", "body", "content", "cookie", "credential",
    "email", "input", "message", "output", "password", "prompt", "result", "secret",
    "subject", "token", "tracestate",
}


class TraceError(ValueError):
    """Raised when an authority trace violates the public privacy contract."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise TraceError(f"invalid, oversized, or symbolic-link file: {path}")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TraceError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise TraceError(f"expected one JSON object: {path}")
    return value


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise TraceError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(value, indent=2) + "\n")


def _id(seed: str, length: int) -> str:
    value = hashlib.sha256(seed.encode()).hexdigest()[:length]
    return "1" + value[1:] if set(value) == {"0"} else value


def _ref(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _attributes(values: dict[str, Any]) -> list[dict[str, Any]]:
    if len(values) > MAX_ATTRIBUTES:
        raise TraceError("span exceeds the public attribute-count limit")
    rows = []
    for key, value in sorted(values.items()):
        lowered = key.lower()
        if any(fragment in lowered for fragment in FORBIDDEN_FRAGMENTS):
            raise TraceError(f"forbidden attribute key: {key}")
        if isinstance(value, str):
            if not value or len(value) > MAX_VALUE_LENGTH:
                raise TraceError(f"attribute value is empty or oversized: {key}")
        elif isinstance(value, list):
            if len(value) > 32 or any(
                not isinstance(item, str) or not item or len(item) > MAX_VALUE_LENGTH
                for item in value
            ):
                raise TraceError(f"attribute string array is invalid: {key}")
        elif not isinstance(value, (bool, int)):
            raise TraceError(f"attribute type is unsupported: {key}")
        rows.append({"key": key, "value": value})
    return rows


def _span(
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    name: str,
    kind: str,
    attributes: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "name": name,
        "kind": kind,
        "status": status,
        "attributes": _attributes(attributes),
    }


def build_export(
    profile: dict[str, Any],
    suite: dict[str, Any],
    receipt: dict[str, Any],
    *,
    require_exact: bool = True,
) -> dict[str, Any]:
    authority_relay.validate_profile(profile)
    authority_relay.verify_receipt(receipt, profile, suite)
    if receipt["adapter_kind"] != "command":
        raise TraceError("trace export requires a command-adapter relay receipt")
    if require_exact and receipt["status"] != "evidence_passed":
        raise TraceError("public trace export requires an exact relay receipt")
    results = {row["case_id"]: row for row in receipt["results"]}
    traces = []
    for case in suite["cases"]:
        case_id = case["case_id"]
        result = results[case_id]
        request = case["request"]
        trace_id = _id(f"{suite['suite_id']}:{case_id}:trace", 32)
        inbound_id = _id(f"{trace_id}:a2a", 16)
        decision_id = _id(f"{trace_id}:decision", 16)
        dispatch_id = _id(f"{trace_id}:mcp", 16)
        decision = result["actual_decision"]
        common = {
            "aau.assurance.case_id": case_id,
            "aau.assurance.synthetic": True,
            "aau.authority.task_ref_sha256": _ref(request["task_id"]),
            "aau.authority.delegation_ref_sha256": _ref(request["delegation_id"]),
        }
        spans = [
            _span(
                trace_id,
                inbound_id,
                None,
                "a2a.receive",
                "SERVER",
                {
                    **common,
                    "gen_ai.operation.name": "invoke_agent",
                    "aau.protocol.name": "a2a",
                    "aau.protocol.version": request["a2a_revision"],
                    "aau.authority.tenant_ref_sha256": _ref(request["tenant"]),
                    "aau.authority.card_ref_sha256": request["agent_card_sha256"],
                },
                "OK" if request["inbound_authenticated"] else "ERROR",
            ),
            _span(
                trace_id,
                decision_id,
                inbound_id,
                "authority.evaluate",
                "INTERNAL",
                {
                    **common,
                    "aau.authority.decision": decision,
                    "aau.authority.reason_codes": result["actual_reason_codes"],
                    "aau.authority.policy_epoch": request["policy_epoch"],
                    "aau.authority.route_ref_sha256": _ref(request["route_id"]),
                    "aau.authority.monitor_active": request["monitor_active"],
                    "aau.authority.human_approval_present": request["human_approval_present"],
                },
                "OK" if decision == "allow" else "ERROR",
            ),
        ]
        if decision == "allow":
            spans.append(
                _span(
                    trace_id,
                    dispatch_id,
                    decision_id,
                    "mcp.tools/call",
                    "CLIENT",
                    {
                        **common,
                        "gen_ai.operation.name": "execute_tool",
                        "aau.protocol.name": "mcp",
                        "aau.protocol.version": request["mcp_revision"],
                        "aau.authority.tool_ref_sha256": _ref(request["outbound_tool"]),
                        "aau.authority.resource_ref_sha256": _ref(request["resource"]),
                        "aau.authority.scope_set_sha256": digest(request["scopes"]),
                        "aau.authority.audience_ref_sha256": _ref(request["token_audience"]),
                    },
                    "UNSET",
                )
            )
        traces.append(
            {
                "case_id": case_id,
                "decision": decision,
                "trace_id": trace_id,
                "span_count": len(spans),
                "mcp_dispatch_recorded": decision == "allow",
                "spans": spans,
            }
        )
    export = {
        "export_version": EXPORT_VERSION,
        "semantic_convention_basis": SEMCONV_BASIS,
        "source": {
            "profile_sha256": digest(profile),
            "suite_sha256": digest(suite),
            "receipt_sha256": digest(receipt),
            "adapter_kind": receipt["adapter_kind"],
            "evidence_status": receipt["status"],
        },
        "summary": {
            "trace_count": len(traces),
            "span_count": sum(row["span_count"] for row in traces),
            "allow_trace_count": sum(row["decision"] == "allow" for row in traces),
            "block_trace_count": sum(row["decision"] == "block" for row in traces),
            "blocked_mcp_dispatch_count": sum(
                row["decision"] == "block" and not row["mcp_dispatch_recorded"] for row in traces
            ),
            "raw_content_attribute_count": 0,
            "tracestate_field_count": 0,
            "baggage_field_count": 0,
        },
        "traces": traces,
        "boundary": {
            "synthetic_deterministic_ids_not_production_randomness": True,
            "metadata_projection_not_live_telemetry_capture": True,
            "no_raw_identity_prompts_messages_arguments_results_tokens_or_personal_data": True,
            "no_tracestate_or_baggage": True,
            "not_opentelemetry_a2a_mcp_security_or_compliance_conformance": True,
        },
        "export_sha256": "",
    }
    export["export_sha256"] = digest(
        {key: value for key, value in export.items() if key != "export_sha256"}
    )
    return export


def validate_export(
    export: dict[str, Any],
    profile: dict[str, Any],
    suite: dict[str, Any],
    receipt: dict[str, Any],
) -> None:
    if export.get("export_version") != EXPORT_VERSION:
        raise TraceError("trace export version is invalid")
    if export.get("semantic_convention_basis") != SEMCONV_BASIS:
        raise TraceError("semantic convention basis is invalid")
    expected = build_export(
        profile,
        suite,
        receipt,
        require_exact=receipt.get("status") != "evidence_failed",
    )
    if export != expected:
        raise TraceError("trace export does not recompute from its exact sources")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Export privacy-bounded authority traces")
    sub = root.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    export.add_argument("profile", type=Path)
    export.add_argument("suite", type=Path)
    export.add_argument("receipt", type=Path)
    export.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("trace_export", type=Path)
    verify.add_argument("profile", type=Path)
    verify.add_argument("suite", type=Path)
    verify.add_argument("receipt", type=Path)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        profile, suite, receipt = map(load_json, (args.profile, args.suite, args.receipt))
        if args.command == "export":
            export = build_export(profile, suite, receipt)
            write_json(export, args.out)
            print(f"wrote {args.out} ({export['summary']['trace_count']} traces)")
        else:
            export = load_json(args.trace_export)
            validate_export(export, profile, suite, receipt)
            print(f"OK: {args.trace_export} is privacy-bounded and source-bound.")
        return 0
    except (TraceError, authority_relay.RelayError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
