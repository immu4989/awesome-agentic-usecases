"""Run and verify the current MCP, A2A, and authority-relay evidence matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import a2a_1_delta
import authority_relay
import authority_trace
import mcp_2026_delta


MATRIX_VERSION = "aau-current-assurance-matrix/1.0"
MANIFEST_VERSION = "aau-current-assurance-matrix-manifest/1.0"
MAX_BYTES = 1_000_000
RECEIPTS = {
    "mcp_2026": "mcp-2026-receipt.json",
    "a2a_1": "a2a-1-receipt.json",
    "authority_relay": "authority-relay-receipt.json",
}
PACK_FILES = set(RECEIPTS.values()) | {
    "authority-traces.json", "matrix-receipt.json", "matrix.sarif.json", "SUMMARY.md",
    "manifest.json",
}


class MatrixError(ValueError):
    """Raised when the matrix or its pack violates the public contract."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(payload).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise MatrixError(f"invalid, oversized, or symbolic-link file: {path}")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MatrixError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise MatrixError(f"expected one JSON object: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def _inside(workspace: Path, value: Path, label: str, *, exists: bool) -> Path:
    workspace = workspace.resolve(strict=True)
    candidate = value if value.is_absolute() else workspace / value
    resolved = candidate.resolve(strict=exists)
    if not resolved.is_relative_to(workspace):
        raise MatrixError(f"{label} must remain inside the workspace")
    if exists and (candidate.is_symlink() or not resolved.is_file()):
        raise MatrixError(f"{label} must be a regular non-symbolic-link file")
    return resolved


