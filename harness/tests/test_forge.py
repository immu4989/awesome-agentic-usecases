import ast
import json
from pathlib import Path

import pytest

from aau_harness.forge import (
    BriefError,
    deterministic_seed,
    diagnose_forged_lab,
    forge,
    load_brief,
)


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
    assert manifest["forge_version"] == "aau-forge/2.0"
    assert manifest["status"] == "adaptation_required"
    assert manifest["generator"]["mode"] == "contract-aware"
    assert manifest["generator"]["contract"] == "Critical Event Fan-Out"
    assert manifest["verification"]["status"] == "not_run"
    assert manifest["source"]["case"]["path"] == (
        "pipeline-safety/incident-notification-coordinator"
    )
    readme = (dest / "README.md").read_text()
    assert "Runnable does not mean domain-validated" in readme
    assert "regional pipeline operator" in readme
    assert "critical_event_fanout_exact" in readme
    blueprint = json.loads((dest / "contract-blueprint.json").read_text())
    assert blueprint["contract"] == "Critical Event Fan-Out"
    workflow = tmp_path / ".github" / "workflows" / "forge-regional-emergency-notice-lab.yml"
    assert workflow.is_file()
    assert str(rel) in workflow.read_text()
    for path in dest.rglob("*.py"):
        ast.parse(path.read_text(), filename=str(path))


@pytest.mark.parametrize(
    ("example", "contract", "metric"),
    [
        ("studio-spec.decision-gate.json", "Decision Gate", "decision_gate_exact"),
        ("studio-spec.rights-continuity.json", "Rights Continuity", "rights_continuity_exact"),
        (
            "studio-spec.critical-event-fanout.json",
            "Critical Event Fan-Out",
            "critical_event_fanout_exact",
        ),
    ],
)
def test_contract_registry_emits_distinct_executable_blueprints(
    tmp_path, example, contract, metric
):
    brief = ROOT / "docs" / "forge-examples" / example
    dest = forge(brief, f"{contract.lower().replace(' ', '-')}-lab", tmp_path, ROOT, verify=False)
    blueprint = json.loads((dest / "contract-blueprint.json").read_text())
    assert blueprint["contract"] == contract
    assert blueprint["exact_metric"] == metric
    test_source = next((dest / "tests").glob("test_*.py")).read_text()
    assert metric in test_source
    assert contract in (dest / "README.md").read_text()


def test_forge_doctor_explains_why_generated_lab_is_not_publishable(tmp_path):
    dest = forge(EXAMPLE, "doctor-example", tmp_path, ROOT, verify=False)
    report = diagnose_forged_lab(dest)
    assert report["publication_ready"] is False
    assert report["contract"] == "Critical Event Fan-Out"
    checks = {item["check"]: item for item in report["checks"]}
    assert checks["contract blueprint"]["passed"] is True
    assert checks["domain truth replaced"]["passed"] is False
    assert checks["real-model evidence"]["passed"] is False


def test_forge_refuses_bad_contract_and_overwrite(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"contract_version": "unknown"}))
    with pytest.raises(BriefError, match="unsupported contract_version"):
        load_brief(bad)

    forge(EXAMPLE, "notice-lab", tmp_path, ROOT, verify=False)
    with pytest.raises(BriefError, match="refusing to overwrite"):
        forge(EXAMPLE, "notice-lab", tmp_path, ROOT, verify=False)
