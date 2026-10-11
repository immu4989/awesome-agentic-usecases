"""Declared scenario/configuration/scoring fingerprints, not execution attestations."""

import hashlib
import json
from pathlib import Path

from .agent_bom import AgentBomError


VERSION = "aau-evaluation-context/1.0"


def _hash_json(value) -> str:
    def check_keys(item):
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("JSON object keys must be strings")
            for child in item.values():
                check_keys(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                check_keys(child)
    try:
        check_keys(value)
        payload = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                             separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise AgentBomError("evaluation context requires finite JSON-compatible values") from exc
    if len(payload) > 2_000_000:
        raise AgentBomError("evaluation context input exceeds 2 MB")
    return hashlib.sha256(payload).hexdigest()


def validate_context(context: dict, scenario_ids=None) -> None:
    if not isinstance(context, dict) or set(context) != {"context_version", "scenario_sha256", "config_sha256", "scoring_sha256"}:
        raise AgentBomError("invalid evaluation context fields")
    if context["context_version"] != VERSION:
        raise AgentBomError("unsupported evaluation context version")
    def valid_hash(value):
        return isinstance(value, str) and len(value) == 64 and set(value) <= set("0123456789abcdef")
    if not valid_hash(context["config_sha256"]):
        raise AgentBomError("invalid evaluation configuration fingerprint")
    for field, limit in (("scenario_sha256", 500), ("scoring_sha256", 20)):
        values = context[field]
        if (not isinstance(values, dict) or not 1 <= len(values) <= limit
                or any(not isinstance(name, str) or not name.strip() or len(name) > 200
                       or not valid_hash(value) for name, value in values.items())):
            raise AgentBomError(f"invalid {field} fingerprints")
    if scenario_ids is not None and set(context["scenario_sha256"]) != set(scenario_ids):
        raise AgentBomError("evaluation context does not cover the exact observed scenario IDs")


def capture_context(scenarios: list[dict], config: dict, scoring_sources: dict[str, bytes]) -> dict:
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 500 or not isinstance(config, dict):
        raise AgentBomError("context requires 1 to 500 scenario objects and a configuration object")
    records = {}
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise AgentBomError("context scenario must be an object")
        identity = scenario.get("scenario_id")
        if not isinstance(identity, str) or not identity.strip() or identity in records:
            raise AgentBomError("context scenarios require unique nonblank scenario_id values")
        records[identity] = _hash_json(scenario)
    if not isinstance(scoring_sources, dict) or not 1 <= len(scoring_sources) <= 20:
        raise AgentBomError("context requires 1 to 20 named scoring source byte strings")
    hashes = {}
    for name, payload in scoring_sources.items():
        if not isinstance(payload, bytes) or not payload or len(payload) > 2_000_000:
            raise AgentBomError("scoring sources must be nonempty bytes within 2 MB")
        hashes[name] = hashlib.sha256(payload).hexdigest()
    context = {"context_version": VERSION, "scenario_sha256": dict(sorted(records.items())),
               "config_sha256": _hash_json(config), "scoring_sha256": hashes}
    validate_context(context)
    return context


def capture_runtime_context(scenarios, config: dict, module_file: str) -> dict:
    """Bind the shared engine and named local mechanics; not a dependency-closure claim."""
    engine = Path(module_file)
    names = {engine.name, "runner.py", "agent_loop.py", "evaluation_context.py"}
    if engine.name == "evidence_service.py":
        names.add("public_value.py")
    return capture_context([scenario.as_dict() for scenario in scenarios], config,
                           {name: (engine.parent / name).read_bytes() for name in sorted(names)})


def compare_contexts(baseline: dict, candidate: dict) -> dict:
    contexts = []
    missing = []
    for label, source in (("baseline", baseline), ("candidate", candidate)):
        if "evaluation_context" not in source:
            missing.append(label)
            contexts.append(None)
        else:
            context = source["evaluation_context"]
            validate_context(context, [row["scenario_id"] for row in source["results"]])
            contexts.append(context)
    if missing:
        return {"status": "unavailable", "missing_sources": missing}
    if contexts[0] != contexts[1]:
        differences = [field for field in ("scenario_sha256", "config_sha256", "scoring_sha256")
                       if contexts[0][field] != contexts[1][field]]
        raise AgentBomError("evaluation contexts differ: " + ", ".join(differences))
    return {"status": "matched", "missing_sources": []}
