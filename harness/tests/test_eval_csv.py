from copy import deepcopy
import csv
from io import StringIO
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, MAX_JSON_BYTES, digest
from aau_harness.catalog_cli import main
from aau_harness.eval_csv import FILES, create_csv_pack, csv_payloads, verify_csv_pack
from aau_harness.eval_operations import review_operations
from aau_harness.eval_pack import create_pack, verify_pack


def inputs():
    root = Path(__file__).resolve().parents[1] / "examples/evaluation-review"
    return json.loads((root / "csv-plan.json").read_text()), (root / "scored-observations.csv").read_bytes()


def test_csv_retains_original_bytes_partial_measurements_and_source_hashes(tmp_path):
    plan, raw = inputs()
    raw = b"\xef\xbb\xbf" + raw.replace(b"\n", b"\r\n")
    original = deepcopy(plan)
    report = create_csv_pack(plan, raw, tmp_path / "pack")
    assert plan == original
    assert report == verify_csv_pack(tmp_path / "pack")
    assert (tmp_path / "pack/source.csv").read_bytes() == raw
    assert report["source_csv_sha256"] == digest(raw)
    assert report["operating_coverage"]["cost_usd"]["reporting_observations"] == 1
    evaluation = json.loads((tmp_path / "pack/evaluation.json").read_text())
    assert "cost_usd" not in evaluation["results"][1]
    operating = review_operations(evaluation, criteria=[{"metric": "completion", "direction": "higher", "limit": 1}], cost_basis="synthetic")
    assert operating["overall"]["cost"]["total_usd"] is None
    assert operating["overall"]["latency"]["p95_s"] == 12
    assert not report["unreported_metrics"]
    assert csv_payloads(plan, raw) == csv_payloads(plan, raw)


def test_header_order_is_not_column_meaning_and_numeric_precision_is_preserved():
    plan, raw = inputs()
    rows = list(csv.reader(StringIO(raw.decode())))
    rows[1][4] = "0.000000123456"
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerows([list(reversed(row)) for row in rows])
    _, payloads = csv_payloads(plan, stream.getvalue().encode())
    assert json.loads(payloads["evaluation.json"])["results"][0]["cost_usd"] == .000000123456


def test_empty_metric_cells_are_not_coerced_and_unreported_columns_are_disclosed():
    plan, raw = inputs()
    raw = raw.replace(b"service,0,1,0,", b"service,0,1,,").replace(b"service,1,1,1,", b"service,1,1,,")
    report, payloads = csv_payloads(plan, raw)
    assert report["unreported_metrics"] == ["unauthorized"]
    assert report["declared_metrics"] == ["completion", "unauthorized"]
    assert all("unauthorized" not in row["metrics"] for row in json.loads(payloads["recording.json"])["observations"])


@pytest.mark.parametrize("defect", ["extra-header", "missing-header", "duplicate-header", "long-row", "short-row",
                                    "blank-row", "duplicate-case", "missing-case", "unknown-case", "one-based-repeat",
                                    "bad-quote", "nul", "encoding", "empty", "oversized"])
