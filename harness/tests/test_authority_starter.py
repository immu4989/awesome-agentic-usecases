import json
import shlex
import sys
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, load_json, main, run_conformance
from aau_harness.authority_starter import create_starter


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
