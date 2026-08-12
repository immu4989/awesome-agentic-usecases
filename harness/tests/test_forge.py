import ast
import json
from pathlib import Path

import pytest

from aau_harness.forge import BriefError, deterministic_seed, forge, load_brief


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "docs" / "studio-spec.example.json"


def test_example_brief_is_valid_and_seed_is_stable():
    brief = load_brief(EXAMPLE)
    assert brief["contract_version"] == "aau-studio/1.0"
    assert deterministic_seed(brief) == deterministic_seed(json.loads(EXAMPLE.read_text()))
    brief["created_at"] = "2099-01-01T00:00:00Z"
    assert deterministic_seed(brief) == deterministic_seed(load_brief(EXAMPLE))
    assert 1000 <= deterministic_seed(brief) <= 9998


def test_forge_emits_runnable_handoff_without_claiming_validation(tmp_path):
    dest = forge(
        EXAMPLE,
        "regional-emergency-notice-lab",
        tmp_path,
        ROOT,
        verify=False,
    )
    rel = dest.relative_to(tmp_path)
    assert rel == Path("pipeline-safety-emergency-reporting/regional-emergency-notice-lab")
    assert (dest / "evaluation-brief.json").is_file()
    assert (dest / "evaluation-brief.schema.json").is_file()
    assert (dest / "ADAPTATION_CHECKLIST.md").is_file()
    manifest = json.loads((dest / "aau-forge.json").read_text())
    assert manifest["forge_version"] == "aau-forge/1.0"
    assert manifest["status"] == "adaptation_required"
    assert manifest["verification"]["status"] == "not_run"
    assert manifest["source"]["case"]["path"] == (
        "pipeline-safety/incident-notification-coordinator"
    )
    readme = (dest / "README.md").read_text()
    assert "Runnable does not mean domain-validated" in readme
    assert "regional pipeline operator" in readme
    workflow = tmp_path / ".github" / "workflows" / "forge-regional-emergency-notice-lab.yml"
    assert workflow.is_file()
    assert str(rel) in workflow.read_text()
    for path in dest.rglob("*.py"):
        ast.parse(path.read_text(), filename=str(path))


def test_forge_refuses_bad_contract_and_overwrite(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"contract_version": "unknown"}))
    with pytest.raises(BriefError, match="unsupported contract_version"):
        load_brief(bad)

    forge(EXAMPLE, "notice-lab", tmp_path, ROOT, verify=False)
    with pytest.raises(BriefError, match="refusing to overwrite"):
        forge(EXAMPLE, "notice-lab", tmp_path, ROOT, verify=False)
