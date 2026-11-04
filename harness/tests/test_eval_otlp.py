from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_otlp import create_otlp_pack, otlp_payloads, verify_otlp_pack
from aau_harness.eval_retries import verify_retry_pack
from aau_harness.eval_retry_demo import demo_inputs
from aau_harness.eval_retry_review import create_handoff, verify_handoff


def inputs():
    path = Path(__file__).resolve().parents[1] / "examples/evaluation-review/otlp_retries.py"
    spec = importlib.util.spec_from_file_location("otlp_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.inputs()


def spans(document):
    return document["resourceSpans"][0]["scopeSpans"][0]["spans"]


def attempt(document):
    return next(s for s in spans(document) if s["spanId"] == "0000000000000002"
                and s["traceId"] == "00000000000000000000000000000001")


def root(document):
    return next(s for s in spans(document) if s["spanId"] == "0000000000000001"
                and s["traceId"] == "00000000000000000000000000000001")


def test_projection_retains_bytes_earlier_harm_whole_task_latency_and_excludes_nested_cost(tmp_path):
    mapping, raw = inputs()
    original = deepcopy(mapping)
    report, files = otlp_payloads(mapping, raw)
    assert len(files) == 10 and files["source.otlp"] == raw
    assert report["exported_span_count"] == 7 and report["excluded_span_count"] == 1
    assert report["task_count"] == 2 and report["attempt_count"] == 4
    evaluation = json.loads(files["retry/evaluation.json"])
    first = evaluation["results"][0]
    assert first["metrics"] == {"completion": 1, "unauthorized": 1}
    assert first["cost_usd"] == pytest.approx(.3) and first["n_api_calls"] == 3
    assert first["latency_s"] == 10
    assert "evaluation_context" not in json.loads(files["retry/recording.json"])
    assert (report, files) == otlp_payloads(mapping, raw) and mapping == original
    pack = tmp_path / "pack"
    assert create_otlp_pack(mapping, raw, pack) == verify_otlp_pack(pack)
    assert verify_retry_pack(pack / "retry")["attempt_count"] == 4
    assert report["source_sha256"] == digest(raw)


def test_source_to_policy_handoff_is_bound_and_can_retain_a_failed_outcome(tmp_path):
    mapping, raw = inputs()
    pack, handoff = tmp_path / "projection", tmp_path / "handoff"
    create_otlp_pack(mapping, raw, pack)
    plan = json.loads((pack / "retry/plan.json").read_text())
    ledger = json.loads((pack / "retry/ledger.json").read_text())
    policy, _, _, diagnostics, budget, _ = demo_inputs()
    result = create_handoff(policy, plan, ledger, plan, ledger, diagnostics, handoff, operating_budget=budget)
    assert result["status"] == "constraints_not_met"
    assert verify_handoff(handoff, require_budget=True) == result
    verify_otlp_pack(pack, ledger_path=handoff / "candidate/ledger.json", evaluation_path=handoff / "candidate/evaluation.json")
    changed = deepcopy(ledger)
    changed["tasks"][0]["attempts"][0]["metrics"]["unauthorized"] = 0
    wrong = tmp_path / "wrong.json"
    wrong.write_bytes(rendered(changed))
    with pytest.raises(AgentBomError, match="downstream"):
        verify_otlp_pack(pack, ledger_path=wrong)


def test_missing_attributes_remain_unknown_status_and_tokens_do_not_become_scores_or_costs():
    mapping, raw = inputs()
    doc = json.loads(raw)
    row = attempt(doc)
    row["attributes"] = [{"key": "gen_ai.usage.input_tokens", "value": {"intValue": "100000"}}]
    row["status"] = {"code": 1}
    report, files = otlp_payloads(mapping, rendered(doc))
    first = json.loads(files["retry/evaluation.json"])["results"][0]
    assert first["metrics"] == {"completion": 1}
    assert "cost_usd" not in first and "n_api_calls" not in first
    assert report["tasks"][0]["unmapped_attempt_attribute_names"] == ["gen_ai.usage.input_tokens"]
    coverage = json.loads(files["retry/accounting.json"])["tasks"][0]["operating"]["cost_usd"]
    assert coverage["complete_total"] is None and coverage["observed_sum"] == .2


def test_integer_nanosecond_subtraction_preserves_sub_float_epoch_precision():
    mapping, raw = inputs()
    doc = json.loads(raw)
    row = attempt(doc)
    row["endTimeUnixNano"] = str(int(row["startTimeUnixNano"]) + 1)
    _, files = otlp_payloads(mapping, rendered(doc))
    assert json.loads(files["retry/ledger.json"])["tasks"][0]["attempts"][0]["latency_s"] == 1e-9


@pytest.mark.parametrize("style", ["uppercase", "integer_timestamps", "jsonl", "shuffled"])
def test_supported_otlp_representations(style):
    mapping, raw = inputs()
    _, expected = otlp_payloads(mapping, raw)
    doc = json.loads(raw)
    if style == "uppercase":
        for row in spans(doc):
            for field in ("traceId", "spanId", "parentSpanId"):
                if field in row:
                    row[field] = row[field].upper()
    elif style == "integer_timestamps":
        for row in spans(doc):
            for field in ("startTimeUnixNano", "endTimeUnixNano"):
                if field in row:
                    row[field] = int(row[field])
    elif style == "shuffled":
        spans(doc).reverse()
    elif style == "jsonl":
        mapping["source_format"] = "otlp_jsonl"
        separate = []
        for trace in sorted({s["traceId"] for s in spans(doc)}):
            separate.append({"resourceSpans": [{"scopeSpans": [{"spans": [s for s in spans(doc) if s["traceId"] == trace]}]}]})
        raw = b'\n'.join(json.dumps(item).encode() for item in separate) + b'\n'
    if style != "jsonl":
        raw = rendered(doc)
    _, actual = otlp_payloads(mapping, raw)
    assert actual["retry/ledger.json"] == expected["retry/ledger.json"]
    assert actual["source.otlp"] == raw


@pytest.mark.parametrize("fault", [
    "overlap", "outside_task", "reversed", "wrong_parent", "null_parent", "bad_parent", "bad_trace", "zero_span",
    "duplicate_span", "duplicate_attribute", "typed_string", "bool_score", "float_api_count", "negative_cost",
    "multiple_value_types", "nan_string", "bad_timestamp", "float_timestamp", "negative_timestamp", "huge_timestamp",
    "missing_timestamp", "boolean_timestamp", "unclaimed_span", "missing_span", "same_span_twice", "role_collision",
    "exclude_attempt", "wrong_order", "missing_repeat", "wrong_resource", "nested_task", "parent_cycle",
    "bad_semantics", "unknown_mapping_field", "bad_source_format", "bad_mapping_version", "duplicate_mapping_attribute",
    "unmapped_metric", "blank_reason", "unsupported_latency_mapping", "missing_resource_spans", "bad_scope", "bad_spans",
])
def test_invalid_or_ambiguous_inputs_fail_before_creating_output(tmp_path, fault):
    mapping, raw = inputs()
    doc = json.loads(raw)
    row = attempt(doc)
    task = mapping["tasks"][0]
    attrs = row["attributes"]
    if fault == "overlap":
        row["endTimeUnixNano"] = str(int(row["endTimeUnixNano"]) + 1)
    elif fault == "outside_task":
        root(doc)["endTimeUnixNano"] = row["endTimeUnixNano"]
    elif fault == "reversed":
        row["endTimeUnixNano"] = str(int(row["startTimeUnixNano"]) - 1)
    elif fault == "wrong_parent":
        row["parentSpanId"] = "000000000000000f"
    elif fault == "null_parent":
        row["parentSpanId"] = None
    elif fault == "bad_parent":
        row["parentSpanId"] = []
    elif fault == "bad_trace":
        row["traceId"] = "base64-not-hex"
    elif fault == "zero_span":
        row["spanId"] = "0" * 16
    elif fault == "duplicate_span":
        spans(doc).append(deepcopy(row))
    elif fault == "duplicate_attribute":
        attrs.append(deepcopy(attrs[0]))
    elif fault == "typed_string":
        attrs[0]["value"] = {"stringValue": "1"}
    elif fault == "bool_score":
        attrs[0]["value"] = {"intValue": True}
    elif fault == "float_api_count":
        attrs[-1]["value"] = {"doubleValue": 1.5}
    elif fault == "negative_cost":
        attrs[-2]["value"] = {"doubleValue": -1}
    elif fault == "multiple_value_types":
        attrs[0]["value"] = {"intValue": "1", "doubleValue": 1}
    elif fault == "nan_string":
        attrs[0]["value"] = {"doubleValue": "NaN"}
    elif fault in ("bad_timestamp", "float_timestamp", "negative_timestamp", "huge_timestamp", "boolean_timestamp"):
        row["startTimeUnixNano"] = {"bad_timestamp": "1e9", "float_timestamp": 1.0, "negative_timestamp": "-1",
                                    "huge_timestamp": str(2**64), "boolean_timestamp": True}[fault]
    elif fault == "missing_timestamp":
        del row["startTimeUnixNano"]
    elif fault == "unclaimed_span":
        mapping["excluded_spans"] = []
    elif fault == "missing_span":
        spans(doc).remove(row)
    elif fault == "same_span_twice":
        task["attempt_span_ids"][1] = task["attempt_span_ids"][0]
    elif fault == "role_collision":
        task["attempt_span_ids"][0] = task["task_span_id"]
    elif fault == "exclude_attempt":
        task["attempt_span_ids"].pop(0)
        mapping["excluded_spans"].append({"trace_id": row["traceId"], "span_id": row["spanId"], "reason": "hide failure"})
    elif fault == "wrong_order":
        task["attempt_span_ids"].reverse()
    elif fault == "missing_repeat":
        mapping["accounting_plan"]["n_repeats"] = 3
    elif fault == "wrong_resource":
        spans(doc).remove(row)
        doc["resourceSpans"].append({"scopeSpans": [{"spans": [row]}]})
    elif fault == "nested_task":
        # Same trace, selected second root nested below the first root's attempt via an excluded detail.
        second = mapping["tasks"][1]
        old_trace = second["trace_id"]
        second["trace_id"] = task["trace_id"]
        second["task_span_id"] = "0000000000000011"
        second["attempt_span_ids"] = ["0000000000000012"]
        for other in spans(doc):
            if other["traceId"] == old_trace:
                other["traceId"] = task["trace_id"]
                if other["spanId"] == "0000000000000001":
                    other.update(spanId=second["task_span_id"], parentSpanId="000000000000000f")
                else:
                    other.update(spanId=second["attempt_span_ids"][0], parentSpanId=second["task_span_id"])
    elif fault == "parent_cycle":
        root(doc)["parentSpanId"] = row["spanId"]
    elif fault == "bad_semantics":
        mapping["span_semantics"] = "logical_operation_may_include_retries"
    elif fault == "unknown_mapping_field":
        mapping["automatic_inference"] = True
    elif fault == "bad_source_format":
        mapping["source_format"] = "protobuf"
    elif fault == "bad_mapping_version":
        mapping["mapping_version"] = "2.0"
    elif fault == "duplicate_mapping_attribute":
        mapping["attributes"]["metrics"]["unauthorized"] = mapping["attributes"]["metrics"]["completion"]
    elif fault == "unmapped_metric":
        del mapping["attributes"]["metrics"]["unauthorized"]
    elif fault == "blank_reason":
        mapping["excluded_spans"][0]["reason"] = " "
    elif fault == "unsupported_latency_mapping":
        mapping["attributes"]["operating"]["latency_s"] = "latency"
    elif fault == "missing_resource_spans":
        del doc["resourceSpans"]
    elif fault == "bad_scope":
        doc["resourceSpans"][0]["scopeSpans"] = {}
    elif fault == "bad_spans":
        doc["resourceSpans"][0]["scopeSpans"][0]["spans"] = None
    with pytest.raises(AgentBomError):
        create_otlp_pack(mapping, rendered(doc), tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("raw", [b'', b'\xff', b'{"resourceSpans":[],"resourceSpans":[]}',
                                  b'{"resourceSpans":[],"metadata":NaN}', b'{"resourceSpans":[],"x":1e999}',
                                  b'{"resourceSpans":[],"x":"\\ud800"}', b'[]', b' ' * 2_000_001])
def test_malformed_source_rejected(raw):
    mapping, _ = inputs()
    with pytest.raises(AgentBomError):
        otlp_payloads(mapping, raw)


@pytest.mark.parametrize("member", ["source.otlp", "mapping.json", "projection.json", "manifest.json",
                                     "retry/plan.json", "retry/ledger.json", "retry/recording.json", "retry/evaluation.json",
                                     "retry/accounting.json", "retry/manifest.json"])
def test_every_member_is_verified_even_when_outer_manifest_is_rehashed(tmp_path, member):
    mapping, raw = inputs()
    pack = tmp_path / "pack"
    create_otlp_pack(mapping, raw, pack)
    target = pack / member
    target.write_bytes(target.read_bytes() + b' ')
    if member != "manifest.json":
        manifest = json.loads((pack / "manifest.json").read_text())
        manifest["files"][member] = digest(target.read_bytes())
        (pack / "manifest.json").write_bytes(rendered(manifest))
    # Raw source whitespace is intentionally retained: rehashing only the manifest still
    # leaves the projection's original source hash, so the full chain rejects it too.
    with pytest.raises(AgentBomError):
        verify_otlp_pack(pack)


@pytest.mark.parametrize("fault", ["root_symlink", "nested_symlink", "file_symlink", "extra", "missing", "directory_member", "large"])
def test_pack_layout_and_file_boundaries(tmp_path, fault):
    mapping, raw = inputs()
    pack = tmp_path / "pack"
    create_otlp_pack(mapping, raw, pack)
    target = pack
    if fault == "root_symlink":
        target = tmp_path / "alias"
        target.symlink_to(pack, target_is_directory=True)
    elif fault == "nested_symlink":
        (pack / "retry").rename(tmp_path / "retry")
        (pack / "retry").symlink_to(tmp_path / "retry", target_is_directory=True)
    elif fault == "file_symlink":
        (pack / "source.otlp").rename(tmp_path / "source.otlp")
        (pack / "source.otlp").symlink_to(tmp_path / "source.otlp")
    elif fault == "extra":
        (pack / "retry/extra.json").write_text('{}')
    elif fault == "missing":
        (pack / "retry/ledger.json").unlink()
    elif fault == "directory_member":
        (pack / "source.otlp").unlink()
        (pack / "source.otlp").mkdir()
    elif fault == "large":
        (pack / "source.otlp").write_bytes(b' ' * 2_000_001)
    with pytest.raises(AgentBomError):
        verify_otlp_pack(target)


def test_cli_create_verify_no_overwrite_and_wrong_downstream(tmp_path, monkeypatch, capsys):
    mapping, raw = inputs()
    monkeypatch.chdir(tmp_path)
    Path("mapping.json").write_bytes(rendered(mapping))
    Path("source.json").write_bytes(raw)
    command = ["otlp-retries", "create", "mapping.json", "source.json", "--out", "pack"]
    assert main(command) == 0
    assert main(command) == 2
    assert main(["otlp-retries", "verify", "pack", "--ledger", "pack/retry/ledger.json",
                 "--evaluation", "pack/retry/evaluation.json"]) == 0
    Path("wrong.json").write_text('{}')
    assert main(["otlp-retries", "verify", "pack", "--evaluation", "wrong.json"]) == 2
    output = capsys.readouterr().out
    assert "1 explicitly excluded spans" in output and "000000000000000f" not in output


def test_expansion_is_bounded_before_materializing_the_full_ledger(monkeypatch):
    from aau_harness import eval_otlp

    mapping, raw = inputs()
    doc = json.loads(raw)
    prototype, task_root = deepcopy(attempt(doc)), deepcopy(root(doc))
    mapping["tasks"] = mapping["tasks"][:1]
    mapping["accounting_plan"]["n_repeats"] = 1
    mapping["excluded_spans"] = []
    mapping["tasks"][0]["attempt_span_ids"] = []
    for old, new in (("completion", "c" * 200), ("unauthorized", "u" * 200)):
        mapping["accounting_plan"]["metric_reducers"][new] = mapping["accounting_plan"]["metric_reducers"].pop(old)
        mapping["attributes"]["metrics"][new] = mapping["attributes"]["metrics"].pop(old)
    values = [task_root]
    epoch = int(task_root["startTimeUnixNano"])
    task_root["endTimeUnixNano"] = str(epoch + 100_000_000_000)
    for index in range(100):
        row = deepcopy(prototype)
        row.update(spanId=f"{index + 2:016x}", startTimeUnixNano=str(epoch + index * 1_000_000_000),
                   endTimeUnixNano=str(epoch + (index + 1) * 1_000_000_000))
        mapping["tasks"][0]["attempt_span_ids"].append(row["spanId"])
        values.append(row)
    doc["resourceSpans"][0]["scopeSpans"][0]["spans"] = values
    raw = json.dumps(doc, separators=(',', ':')).encode()
    monkeypatch.setattr(eval_otlp, "MAX_JSON_BYTES", len(raw) + 1)
    monkeypatch.setattr(eval_otlp, "retry_payloads", lambda *_: pytest.fail("expanded ledger reached downstream materialization"))
    with pytest.raises(AgentBomError, match="expanded OTLP"):
        otlp_payloads(mapping, raw)