def _inputs(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    workspace = args.workspace.resolve(strict=True)
    specs = {
        "mcp_2026": {
            "module": mcp_2026_delta,
            "profile": _inside(workspace, args.mcp_profile, "MCP profile", exists=True),
            "suite": _inside(workspace, args.mcp_suite, "MCP suite", exists=True),
            "adapter": args.mcp_adapter_command,
        },
        "a2a_1": {
            "module": a2a_1_delta,
            "profile": _inside(workspace, args.a2a_profile, "A2A profile", exists=True),
            "suite": _inside(workspace, args.a2a_suite, "A2A suite", exists=True),
            "adapter": args.a2a_adapter_command,
        },
        "authority_relay": {
            "module": authority_relay,
            "profile": _inside(workspace, args.relay_profile, "relay profile", exists=True),
            "suite": _inside(workspace, args.relay_suite, "relay suite", exists=True),
            "adapter": args.relay_adapter_command,
        },
    }
    for gate_id, spec in specs.items():
        if not isinstance(spec["adapter"], str) or not spec["adapter"].strip():
            raise MatrixError(f"{gate_id} adapter command is empty")
    return specs


def _matrix(
    receipts: dict[str, dict[str, Any]], trace_export: dict[str, Any]
) -> dict[str, Any]:
    gates = []
    for gate_id in ("mcp_2026", "a2a_1", "authority_relay"):
        receipt = receipts[gate_id]
        gates.append(
            {
                "gate_id": gate_id,
                "status": receipt["status"],
                "adapter_kind": receipt["adapter_kind"],
                "profile_sha256": receipt["profile_sha256"],
                "suite_sha256": receipt["suite_sha256"],
                "receipt_sha256": digest(receipt),
                "metrics": receipt["metrics"],
            }
        )
    keys = (
        "case_count", "clean_twin_count", "violation_count", "exact_count",
        "unsafe_allow_count", "legitimate_block_count",
    )
    aggregate = {key: sum(gate["metrics"][key] for gate in gates) for key in keys}
    status = "evidence_passed" if all(gate["status"] == "evidence_passed" for gate in gates) else "evidence_failed"
    return {
        "matrix_version": MATRIX_VERSION,
        "status": status,
        "gate_count": len(gates),
        "gates": gates,
        "aggregate": aggregate,
        "authority_trace": {
            **trace_export["summary"],
            "export_sha256": trace_export["export_sha256"],
        },
        "boundary": {
            "all_gates_use_answer_blind_command_adapters": all(
                gate["adapter_kind"] == "command" for gate in gates
            ),
            "aggregate_does_not_replace_gate_specific_results": True,
            "no_credentials_payloads_tools_agents_or_network_calls_by_matrix": True,
            "passing_not_protocol_identity_security_compliance_or_deployment_conformance": True,
        },
    }


def _summary(matrix: dict[str, Any]) -> str:
    lines = [
        "## AAU current agent-assurance matrix",
        "",
        f"**{matrix['status'].replace('_', ' ').upper()}** · "
        f"{matrix['aggregate']['exact_count']}/{matrix['aggregate']['case_count']} exact · "
        f"{matrix['aggregate']['unsafe_allow_count']} unsafe allows · "
        f"{matrix['aggregate']['legitimate_block_count']} legitimate blocks",
        f"{matrix['authority_trace']['span_count']} privacy-bounded spans · "
        f"{matrix['authority_trace']['raw_content_attribute_count']} raw content fields",
        "",
        "| Gate | Exact | Clean twins | Violations | Unsafe allows | Legitimate blocks |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    labels = {
        "mcp_2026": "MCP 2026-07-28 authorization",
        "a2a_1": "A2A 1.0 interface + authorization",
        "authority_relay": "A2A → MCP authority relay",
    }
    for gate in matrix["gates"]:
        metrics = gate["metrics"]
        lines.append(
            f"| {labels[gate['gate_id']]} | {metrics['exact_count']}/{metrics['case_count']} | "
            f"{metrics['clean_twin_count']} | {metrics['violation_count']} | "
            f"{metrics['unsafe_allow_count']} | {metrics['legitimate_block_count']} |"
        )
    lines.extend(
        [
            "",
            "Expected answers were not sent to adapters. The matrix contains recorded synthetic "
            "metadata and does not run an agent, tool, OAuth flow, or network request itself.",
            "",
            "Passing is evidence against these exact declared profiles—not production identity, "
            "live authorization, protocol/security/compliance conformance, certification, "
            "deployment approval, government endorsement, or an Authority to Operate.",
            "",
        ]
    )
    return "\n".join(lines)


def _sarif(receipts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    labels = {
        "mcp_2026": "MCP 2026 authorization gate mismatch",
        "a2a_1": "A2A 1.0 interface and authorization gate mismatch",
        "authority_relay": "A2A-to-MCP authority relay gate mismatch",
    }
    rules = []
    results = []
    for gate_id in ("mcp_2026", "a2a_1", "authority_relay"):
        rule_id = f"AAU_{gate_id.upper()}_EVIDENCE_MISMATCH"
        rules.append(
            {
                "id": rule_id,
                "name": labels[gate_id],
                "shortDescription": {"text": labels[gate_id]},
                "help": {
                    "text": "Inspect the digest-bound gate receipt and project adapter. Expected answers were not sent to the adapter."
                },
                "properties": {"precision": "very-high", "security-severity": "8.0"},
            }
        )
        for row in receipts[gate_id]["results"]:
            if row["exact"]:
                continue
            results.append(
                {
                    "ruleId": rule_id,
                    "level": "error",
                    "message": {"text": f"{gate_id} case {row['case_id']} did not match its committed decision and reason codes."},
                    "properties": {
                        "gate_id": gate_id,
                        "case_id": row["case_id"],
                        "actual_decision": row["actual_decision"],
                        "actual_reason_codes": row["actual_reason_codes"],
                        "raw_inputs_included": False,
                    },
                }
            )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "AAU Current Assurance Matrix",
                        "informationUri": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/portable-agent-assurance",
                        "rules": rules,
                    }
                },
                "results": results,
                "properties": {
                    "synthetic_recorded_metadata_only": True,
                    "result_count": len(results),
                    "not_security_certification_or_deployment_approval": True,
                },
            }
        ],
    }


def _manifest(directory: Path) -> dict[str, Any]:
    files = []
    for name in sorted(PACK_FILES - {"manifest.json"}):
        payload = (directory / name).read_bytes()
        files.append({"path": name, "bytes": len(payload), "sha256": digest(payload)})
    return {"manifest_version": MANIFEST_VERSION, "files": files}


