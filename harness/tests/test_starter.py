import json
import subprocess
import sys

import pytest

from aau_harness.catalog_cli import main as aau_main
from aau_harness.evaluate import command_adapter, evaluate_suite, load_suite
from aau_harness.starter import (
    ACTION_PINS,
    PACKAGE_VERSION,
    STARTER_VERSION,
    TEMPLATES,
    browser_contract,
    doctor_project,
    init_project,
)


@pytest.mark.parametrize("template_id", TEMPLATES)
def test_every_template_generates_a_ready_runnable_starter(tmp_path, template_id):
    target = tmp_path / template_id
    report = init_project(template_id, target, template_id=template_id)
    assert report.ready is True
    assert all(check.status == "pass" for check in report.checks)

    suite = load_suite(target / "suite.json")
    invoke = command_adapter(
        f"{sys.executable} {target / 'adapter_command.py'}",
        2,
    )
    receipt, _ = evaluate_suite(suite, invoke, "command")
    assert receipt["metrics"]["exact_rate"] == 1.0
    assert receipt["privacy"]["scenario_inputs_included"] is False
    assert receipt["privacy"]["expected_answers_included"] is False

    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=target,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_init_refuses_overwrite_and_path_traversal(tmp_path):
    target = tmp_path / "existing"
    target.mkdir()
    marker = target / "keep.txt"
    marker.write_text("user owned\n")
    with pytest.raises(ValueError, match="refusing to overwrite"):
        init_project("existing", target)
    assert marker.read_text() == "user owned\n"

    with pytest.raises(ValueError, match="name must be"):
        init_project("../escape", tmp_path / "escape")


def test_doctor_warns_on_customization_but_fails_closed_on_suite_boundary(tmp_path):
    target = tmp_path / "customized"
    init_project("customized", target)
    readme = target / "README.md"
    readme.write_text(readme.read_text() + "\nLocal notes.\n")
    report = doctor_project(target)
    assert report.ready is True
    assert next(item for item in report.checks if item.check_id == "template-drift").status == "warn"

    suite_path = target / "suite.json"
    suite = json.loads(suite_path.read_text())
    suite["sharing"]["human_review_complete"] = False
    suite_path.write_text(json.dumps(suite))
    report = doctor_project(target)
    assert report.ready is False
    assert next(item for item in report.checks if item.check_id == "suite-contract").status == "fail"


def test_doctor_does_not_execute_adapter_without_explicit_opt_in(tmp_path):
    target = tmp_path / "untrusted-adapter"
    init_project("untrusted-adapter", target)
    adapter = target / "adapter_command.py"
    marker = target / "adapter-executed.txt"
    adapter.write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        + adapter.read_text()
    )

    report = doctor_project(target)
    assert report.ready is True
    assert not marker.exists()
    adapter_check = next(item for item in report.checks if item.check_id == "adapter-contract")
    assert "not executed" in adapter_check.message

    report = doctor_project(target, run_adapter=True)
    assert report.ready is True
    assert marker.read_text() == "executed"


def test_doctor_rejects_manifest_traversal_and_symlinks(tmp_path):
    target = tmp_path / "hostile-starter"
    init_project("hostile-starter", target)
    manifest_path = target / "aau-starter.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["generated_file_sha256"]["../outside.txt"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    report = doctor_project(target)
    assert report.ready is False
    required = next(item for item in report.checks if item.check_id == "required-files")
    assert "unexpected" in required.message

    manifest["generated_file_sha256"].pop("../outside.txt")
    manifest_path.write_text(json.dumps(manifest))
    suite = target / "suite.json"
    outside = tmp_path / "outside-suite.json"
    outside.write_text(suite.read_text())
    suite.unlink()
    suite.symlink_to(outside)
    report = doctor_project(target)
    assert report.ready is False
    required = next(item for item in report.checks if item.check_id == "required-files")
    assert "missing or unsafe: suite.json" in required.message


def test_cli_init_and_doctor_work_without_a_repository_checkout(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert aau_main(["init", "my-agent", "--template", "incident-triage"]) == 0
    output = capsys.readouterr().out
    assert "Created" in output
    assert "Starter doctor" in output

    monkeypatch.chdir(tmp_path / "my-agent")
    assert aau_main(["doctor", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ready"] is True
    assert report["doctor_version"] == "aau-agent-evidence-doctor/1.0"


def test_cli_customizes_the_same_fields_as_the_browser_builder(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    result = aau_main(
        [
            "init",
            "custom-agent",
            "--template",
            "customer-escalation",
            "--mission",
            "Route synthetic requests under an explicit human authority boundary.",
            "--human-role",
            "Review lead",
            "--protected-action",
            "Approve a financial account change",
            "--routine-outcome",
            "route routine",
            "--human-outcome",
            "route human",
            "--stop-outcome",
            "stop unsafe",
        ]
    )
    assert result == 0
    capsys.readouterr()
    suite = json.loads((tmp_path / "custom-agent" / "suite.json").read_text())
    assert suite["description"].startswith("Route synthetic")
    assert suite["human_authority"]["accountable_role"] == "Review lead"
    assert {case["expected"]["outcome"] for case in suite["cases"]} == {
        "route_routine",
        "route_human",
        "stop_unsafe",
    }


def test_generated_ci_is_least_privilege_and_immutable(tmp_path):
    target = tmp_path / "ci-starter"
    init_project("ci-starter", target, adapter="http")
    workflow = (target / ".github/workflows/aau-evaluation.yml").read_text()
    assert "permissions:\n  contents: read" in workflow
    assert f"aau-harness=={PACKAGE_VERSION}" in workflow
    assert "persist-credentials: false" in workflow
    assert all(f"@{pin}" in workflow for pin in ACTION_PINS.values())
    assert "http://127.0.0.1:8000/evaluate" in workflow
    assert "socket.create_connection" in workflow


def test_manifest_records_origin_without_claiming_validation(tmp_path):
    target = tmp_path / "manifest-starter"
    init_project("manifest-starter", target)
    manifest = json.loads((target / "aau-starter.json").read_text())
    assert manifest["starter_version"] == STARTER_VERSION
    assert manifest["package_version"] == PACKAGE_VERSION
    assert manifest["status"] == "synthetic_onboarding_not_production_validation"
    assert len(manifest["generated_file_sha256"]) == 10
    assert "certification" in manifest["boundary"]


def test_browser_contract_exposes_three_templates_and_no_private_data():
    contract = browser_contract()
    assert contract["schema_version"] == "aau-agent-starter-browser/1.0"
    assert contract["bundle_file_count"] == 11
    assert {item["id"] for item in contract["templates"]} == set(TEMPLATES)
    assert "not uploaded" in contract["privacy"]
