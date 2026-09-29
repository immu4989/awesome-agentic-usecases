import json
import shlex
import sys
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, load_json, main, run_conformance
from aau_harness.authority_starter import create_starter
from aau_harness.authority_check import check_authority, verify_check
from aau_harness.authority_campaign import repeat_authority, verify_campaign


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
    assert main(["verify-authority-check", str(out), "--adapter-artifact", str(adapter),
                 "--workspace", str(workspace)]) == 1
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
    assert main(["verify-authority-check", str(out), "--adapter-artifact", str(adapter),
                 "--workspace", str(ROOT)]) == 0
    for name in ("report.json", "completion.json", "review.html", "results.xml"):
        path = out / name
        original = path.read_bytes()
        path.write_bytes(b"{}" if name.endswith(".json") else b"altered presentation")
        with pytest.raises(AgentBomError, match="does not recompute"):
            verify_check(out, adapter, ROOT)
        path.write_bytes(original)
    (out / "unexpected.txt").write_text("extra")
    with pytest.raises(AgentBomError, match="file set"):
        verify_check(out, adapter, ROOT)
    (out / "unexpected.txt").unlink()
    original = (out / "completion.json").read_bytes()
    (out / "completion.json").unlink()
    with pytest.raises(AgentBomError, match="file set"):
        verify_check(out, adapter, ROOT)
    outside = tmp_path / "marker.json"
    outside.write_bytes(original)
    (out / "completion.json").symlink_to(outside)
    with pytest.raises(AgentBomError, match="invalid check file"):
        verify_check(out, adapter, ROOT)


def test_repeated_staging_collects_all_failed_runs_and_checks_bounds(tmp_path):
    workspace = tmp_path / "workspace"
    create_starter(load_json(BOM), workspace)
    adapter = workspace / "adapter.py"
    out = tmp_path / "campaign"
    command = shlex.join([sys.executable, str(adapter)])
    args = ["repeat-authority", str(workspace / "inventory.json"), "--command", command,
            "--adapter-artifact", str(adapter), "--workspace", str(workspace),
            "--runs", "2", "--out", str(out)]
    assert main(args) == 1
    assert load_json(out / "completion.json")["completed_runs"] == 2
    report = load_json(out / "repeatability.json")
    assert report["counts"]["stable_failure"] == report["case_count"]
    assert report["counts"]["unstable"] == 0
    assert main(["verify-authority-campaign", str(out), "--adapter-artifact", str(adapter),
                 "--workspace", str(workspace)]) == 1
    for name in ("run-001", "run-002"):
        assert verify_check(out / name, adapter, workspace)["status"] == "evidence_failed"
    with pytest.raises(AgentBomError, match="overwrite"):
        repeat_authority(load_json(BOM), "never execute", adapter, workspace, out, 2)
    for count in (True, 1, 11):
        with pytest.raises(AgentBomError, match="2 to 10"):
            repeat_authority(load_json(BOM), command, adapter, workspace, tmp_path / "invalid", count)
    assert not (tmp_path / "invalid").exists()


def test_repeated_staging_interruption_keeps_completed_runs_without_summary(tmp_path, monkeypatch):
    import aau_harness.authority_campaign as campaign
    adapter = ROOT / "agent-capability-bom/examples/reference_conformance_adapter.py"
    original = campaign.check_authority
    attempts = []
    def fail_second(*args):
        attempts.append(1)
        if len(attempts) == 2:
            raise AgentBomError("adapter protocol error")
        return original(*args)
    monkeypatch.setattr(campaign, "check_authority", fail_second)
    out = tmp_path / "interrupted"
    with pytest.raises(AgentBomError, match="protocol error"):
        repeat_authority(load_json(BOM), shlex.join([sys.executable, str(adapter)]),
                         adapter, ROOT, out, 3)
    assert len(attempts) == 2
    assert verify_check(out / "run-001", adapter, ROOT)["status"] == "evidence_passed"
    assert not (out / "repeatability.json").exists()
    assert not (out / "completion.json").exists()


def test_repeated_reference_example_completes_passing_campaign(tmp_path, monkeypatch):
    adapter = ROOT / "agent-capability-bom/examples/reference_conformance_adapter.py"
    out = tmp_path / "reference-campaign"
    args = ["repeat-authority", str(BOM), "--command", shlex.join([sys.executable, str(adapter)]),
            "--adapter-artifact", str(adapter), "--workspace", str(ROOT),
            "--runs", "2", "--out", str(out)]
    assert main(args) == 0
    report = load_json(out / "repeatability.json")
    assert report["counts"]["stable_pass"] == report["case_count"]
    assert report["distinct_receipt_count"] == 1
    assert load_json(out / "completion.json")["status"] == "evidence_passed"
    import aau_harness.authority_check as check
    def forbid_execution(*args, **kwargs):
        raise AssertionError("verification must not execute adapters")
    monkeypatch.setattr(check, "run_conformance", forbid_execution)
    verify_args = ["verify-authority-campaign", str(out), "--adapter-artifact", str(adapter),
                   "--workspace", str(ROOT)]
    assert main(verify_args) == 0
    for name in ("completion.json", "repeatability.json", "run-002/report.json"):
        path = out / name
        saved = path.read_bytes()
        path.write_text("{}")
        assert main(verify_args) == 2
        path.write_bytes(saved)
    (out / "extra").mkdir()
    with pytest.raises(AgentBomError, match="file set"):
        verify_campaign(out, adapter, ROOT)
    (out / "extra").rmdir()
    (out / "run-002").rename(tmp_path / "moved-run")
    with pytest.raises(AgentBomError, match="file set"):
        verify_campaign(out, adapter, ROOT)
    (out / "run-002").symlink_to(tmp_path / "moved-run", target_is_directory=True)
    with pytest.raises(AgentBomError, match="real directory"):
        verify_campaign(out, adapter, ROOT)
