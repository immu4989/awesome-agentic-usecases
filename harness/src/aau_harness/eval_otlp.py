"""Project explicitly mapped OTLP spans into source-retaining sequential retry evidence."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered
from .eval_retries import FILES as RETRY_FILES, retry_payloads


ROOT_FILES = {"source.otlp", "mapping.json", "projection.json", "manifest.json"}
BOUNDARY = (
    "Offline projection, not an OTLP receiver, execution, scoring, completeness attestation, or retry authorization. "
    "Only explicitly declared single-attempt spans that are direct, sequential children of a task span in the same "
    "resource entry are supported. A GenAI logical-operation span can already include retries: do not relabel it "
    "as one physical attempt. Resource co-location does not prove a common trustworthy clock. All supplied spans "
    "must have a declared role; exclusion reasons are reviewer declarations, not proof exclusions are appropriate. "
    "Missing external or sampled-out spans cannot be detected if declarations also omit them. Source bytes, including "
    "unmapped attributes, events, prompts, credentials, and identifiers, are retained without sanitization. Inspect "
    "before sharing. Numeric score, USD cost, and API-count attributes require explicit mappings; no score is inferred "
    "from status and no price or call count is inferred from tokens or span counts. Missing attributes stay unknown. "
    "Nanosecond timestamps are subtracted as integers before seconds conversion; clocks and duration accuracy are "
    "not authenticated. No nested/parallel cost aggregation, network calls, model calls, uploads, or context fabrication. "
    "Hashes are not signatures; downstream review requires independently approved scoring and accounting definitions."
)


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AgentBomError("OTLP JSON contains duplicate object keys")
        result[key] = value
    return result


def _constant(_):
    raise AgentBomError("OTLP JSON requires finite numbers")


def _integer(value, *, signed=False):
    if isinstance(value, str) and re.fullmatch(r"-?(?:0|[1-9][0-9]*)", value):
        try:
            value = int(value)
        except ValueError as exc:
            raise AgentBomError("OTLP integer exceeds supported range") from exc
    lower, upper = (-2**63, 2**63 - 1) if signed else (0, 2**64 - 1)
    if type(value) is not int or not lower <= value <= upper:
        raise AgentBomError("OTLP integer must be an in-range decimal string or integer, not float/bool")
    return value


def _id(value, length):
    if (not isinstance(value, str) or re.fullmatch(rf"[0-9a-fA-F]{{{length}}}", value) is None
            or int(value, 16) == 0):
        raise AgentBomError("OTLP IDs must be nonzero hex trace/span identifiers")
    return value.lower()


def _key(trace, span):
    return _id(trace, 32), _id(span, 16)


def _source(raw, source_format):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_JSON_BYTES:
        raise AgentBomError("OTLP source requires 1 to 2000000 bytes")
    try:
        text = raw.decode("utf-8")
        chunks = text.splitlines() if source_format == "otlp_jsonl" else [text]
        if not chunks or len(chunks) > 10000 or any(not chunk.strip() for chunk in chunks):
            raise AgentBomError("OTLP JSONL requires nonblank records, at most 10000")
        documents = [json.loads(chunk, object_pairs_hook=_object_pairs, parse_constant=_constant) for chunk in chunks]
        # Check even unmapped metadata for unsupported nonfinite values and invalid Unicode.
        json.dumps(documents, allow_nan=False, ensure_ascii=False).encode("utf-8")
    except (UnicodeError, ValueError, OverflowError, RecursionError) as exc:
        raise AgentBomError("OTLP source must be bounded, finite UTF-8 JSON without duplicate keys") from exc
    spans = {}
    for document_index, document in enumerate(documents):
        if not isinstance(document, dict) or not isinstance(document.get("resourceSpans"), list):
            raise AgentBomError("each OTLP record requires a resourceSpans array")
        for resource_index, resource in enumerate(document["resourceSpans"]):
            if not isinstance(resource, dict) or not isinstance(resource.get("scopeSpans"), list):
                raise AgentBomError("resourceSpans entries require scopeSpans arrays")
            for scope in resource["scopeSpans"]:
                if not isinstance(scope, dict) or not isinstance(scope.get("spans"), list):
                    raise AgentBomError("scopeSpans entries require spans arrays")
                for span in scope["spans"]:
                    if not isinstance(span, dict):
                        raise AgentBomError("OTLP span must be an object")
                    key = _key(span.get("traceId"), span.get("spanId"))
                    if key in spans or len(spans) >= 10000:
                        raise AgentBomError("OTLP span identities must be unique, at most 10000")
                    parent = span.get("parentSpanId", "")
                    if parent != "":
                        _id(parent, 16)
                    spans[key] = (span, (document_index, resource_index))
    if not spans:
        raise AgentBomError("OTLP source contains no spans")
    return spans


def _attributes(span):
    entries = span.get("attributes", [])
    if not isinstance(entries, list):
        raise AgentBomError("selected span attributes must be an array")
    result = {}
    for entry in entries:
        if (not isinstance(entry, dict) or not isinstance(entry.get("key"), str) or not entry["key"]
                or entry["key"] in result or not isinstance(entry.get("value"), dict)):
            raise AgentBomError("selected span attributes require unique keys and AnyValue objects")
        result[entry["key"]] = entry["value"]
    return result


def _number(value):
    if set(value) == {"intValue"}:
        return _integer(value["intValue"], signed=True)
    if set(value) == {"doubleValue"}:
        number = value["doubleValue"]
        if type(number) in (int, float) and -sys.float_info.max <= number <= sys.float_info.max:
            return number
    raise AgentBomError("mapped attributes require finite numeric intValue/doubleValue, without coercion")


def _interval(span):
    start = _integer(span.get("startTimeUnixNano"))
    end = _integer(span.get("endTimeUnixNano"))
    if end < start:
        raise AgentBomError("selected span ends before its start")
    return start, end


def otlp_payloads(mapping: dict, raw: bytes) -> tuple[dict, dict[str, bytes]]:
    required = {"mapping_version", "source_format", "span_semantics", "accounting_plan", "attributes", "tasks", "excluded_spans"}
    if not isinstance(mapping, dict) or set(mapping) != required:
        raise AgentBomError("OTLP mapping requires exactly the documented fields")
    try:
        if len(json.dumps(mapping, allow_nan=False).encode()) > MAX_JSON_BYTES:
            raise AgentBomError("OTLP mapping exceeds 2 MB")
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        raise AgentBomError("OTLP mapping must be bounded finite JSON") from exc
    if (mapping["mapping_version"] != "aau-otlp-retry-import/1.0"
            or mapping["source_format"] not in ("otlp_json", "otlp_jsonl")
            or mapping["span_semantics"] != "single_attempt_direct_children_same_resource_clock"):
        raise AgentBomError("unsupported OTLP mapping version, source format, or attempt/clock declaration")
    plan, columns = mapping["accounting_plan"], mapping["attributes"]
    if not isinstance(plan, dict) or not isinstance(plan.get("metric_reducers"), dict):
        raise AgentBomError("OTLP mapping requires a retry accounting plan")
    if (not isinstance(columns, dict) or set(columns) != {"metrics", "operating"}
            or not isinstance(columns["metrics"], dict) or set(columns["metrics"]) != set(plan["metric_reducers"])
            or not isinstance(columns["operating"], dict) or not set(columns["operating"]) <= {"cost_usd", "n_api_calls"}):
        raise AgentBomError("attribute map must cover every reduced metric and only supported operating attributes")
    names = [*columns["metrics"].values(), *columns["operating"].values()]
    if (any(not isinstance(name, str) or not name.strip() or len(name) > 200 for name in names)
            or len(names) != len(set(names))):
        raise AgentBomError("mapped attributes must be distinct nonblank names of at most 200 characters")
    if (not isinstance(mapping["tasks"], list) or not 1 <= len(mapping["tasks"]) <= 10000
            or not isinstance(mapping["excluded_spans"], list) or len(mapping["excluded_spans"]) > 10000):
        raise AgentBomError("OTLP mapping requires 1 to 10000 tasks and at most 10000 explicit exclusions")
    spans = _source(raw, mapping["source_format"])
    roles, tasks, details = {}, [], []
    expanded_size = 0

    def claim(key, role):
        if key not in spans or key in roles:
            raise AgentBomError("each declared span must exist and have exactly one role")
        roles[key] = role
        return spans[key]

    for declaration in mapping["tasks"]:
        if not isinstance(declaration, dict) or set(declaration) != {"scenario_id", "repeat", "trace_id", "task_span_id", "attempt_span_ids"}:
            raise AgentBomError("task mapping requires scenario_id, repeat, trace_id, task_span_id, attempt_span_ids")
        root_key = _key(declaration["trace_id"], declaration["task_span_id"])
        root, resource = claim(root_key, "task")
        start, end = _interval(root)
        attempt_ids = declaration["attempt_span_ids"]
        if not isinstance(attempt_ids, list) or not 1 <= len(attempt_ids) <= 100:
            raise AgentBomError("each task requires 1 to 100 ordered attempt span IDs")
        previous_end, attempts, ignored = start, [], set()
        for index, span_id in enumerate(attempt_ids):
            key = _key(root_key[0], span_id)
            span, attempt_resource = claim(key, "attempt")
            if attempt_resource != resource or span.get("parentSpanId", "").lower() != root_key[1]:
                raise AgentBomError("attempts must be direct task children in the same resource entry")
            attempt_start, attempt_end = _interval(span)
            if attempt_start < previous_end or attempt_end > end:
                raise AgentBomError("attempts must be ordered, non-overlapping, and contained in their task interval")
            previous_end = attempt_end
            values = _attributes(span)
            ignored.update(set(values) - set(names))
            attempt = {"attempt_id": ":".join(key), "attempt_index": index, "metrics": {},
                       "latency_s": (attempt_end - attempt_start) / 1_000_000_000}
            for metric, attribute in columns["metrics"].items():
                if attribute in values:
                    attempt["metrics"][metric] = _number(values[attribute])
            for field, attribute in columns["operating"].items():
                if attribute in values:
                    attempt[field] = _number(values[attribute])
            # Short source attribute names can map to long metric names on every attempt.
            # Bound expansion while building, before the shared ledger validator runs.
            expanded_size += len(rendered(attempt))
            if expanded_size > MAX_JSON_BYTES:
                raise AgentBomError("expanded OTLP attempt evidence exceeds 2 MB")
            attempts.append(attempt)
        tasks.append({"scenario_id": declaration["scenario_id"], "repeat": declaration["repeat"],
                      "elapsed_s": (end - start) / 1_000_000_000, "attempt_count": len(attempts), "attempts": attempts})
        details.append({"scenario_id": declaration["scenario_id"], "repeat": declaration["repeat"],
                        "task_span": ":".join(root_key), "attempt_spans": [a["attempt_id"] for a in attempts],
                        "unmapped_attempt_attribute_names": sorted(ignored)})
    for excluded in mapping["excluded_spans"]:
        if (not isinstance(excluded, dict) or set(excluded) != {"trace_id", "span_id", "reason"}
                or not isinstance(excluded["reason"], str) or not excluded["reason"].strip() or len(excluded["reason"]) > 500):
            raise AgentBomError("excluded spans require exact identity and a nonblank reason of at most 500 characters")
        claim(_key(excluded["trace_id"], excluded["span_id"]), "excluded")
    if set(roles) != set(spans):
        raise AgentBomError("every exported span requires a task, attempt, or explicit excluded role")
    for key, (span, _) in spans.items():
        parent = span.get("parentSpanId")
        if parent and roles.get((key[0], parent.lower())) == "task" and roles[key] != "attempt":
            raise AgentBomError("direct children of selected tasks cannot be excluded or nested tasks")
    # Validate the declared parent forest in linear time, including excluded spans.
    ancestors = {}
    for key in spans:
        current, path, visiting = key, [], set()
        while current in spans and current not in ancestors:
            if current in visiting:
                raise AgentBomError("exported parent graph contains a cycle")
            visiting.add(current)
            path.append(current)
            parent = spans[current][0].get("parentSpanId")
            current = (current[0], parent.lower()) if parent else None
        selected_above = ancestors.get(current, False)
        for member in reversed(path):
            if roles[member] == "task" and selected_above:
                raise AgentBomError("selected task spans cannot be nested under selected tasks or attempts")
            selected_above = selected_above or roles[member] in ("task", "attempt")
            ancestors[member] = selected_above
    ledger = {"ledger_version": "aau-task-attempt-ledger/1.0", "tasks": tasks}
    accounting, retry_files = retry_payloads(deepcopy(plan), ledger)
    report = {"report_version": "aau-otlp-retry-projection/1.0", "source_sha256": digest(raw),
              "mapping_sha256": digest(mapping), "ledger_sha256": digest(ledger),
              "evaluation_sha256": accounting["evaluation_sha256"], "exported_span_count": len(spans),
              "task_count": len(tasks), "attempt_count": accounting["attempt_count"],
              "excluded_span_count": len(mapping["excluded_spans"]), "tasks": details,
              "excluded_spans": deepcopy(mapping["excluded_spans"]), "boundary": BOUNDARY}
    payloads = {"source.otlp": raw, "mapping.json": rendered(mapping), "projection.json": rendered(report),
                **{f"retry/{name}": value for name, value in retry_files.items()}}
    payloads["manifest.json"] = rendered({"pack_version": "aau-otlp-retry-pack/1.0",
                                         "files": {name: digest(value) for name, value in sorted(payloads.items())}})
    if any(len(value) > MAX_JSON_BYTES for value in payloads.values()):
        raise AgentBomError("OTLP projection pack member exceeds 2 MB")
    return report, payloads


def _read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise AgentBomError("OTLP pack inputs must be regular non-symlink files within 2 MB")
    with path.open("rb") as stream:
        return stream.read(MAX_JSON_BYTES + 1)


def create_otlp_pack(mapping: dict, raw: bytes, directory: Path) -> dict:
    if directory.exists() or directory.is_symlink():
        raise AgentBomError("refusing to overwrite OTLP projection destination")
    report, payloads = otlp_payloads(mapping, raw)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "retry").mkdir()
    for name, value in payloads.items():
        with (directory / name).open("xb") as stream:
            stream.write(value)  # Completion manifest last.
    return report


def verify_otlp_pack(directory: Path, *, ledger_path: Path | None = None, evaluation_path: Path | None = None) -> dict:
    if (directory.is_symlink() or not directory.is_dir()
            or {p.name for p in directory.iterdir()} != ROOT_FILES | {"retry"}):
        raise AgentBomError("OTLP pack requires exact root members")
    retry = directory / "retry"
    if retry.is_symlink() or not retry.is_dir() or {p.name for p in retry.iterdir()} != RETRY_FILES:
        raise AgentBomError("OTLP pack requires exact nested retry members")
    actual = {name: _read(directory / name) for name in ROOT_FILES | {f"retry/{name}" for name in RETRY_FILES}}
    report, expected = otlp_payloads(load_json(directory / "mapping.json"), actual["source.otlp"])
    if actual != expected:
        raise AgentBomError("OTLP source-to-evaluation pack does not recompute")
    for path, name in ((ledger_path, "ledger.json"), (evaluation_path, "evaluation.json")):
        if path is not None and digest(load_json(path)) != digest(json.loads(expected[f"retry/{name}"])):
            raise AgentBomError("downstream evidence does not match the OTLP projection")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aau otlp-retries", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("mapping", type=Path)
    create.add_argument("source", type=Path)
    create.add_argument("--out", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    verify.add_argument("--ledger", type=Path)
    verify.add_argument("--evaluation", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            create_otlp_pack(load_json(args.mapping), _read(args.source), args.out)
            report = verify_otlp_pack(args.out)
        else:
            report = verify_otlp_pack(args.directory, ledger_path=args.ledger, evaluation_path=args.evaluation)
        print(f"OTLP projection verified: {report['task_count']} tasks, {report['attempt_count']} attempts, "
              f"{report['excluded_span_count']} explicitly excluded spans. Not scoring or deployment approval.")
        return 0
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
