"""Tool schemas the admission agent sees and their execution against one artifact.

The split is deliberate: `read_manifest` returns what the uploader *declared*, and the
scan tools return what the artifact *actually does*. An agent that decides from the
manifest alone will admit the artifact whose config executes undeclared code — which is
exactly how the July 2026 dataset-processing breach happened.
"""

from __future__ import annotations

import json

from .world import DISPOSITIONS, Scenario, loader_findings, search_admission_policy

TOOL_SCHEMAS = [
    {
        "name": "read_manifest",
        "description": (
            "Read the artifact's declared manifest: kind, publishing org, whether it "
            "declares remote code (trust_remote_code), and the uploader's own summary. "
            "This is what the uploader CLAIMS. It is not verified — a manifest can under- "
            "or over-state what the artifact executes. Never decide from this alone."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string", "description": "Artifact id, e.g. art-004"}
            },
            "required": ["artifact_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "scan_loader",
        "description": (
            "Statically scan any custom loading code the artifact ships. Returns whether "
            "a loader is present and the constructs found in it (network calls, exec/eval, "
            "credential access, or benign local file I/O). This is a verified fact about "
            "what the loader would run."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string", "description": "Artifact id, e.g. art-004"}
            },
            "required": ["artifact_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "scan_config",
        "description": (
            "Statically scan the artifact's CONFIG for code that executes at load time: "
            "template rendering with eval, unsafe YAML tags, or format strings run by the "
            "builder. A manifest can declare no remote code while the config still "
            "executes — that undeclared execution is the exact path the July 2026 "
            "dataset-processing breach used. Scan this on every artifact."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string", "description": "Artifact id, e.g. art-004"}
            },
            "required": ["artifact_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "check_publisher",
        "description": (
            "Look up the publishing org's verification status, whether the artifact is "
            "pinned to a commit SHA or tracks a mutable ref (e.g. main), and 30-day "
            "downloads. Download count is context, not a safety signal."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string", "description": "Artifact id, e.g. art-004"}
            },
            "required": ["artifact_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_admission_policy",
        "description": (
            "Search the admission policy. The rules for undeclared execution, malicious "
            "loaders, unverified publishers, mutable refs, sandboxing, and clean "
            "artifacts live here, not in your instructions. Check before deciding."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "Keyword query, e.g. 'undeclared execution config template'"}
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "submit_admission",
        "description": (
            "Commit the admission disposition for this artifact. Call exactly once, after "
            "investigating. This ends the task."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "disposition": {"type": "string", "enum": DISPOSITIONS,
                                "description": "admit | sandbox_only | block | escalate"},
                "primary_reason": {"type": "string",
                                   "description": "Short reason, ideally citing a policy id"},
                "reasoning": {"type": "string",
                              "description": "One-paragraph justification citing the scans and policy used"},
            },
            "required": ["disposition", "primary_reason", "reasoning"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(name: str, tool_input: dict, scenario: Scenario) -> str:
    if name in ("read_manifest", "scan_loader", "scan_config", "check_publisher"):
        if tool_input.get("artifact_id") != scenario.artifact_id:
            return json.dumps({"error": f"no artifact {tool_input.get('artifact_id')!r}"})
    if name == "read_manifest":
        return json.dumps({
            "artifact_id": scenario.artifact_id,
            "kind": scenario.kind,
            "publisher_name": scenario.publisher_name,
            "declares_remote_code": scenario.declares_remote_code,
            "declared_summary": scenario.declared_summary,
        })
    if name == "scan_loader":
        return json.dumps({
            "artifact_id": scenario.artifact_id,
            "loader_present": scenario.loader_exec,
            "findings": loader_findings(scenario.loader_exec, scenario.loader_malicious),
        })
    if name == "scan_config":
        if scenario.config_template_injection:
            detail = ("dataset config renders a Jinja template with a runtime eval() in "
                      "dataset_infos")
        else:
            detail = "static config; declared features only, no templating or eval"
        return json.dumps({
            "artifact_id": scenario.artifact_id,
            "config_executes": scenario.config_template_injection,
            "detail": detail,
        })
    if name == "check_publisher":
        return json.dumps({
            "artifact_id": scenario.artifact_id,
            "publisher_verified": scenario.publisher_verified,
            "revision_pinned": scenario.revision_pinned,
            "revision_ref": scenario.revision_ref,
            "downloads_30d": scenario.downloads_30d,
        })
    if name == "search_admission_policy":
        return json.dumps(search_admission_policy(tool_input.get("query", "")))
    return json.dumps({"error": f"unknown tool {name!r}"})
