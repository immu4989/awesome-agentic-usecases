import json
import sys
from pathlib import Path

import pytest

from aau_harness.catalog_cli import main as aau_main
from aau_harness.evaluate import command_adapter, evaluate_suite, load_suite, mock_adapter
from aau_harness.starter import init_project
from aau_harness.submission import (
    SubmissionError,
    build_submission,
    resolve_metadata,
    validate_pack,
)


def metadata(**overrides):
    values = {
        "submission_id": "incident-routing-receipt",
        "contributor_name": "Example Contributor",
        "github": "example-contributor",
        "summary": "Routes synthetic service incidents while preserving human authority.",
        "why_fork": "Replace the rules and cases with a reviewed local operating boundary.",
        "beneficiaries": "Public-service operations teams and the people relying on them.",
        "industry": "Public services",
        "failure_shape": "Urgency pressure can cause an agent to cross a protected boundary.",
        "tags": ["public-service", "incident-routing", "human-authority"],
    }
    values.update(overrides)
    return resolve_metadata(**values)


def starter_and_receipt(tmp_path: Path, *, adapter_kind: str = "command"):
    starter = tmp_path / "starter"
    init_project("community-agent", starter, template_id="incident-triage")
    suite = load_suite(starter / "suite.json")
    if adapter_kind == "mock":
        invoke = mock_adapter
    else:
        invoke = command_adapter(f"{sys.executable} {starter / 'adapter_command.py'}", 2)
    receipt, _ = evaluate_suite(suite, invoke, adapter_kind)
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt))
    return starter, receipt_path


def write_distinct_receipt(starter: Path, target: Path, latency: float) -> Path:
    suite = load_suite(starter / "suite.json")
    invoke = command_adapter(f"{sys.executable} {starter / 'adapter_command.py'}", 2)
    receipt, _ = evaluate_suite(suite, invoke, "command")
    for row in receipt["results"]:
        row["latency_s"] = latency
    receipt["metrics"]["mean_latency_s"] = latency
    target.write_text(json.dumps(receipt))
    return target


def refresh_manifest(pack: Path) -> None:
    """Update integrity rows after a semantic-tamper fixture changes a file."""
    import hashlib

    manifest_path = pack / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for row in manifest["files"]:
        data = (pack / row["path"]).read_bytes()
        row["bytes"] = len(data)
        row["sha256"] = hashlib.sha256(data).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def test_builds_and_validates_generated_public_evidence_pack(tmp_path):
    starter, receipt = starter_and_receipt(tmp_path)
    output = tmp_path / "pack"
    report = build_submission(starter, [receipt], output, metadata())

    assert report["ready"] is True
    assert report["level"] == "Generated"
    assert report["receipt_count"] == 1
    assert report["file_count"] == 11
    assert validate_pack(output)["score"] == {"passed": 3, "total": 9}
    assert "identity_verified" in (output / "manifest.json").read_text()
    card = (output / "assets/evidence-card.svg").read_text()
    assert "Built With Evidence" not in card
    assert "Generated" in card
    assert "PROTECTED HUMAN AUTHORITY" in card


def test_rejects_mock_private_and_inconsistent_receipts(tmp_path):
    starter, mock_receipt = starter_and_receipt(tmp_path, adapter_kind="mock")
    with pytest.raises(SubmissionError, match="not a mock"):
        build_submission(starter, [mock_receipt], tmp_path / "mock-pack", metadata())

    _, receipt_path = starter_and_receipt(tmp_path / "second")
    receipt = json.loads(receipt_path.read_text())
    receipt["raw_response"] = "must never become public"
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(SubmissionError, match="unsupported public fields"):
        build_submission(
            tmp_path / "second" / "starter",
            [receipt_path],
            tmp_path / "private-pack",
            metadata(),
        )

    del receipt["raw_response"]
    receipt["metrics"]["exact_rate"] = 0.25
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(SubmissionError, match="inconsistent with results"):
        build_submission(
            tmp_path / "second" / "starter",
            [receipt_path],
            tmp_path / "false-pack",
            metadata(),
        )


@pytest.mark.parametrize(
    "field,value,pattern",
    [
        ("summary", "Contact person@example.gov for the full record.", "email_address"),
        ("why_fork", "Use api_key=do-not-publish in testing.", "credential"),
        ("beneficiaries", "Applicant 123-45-6789 needs assistance.", "social_security"),
    ],
)
def test_sensitive_metadata_is_blocked(field, value, pattern):
    with pytest.raises(SubmissionError, match=pattern):
        metadata(**{field: value})


