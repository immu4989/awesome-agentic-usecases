import json
import shlex
import sys
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, load_json, main, run_conformance
from aau_harness.authority_starter import create_starter
from aau_harness.authority_check import check_authority


ROOT = Path(__file__).resolve().parents[2]
BOM = ROOT / "agent-capability-bom/examples/candidate.json"


def test_starter_runs_but_cannot_claim_implemented_policy(tmp_path):
    out = tmp_path / "authority workspace"
    assert main(["init-adapter", str(BOM), "--out", str(out)]) == 0
    bom = load_json(out / "inventory.json")
    assert bom == load_json(BOM)
    suite = load_json(out / "suite.json")
    receipt = run_conformance(
        bom, suite, "command", shlex.join([sys.executable, str(out / "adapter.py")]),
        adapter_artifact=out / "adapter.py", workspace=out,
    )
    assert receipt["status"] == "evidence_failed"
    assert receipt["metrics"]["legitimate_block_count"] == 3
    assert receipt["metrics"]["exact_count"] == 0
    assert all(row["actual_reason_codes"] == ["ADAPTER_NOT_IMPLEMENTED"]
               for row in receipt["results"])
    assert set(path.name for path in out.iterdir()) == {
        "README.md", "adapter.py", "inventory.json", "suite.json",
    }


def test_starter_preserves_existing_work_and_rejects_invalid_inventory(tmp_path):
    out = tmp_path / "existing"
    out.mkdir()
    sentinel = out / "adapter.py"
    sentinel.write_text("user work")
    with pytest.raises(AgentBomError, match="refusing to overwrite"):
        create_starter(load_json(BOM), out)
    assert sentinel.read_text() == "user work"
    invalid = json.loads(BOM.read_text())
    invalid["release_id"] = ""
    with pytest.raises(AgentBomError):
        create_starter(invalid, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


def test_one_command_check_keeps_failed_reports_and_refuses_existing_output(tmp_path):
    workspace = tmp_path / "workspace"
    create_starter(load_json(BOM), workspace)
    adapter = workspace / "adapter.py"
    out = tmp_path / "check"
    args = ["check-authority", str(workspace / "inventory.json"),
            "--command", shlex.join([sys.executable, str(adapter)]),
            "--adapter-artifact", str(adapter), "--workspace", str(workspace), "--out", str(out)]
    assert main(args) == 1
    assert {p.name for p in out.iterdir()} == {
        "inventory.json", "suite.json", "receipt.json", "report.json", "review.html",
        "results.xml", "completion.json"}
    assert load_json(out / "completion.json")["status"] == "evidence_failed"
    assert load_json(out / "report.json")["exact_count"] == 0
    assert main(["verify-conformance", str(out / "receipt.json"), str(out / "inventory.json"),
                 str(out / "suite.json"), "--adapter-artifact", str(adapter),
                 "--workspace", str(workspace)]) == 1
    saved = (out / "receipt.json").read_bytes()
    # An invalid command is never executed when the output already exists.
    with pytest.raises(AgentBomError, match="overwrite"):
        check_authority(load_json(BOM), "not-a-command", adapter, workspace, out)
    assert (out / "receipt.json").read_bytes() == saved
    adapter.write_text("print('invalid json')")
    args[-1] = str(tmp_path / "broken")
    assert main(args) == 2
    assert not (tmp_path / "broken").exists()


def test_one_command_check_passes_with_explicit_reference_example(tmp_path):
    adapter = ROOT / "agent-capability-bom/examples/reference_conformance_adapter.py"
    out = tmp_path / "passing"
    assert main(["check-authority", str(BOM), "--command",
                 shlex.join([sys.executable, str(adapter)]), "--adapter-artifact", str(adapter),
                 "--workspace", str(ROOT), "--out", str(out)]) == 0
    completion = load_json(out / "completion.json")
    assert completion["status"] == "evidence_passed"
    assert completion["exact_count"] == completion["case_count"]