def test_csv_rejects_ambiguous_or_incomplete_sources_before_creating_output(tmp_path, defect):
    plan, raw = inputs()
    lines = raw.splitlines(keepends=True)
    if defect == "extra-header":
        raw = raw.replace(b"calls\n", b"calls,private_prompt\n")
    elif defect == "missing-header":
        raw = raw.replace(b",calls\n", b"\n")
    elif defect == "duplicate-header":
        raw = raw.replace(b",calls\n", b",usd\n")
    elif defect == "long-row":
        raw = raw.replace(b"1.5,2\n", b"1.5,2,extra\n")
    elif defect == "short-row":
        raw = raw.replace(b"1.5,2\n", b"1.5\n")
    elif defect == "blank-row":
        raw += b"\n"
    elif defect == "duplicate-case":
        raw = lines[0] + lines[1] + lines[1]
    elif defect == "missing-case":
        raw = lines[0] + lines[1]
    elif defect == "unknown-case":
        raw = raw.replace(b"service,1", b"other,1")
    elif defect == "one-based-repeat":
        raw = raw.replace(b"service,0", b"service,2")
    elif defect == "bad-quote":
        raw = lines[0] + b'"unterminated'
    elif defect == "nul":
        raw += b"\x00"
    elif defect == "encoding":
        raw += b"\xff"
    elif defect == "empty":
        raw = b""
    else:
        raw = b"x" * (MAX_JSON_BYTES + 1)
    with pytest.raises(AgentBomError):
        create_csv_pack(plan, raw, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("value", ["=1+1", "NaN", "Infinity", "true", "null", "$0.1", "1,000", "0x10", "1e9999", "-1", '"1"'])
def test_numeric_cells_do_not_execute_formulas_or_coerce_invalid_values(value):
    plan, raw = inputs()
    rows = list(csv.reader(StringIO(raw.decode())))
    rows[1][4] = value
    stream = StringIO(newline="")
    csv.writer(stream).writerows(rows)
    with pytest.raises(AgentBomError):
        csv_payloads(plan, stream.getvalue().encode())


@pytest.mark.parametrize("defect", ["version", "extra", "shared-column", "unknown-operation", "bad-map", "empty-map",
                                    "repeat-type", "scenario-census", "context"])
def test_invalid_conversion_plans_are_rejected(defect):
    plan, raw = inputs()
    if defect == "version":
        plan["plan_version"] = "unknown"
    elif defect == "extra":
        plan["skip_errors"] = True
    elif defect == "shared-column":
        plan["columns"]["metrics"]["completion"] = "usd"
    elif defect == "unknown-operation":
        plan["columns"]["operating"]["latency_ms"] = "milliseconds"
    elif defect == "bad-map":
        plan["columns"]["metrics"] = []
    elif defect == "empty-map":
        plan["columns"]["metrics"] = {}
    elif defect == "repeat-type":
        plan["n_repeats"] = True
    elif defect == "scenario-census":
        plan["scenario_ids"].append("unmeasured")
    else:
        plan["evaluation_context"] = None
    with pytest.raises(AgentBomError):
        csv_payloads(plan, raw)


@pytest.mark.parametrize("member", sorted(FILES))
def test_every_conversion_pack_member_is_recomputed(tmp_path, member):
    plan, raw = inputs()
    pack = tmp_path / "pack"
    create_csv_pack(plan, raw, pack)
    path = pack / member
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(AgentBomError):
        verify_csv_pack(pack)


def test_changed_derived_scores_and_rehashed_manifest_do_not_fake_verification(tmp_path):
    plan, raw = inputs()
    pack = tmp_path / "pack"
    create_csv_pack(plan, raw, pack)
    path = pack / "evaluation.json"
    evaluation = json.loads(path.read_text())
    evaluation["results"][1]["metrics"]["unauthorized"] = 0
    path.write_text(json.dumps(evaluation))
    manifest = json.loads((pack / "manifest.json").read_text())
    manifest["files"]["evaluation.json"] = digest(path.read_bytes())
    (pack / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(AgentBomError):
        verify_csv_pack(pack)


def test_conversion_binds_into_existing_recording_dossier(tmp_path):
    plan, raw = inputs()
    converted, dossier = tmp_path / "converted", tmp_path / "dossier"
    create_csv_pack(plan, raw, converted)
    source = json.loads((converted / "recording.json").read_text())
    criteria = [{"metric": "completion", "direction": "higher", "limit": 1},
                {"metric": "unauthorized", "direction": "lower", "limit": 0}]
    policy = {"policy_version": "aau-evaluation-review-policy/1.0", "scenario_ids": ["service"],
              "minimum_repeats": 2, "metrics": [{"metric": rule["metric"], "direction": rule["direction"],
                  "candidate_observation_limit": rule["limit"], "max_mean_regression": 0,
                  "max_regressed_scenarios": 0} for rule in criteria]}
    diagnostic = {"plan_version": "aau-evaluation-diagnostics/1.0", "criteria": criteria, "draw_sizes": [1, 2],
                  "cost_basis": {"baseline": "synthetic", "candidate": "synthetic"}}
    create_pack(policy, source, source, dossier, recordings=True, diagnostics=diagnostic)
    assert verify_pack(dossier, require_recordings=True, require_diagnostics=True)["status"] == "constraints_not_met"
    verify_csv_pack(converted, evaluation_path=dossier / "candidate.json")
    candidate = json.loads((dossier / "candidate.json").read_text())
    candidate["results"][0]["cost_usd"] = 99
    (dossier / "candidate.json").write_text(json.dumps(candidate))
    with pytest.raises(AgentBomError, match="downstream"):
        verify_csv_pack(converted, evaluation_path=dossier / "candidate.json")


@pytest.mark.parametrize("defect", ["missing", "extra", "symlink", "oversized"])
def test_conversion_verification_rejects_invalid_member_sets(tmp_path, defect):
    plan, raw = inputs()
    pack = tmp_path / "pack"
    create_csv_pack(plan, raw, pack)
    if defect == "missing":
        (pack / "source.csv").unlink()
    elif defect == "extra":
        (pack / "extra.json").write_text("{}")
    elif defect == "symlink":
        target = tmp_path / "source.csv"
        (pack / "source.csv").rename(target)
        (pack / "source.csv").symlink_to(target)
    else:
        (pack / "source.csv").write_bytes(b"x" * (MAX_JSON_BYTES + 1))
    with pytest.raises(AgentBomError):
        verify_csv_pack(pack)


def test_cli_complete_workflow_preserves_paths_and_avoids_payload_logging(tmp_path, capsys):
    plan, raw = inputs()
    plan_path, csv_path = tmp_path / "plan.json", tmp_path / "input.csv"
    plan_path.write_text(json.dumps(plan))
    csv_path.write_bytes(raw)
    destination = tmp_path / "converted"
    args = ["csv-eval", "create", str(plan_path), str(csv_path), "--out", str(destination)]
    assert main(args) == 0
    assert main(["csv-eval", "verify", str(destination), "--evaluation", str(destination / "evaluation.json")]) == 0
    assert main(args) == 2
    csv_path.write_bytes(raw.replace(b"0.10", b"PRIVATE_INVALID_VALUE"))
    args[-1] = str(tmp_path / "invalid")
    assert main(args) == 2
    output = capsys.readouterr()
    assert "PRIVATE_INVALID_VALUE" not in output.out + output.err
    assert not (tmp_path / "invalid").exists()


def test_csv_expansion_is_bounded_before_creating_output(tmp_path, monkeypatch):
    from aau_harness import eval_csv

    monkeypatch.setattr(eval_csv, "MAX_JSON_BYTES", 700)
    plan = {"plan_version": "aau-csv-observation-import/1.0", "source_label": "synthetic",
            "scenario_ids": ["a"], "n_repeats": 20,
            "columns": {"scenario_id": "id", "repeat": "r", "metrics": {"m" * 200: "x"}, "operating": {}}}
    raw = ("id,r,x\n" + "".join(f"a,{repeat},1\n" for repeat in range(20))).encode()
    assert len(raw) < 700
    with pytest.raises(AgentBomError, match="expanded observations"):
        create_csv_pack(plan, raw, tmp_path / "oversized")
    assert not (tmp_path / "oversized").exists()