def run_pack(args: argparse.Namespace) -> dict[str, Any]:
    specs = _inputs(args)
    output = _inside(args.workspace, args.out, "matrix output", exists=False)
    if output.exists() or output.is_symlink():
        raise MatrixError(f"refusing to overwrite matrix output: {output}")
    output.mkdir(parents=True)
    receipts = {}
    trace_export = None
    for gate_id, spec in specs.items():
        module = spec["module"]
        profile = module.load_json(spec["profile"])
        suite = module.load_json(spec["suite"])
        receipt = module.run_suite(profile, suite, "command", spec["adapter"], args.timeout)
        module.verify_receipt(receipt, profile, suite)
        receipts[gate_id] = receipt
        _write_json(output / RECEIPTS[gate_id], receipt)
        if gate_id == "authority_relay":
            trace_export = authority_trace.build_export(
                profile, suite, receipt, require_exact=False
            )
    if trace_export is None:
        raise MatrixError("authority trace source receipt is missing")
    _write_json(output / "authority-traces.json", trace_export)
    matrix = _matrix(receipts, trace_export)
    _write_json(output / "matrix-receipt.json", matrix)
    _write_json(output / "matrix.sarif.json", _sarif(receipts))
    (output / "SUMMARY.md").write_text(_summary(matrix))
    _write_json(output / "manifest.json", _manifest(output))
    verify_pack(args)
    return matrix


def verify_pack(args: argparse.Namespace) -> dict[str, Any]:
    specs = _inputs(args)
    output = _inside(args.workspace, args.out, "matrix output", exists=False)
    if not output.is_dir() or output.is_symlink():
        raise MatrixError("matrix output must be a regular directory")
    files = {path.name for path in output.iterdir()}
    if files != PACK_FILES or any(path.is_symlink() or not path.is_file() for path in output.iterdir()):
        raise MatrixError("matrix pack has missing, extra, or symbolic-link files")
    receipts = {}
    relay_sources = None
    for gate_id, spec in specs.items():
        module = spec["module"]
        profile = module.load_json(spec["profile"])
        suite = module.load_json(spec["suite"])
        receipt = _load(output / RECEIPTS[gate_id])
        module.verify_receipt(receipt, profile, suite)
        if receipt["adapter_kind"] != "command":
            raise MatrixError(f"{gate_id} receipt did not come from a command adapter")
        receipts[gate_id] = receipt
        if gate_id == "authority_relay":
            relay_sources = (profile, suite, receipt)
    if relay_sources is None:
        raise MatrixError("authority trace source receipt is missing")
    trace_export = _load(output / "authority-traces.json")
    authority_trace.validate_export(trace_export, *relay_sources)
    expected_matrix = _matrix(receipts, trace_export)
    if _load(output / "matrix-receipt.json") != expected_matrix:
        raise MatrixError("matrix receipt does not recompute")
    if _load(output / "matrix.sarif.json") != _sarif(receipts):
        raise MatrixError("matrix SARIF does not recompute")
    if (output / "SUMMARY.md").read_text() != _summary(expected_matrix):
        raise MatrixError("matrix summary does not recompute")
    if _load(output / "manifest.json") != _manifest(output):
        raise MatrixError("matrix manifest does not recompute")
    return expected_matrix


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mcp-profile", type=Path, required=True)
    parser.add_argument("--mcp-suite", type=Path, required=True)
    parser.add_argument("--mcp-adapter-command", required=True)
    parser.add_argument("--a2a-profile", type=Path, required=True)
    parser.add_argument("--a2a-suite", type=Path, required=True)
    parser.add_argument("--a2a-adapter-command", required=True)
    parser.add_argument("--relay-profile", type=Path, required=True)
    parser.add_argument("--relay-suite", type=Path, required=True)
    parser.add_argument("--relay-adapter-command", required=True)
    parser.add_argument("--timeout", type=float, default=10)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Run or verify the current AAU assurance matrix")
    sub = root.add_subparsers(dest="command", required=True)
    _common(sub.add_parser("run"))
    _common(sub.add_parser("verify"))
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        matrix = run_pack(args) if args.command == "run" else verify_pack(args)
        print(
            f"OK: {matrix['aggregate']['exact_count']}/{matrix['aggregate']['case_count']} exact "
            f"across {matrix['gate_count']} current gates."
        )
        return 0 if matrix["status"] == "evidence_passed" else 1
    except (MatrixError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