def test_manifest_tamper_undeclared_files_symlinks_and_overwrite_are_blocked(tmp_path):
    starter, receipt = starter_and_receipt(tmp_path)
    output = tmp_path / "pack"
    build_submission(starter, [receipt], output, metadata())

    with pytest.raises(SubmissionError, match="refusing to overwrite"):
        build_submission(starter, [receipt], output, metadata())

    readme = output / "README.md"
    readme.write_text(readme.read_text() + "tampered\n")
    with pytest.raises(SubmissionError, match="manifest mismatch"):
        validate_pack(output)

    # Restore with a fresh pack, then check an undeclared file and a symlink.
    second = tmp_path / "second-pack"
    build_submission(starter, [receipt], second, metadata(submission_id="second-pack"))
    (second / "undeclared.txt").write_text("extra")
    with pytest.raises(SubmissionError, match="undeclared"):
        validate_pack(second)
    (second / "undeclared.txt").unlink()
    (second / "linked.txt").symlink_to(tmp_path / "outside.txt")
    with pytest.raises(SubmissionError, match="symlinks"):
        validate_pack(second)


def test_semantic_tampering_is_rejected_even_after_manifest_is_recomputed(tmp_path):
    starter, receipt = starter_and_receipt(tmp_path)
    output = tmp_path / "pack"
    build_submission(starter, [receipt], output, metadata())
    submission_path = output / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["private_note"] = "unsupported"
    submission_path.write_text(json.dumps(submission, indent=2, sort_keys=True) + "\n")
    refresh_manifest(output)
    with pytest.raises(SubmissionError, match="unsupported fields"):
        validate_pack(output)


def test_auxiliary_files_cannot_smuggle_sensitive_data_or_active_svg(tmp_path):
    starter, receipt = starter_and_receipt(tmp_path)
    sensitive_pack = tmp_path / "sensitive-pack"
    build_submission(starter, [receipt], sensitive_pack, metadata(submission_id="sensitive-pack"))
    readme = sensitive_pack / "README.md"
    readme.write_text(readme.read_text() + "\nContact hidden.person@example.gov.\n")
    refresh_manifest(sensitive_pack)
    with pytest.raises(SubmissionError, match="sensitive-data scan"):
        validate_pack(sensitive_pack)

    active_pack = tmp_path / "active-pack"
    build_submission(starter, [receipt], active_pack, metadata(submission_id="active-pack"))
    card = active_pack / "assets/evidence-card.svg"
    card.write_text(card.read_text().replace("<svg ", '<svg onload="alert(1)" '))
    refresh_manifest(active_pack)
    with pytest.raises(SubmissionError, match="passive SVG"):
        validate_pack(active_pack)


def test_evidence_levels_are_derived_cumulatively(tmp_path):
    starter, _ = starter_and_receipt(tmp_path)
    suite_path = starter / "suite.json"
    suite = json.loads(suite_path.read_text())
    originals = list(suite["cases"])
    while len(suite["cases"]) < 10:
        source = originals[len(suite["cases"]) % len(originals)]
        copied = json.loads(json.dumps(source))
        copied["scenario_id"] = f"incident-{len(suite['cases']) + 1:03d}"
        suite["cases"].append(copied)
    suite_path.write_text(json.dumps(suite, indent=2, sort_keys=True) + "\n")

    receipts = [
        write_distinct_receipt(starter, tmp_path / f"run-{index}.json", index / 1000)
        for index in range(1, 4)
    ]
    review = {
        "reviewer": "Jordan Reviewer",
        "reviewer_role": "Service operations lead",
        "scope": "Reviewed the synthetic routing boundary and expected outcomes.",
        "reviewed_at": "2026-08-23",
        "sources": ["https://www.nist.gov/", "https://www.gao.gov/"],
    }
    reproduction = {
        "reproducer_name": "Taylor Reproducer",
        "reproducer_github": "different-reviewer",
        "scope": "Repeated the public suite against the declared adapter contract.",
        "receipt_file": "run-03",
    }
    output = tmp_path / "verified-pack"
    report = build_submission(
        starter,
        receipts,
        output,
        metadata(review=review, reproduction=reproduction),
    )

    assert report["level"] == "Verified"
    assert report["score"] == {"passed": 9, "total": 9}
    submission = json.loads((output / "submission.json").read_text())
    assert submission["reproduction"]["receipt_file"] == "receipts/run-03.json"


def test_catalog_cli_submit_works_outside_repository(tmp_path, monkeypatch, capsys):
    starter, receipt = starter_and_receipt(tmp_path)
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "cli-pack"
    args = [
        "submit",
        str(starter),
        "--receipt",
        str(receipt),
        "--out",
        str(output),
        "--id",
        "cli-pack",
        "--contributor-name",
        "CLI Contributor",
        "--github",
        "cli-contributor",
        "--summary",
        "Routes a reviewed synthetic incident signal.",
        "--why-fork",
        "Adapt the rules to a local public boundary.",
        "--beneficiaries",
        "Service teams and residents.",
        "--industry",
        "Public services",
        "--failure-shape",
        "Urgency pressure can bypass human authority.",
        "--tag",
        "public-service",
        "--tag",
        "routing",
    ]
    assert aau_main(args) == 0
    assert "READY  cli-pack · Generated" in capsys.readouterr().out
    assert aau_main(["submit", "--validate", str(output), "--json"]) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["ready"] is True
