import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, generate_conformance_suite, load_json, main, run_conformance
from aau_harness.authority_report import explain_conformance


ROOT = Path(__file__).resolve().parents[2]


def test_report_separates_decision_and_reason_failures_and_omits_inputs():
    bom = load_json(ROOT / "agent-capability-bom/examples/candidate.json")
    suite = generate_conformance_suite(bom)
    receipt = run_conformance(bom, suite, "reference")
    clean = next(i for i, case in enumerate(suite["cases"]) if case["clean_twin"])
    blocked = [i for i, case in enumerate(suite["cases"]) if not case["clean_twin"]]
    receipt["results"][clean].update(actual_decision="block", exact=False)
    receipt["results"][blocked[0]].update(actual_decision="allow", exact=False)
    receipt["results"][blocked[1]].update(actual_reason_codes=["WRONG_REASON"], exact=False)
    receipt["metrics"].update(exact_count=16, unsafe_allow_count=1, legitimate_block_count=1)
    receipt["status"] = "evidence_failed"
    report = explain_conformance(receipt, bom, suite)
    assert report["categories"] == {"unsafe_allow": 1, "legitimate_block": 1, "reason_mismatch": 1}
    assert report["mismatch_count"] == 3
    assert not report["adapter_bytes_checked"]
    reason = next(row for row in report["mismatches"] if row["category"] == "reason_mismatch")
    assert reason["missing_reason_codes"] == suite["cases"][blocked[1]]["expected_reason_codes"]
    assert reason["unexpected_reason_codes"] == ["WRONG_REASON"]
    assert all("input" not in row for row in report["mismatches"])
    assert report == explain_conformance(receipt, bom, suite)
    receipt["metrics"]["exact_count"] = 19
    with pytest.raises(AgentBomError, match="metrics do not recompute"):
        explain_conformance(receipt, bom, suite)


def test_passing_report_has_no_invented_failures():
    bom = load_json(ROOT / "agent-capability-bom/examples/candidate.json")
    suite = generate_conformance_suite(bom)
    report = explain_conformance(run_conformance(bom, suite, "reference"), bom, suite)
    assert report["mismatch_count"] == 0
    assert report["mismatches"] == []
    assert report["status"] == "evidence_passed"


@pytest.mark.parametrize("failed", [False, True])
def test_cli_exit_codes_verification_and_no_overwrite(tmp_path, failed):
    bom = load_json(ROOT / "agent-capability-bom/examples/candidate.json")
    suite = generate_conformance_suite(bom)
    receipt = run_conformance(bom, suite, "reference")
    if failed:
        receipt["results"][0].update(actual_reason_codes=["WRONG_REASON"], exact=False)
        receipt["metrics"]["exact_count"] -= 1
        receipt["status"] = "evidence_failed"
    for name, value in (("bom", bom), ("suite", suite), ("receipt", receipt)):
        (tmp_path / f"{name}.json").write_text(json.dumps(value))
    output = tmp_path / "report.json"
    args = ["explain-conformance", str(tmp_path / "receipt.json"),
            str(tmp_path / "bom.json"), str(tmp_path / "suite.json"), "--out", str(output)]
    assert main(args) == int(failed)
    saved = output.read_bytes()
    assert load_json(output)["mismatch_count"] == int(failed)
    assert main(args) == 2
    assert output.read_bytes() == saved
    receipt["metrics"]["exact_count"] = -1
    (tmp_path / "receipt.json").write_text(json.dumps(receipt))
    args[-1] = str(tmp_path / "invalid-report.json")
    assert main(args) == 2
    assert not (tmp_path / "invalid-report.json").exists()
