from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
import aau_freshness as freshness  # noqa: E402
import open_review_issue as updater  # noqa: E402

ROOT = Path(__file__).parents[2]


def report(monkeypatch, failed=()):
    registry = json.loads((ROOT / "policy-freshness/sources.json").read_text())
    def fetch(source, timeout):
        if source["source_id"] in failed:
            raise TimeoutError()
        return source["baseline"]
    monkeypatch.setattr(freshness, "_fetch", fetch)
    return freshness.scan_registry(registry, ROOT, 1, date(2026, 8, 30))


def block(value):
    return updater.snapshot(value, None, freshness.issue_markdown(value))


def test_new_findings_update_existing_notice_and_preserve_human_notes(monkeypatch):
    first = report(monkeypatch, ["cisa-jcdc-ai-playbook"])
    marker, managed, active = block(first)
    initial = updater.reconcile_body(None, marker, managed, active)
    existing = "Owner: investigation in progress.\n\n" + initial + "\nDo not discard this decision record."
    newer = report(monkeypatch, ["cisa-jcdc-ai-playbook", "nist-agent-standards-initiative"])
    result = updater.reconcile_body(existing, *block(newer))
    assert result.startswith("Owner: investigation in progress.")
    assert result.endswith("Do not discard this decision record.")
    assert "**2** source(s)" in result
    assert result.count(updater.BEGIN) == 1


def test_unchanged_findings_ignore_new_scan_dates_and_report_hashes(monkeypatch):
    value = report(monkeypatch, ["cisa-jcdc-ai-playbook"])
    initial = updater.reconcile_body(None, *block(value))
    later = deepcopy(value)
    later["as_of"] = "2026-08-31"
    later["report_sha256"] = freshness.digest({key: item for key, item in later.items() if key != "report_sha256"})
    assert updater.reconcile_body(initial, *block(later)) is None


def test_all_clear_updates_an_existing_issue_but_does_not_resolve_human_work(monkeypatch):
    initial = updater.reconcile_body(None, *block(report(monkeypatch, ["cisa-jcdc-ai-playbook"])))
    cleared = block(report(monkeypatch))
    assert updater.reconcile_body(None, *cleared) is None
    result = updater.reconcile_body(initial, *cleared)
    assert "no machine-flagged findings" in result
    assert "does not resolve earlier human review" in result


def test_legacy_notice_is_retained_in_full(monkeypatch):
    legacy = "Original source alert\n\nHuman owner: awaiting review."
    result = updater.reconcile_body(legacy, *block(report(monkeypatch)))
    assert result.endswith(legacy)
    assert "Earlier notice and owner notes (retained)" in result


@pytest.mark.parametrize("existing", [updater.BEGIN, updater.END, updater.END + updater.BEGIN,
                                       updater.BEGIN + updater.BEGIN + updater.END])
def test_ambiguous_markers_refuse_overwrite(monkeypatch, existing):
    with pytest.raises(ValueError):
        updater.reconcile_body(existing, *block(report(monkeypatch)))


def test_large_human_notes_are_never_truncated(monkeypatch):
    with pytest.raises(ValueError):
        updater.reconcile_body("x" * updater.MAX_BODY_BYTES, *block(report(monkeypatch)))


def test_reports_and_supplied_body_must_agree(monkeypatch):
    value = report(monkeypatch)
    with pytest.raises(ValueError):
        updater.snapshot(value, None, "invented notice")
    value["summary"]["human_review_required_count"] = 1
    with pytest.raises(ValueError):
        block(value)
    value["report_sha256"] = freshness.digest({key: item for key, item in value.items() if key != "report_sha256"})
    with pytest.raises(ValueError):
        block(value)


def test_compatibility_findings_participate_in_reconciliation(monkeypatch):
    value = report(monkeypatch)
    compatibility = json.loads((ROOT / "policy-freshness/compatibility-report.json").read_text())
    assert not updater.snapshot(value, compatibility, freshness.issue_markdown(value, compatibility))[2]
    compatibility["bindings"][0]["status"] = "migration_required"
    compatibility["summary"].update(migration_required_count=1, evidence_ready_count=9, human_review_required_count=1)
    compatibility["report_sha256"] = freshness.digest({key: item for key, item in compatibility.items() if key != "report_sha256"})
    assert updater.snapshot(value, compatibility, freshness.issue_markdown(value, compatibility))[2]
    compatibility["as_of"] = "2026-08-31"
    compatibility["report_sha256"] = freshness.digest({key: item for key, item in compatibility.items() if key != "report_sha256"})
    with pytest.raises(ValueError):
        updater.snapshot(value, compatibility, freshness.issue_markdown(value, compatibility))


@pytest.mark.parametrize("state", ["create", "update", "unchanged", "clear", "race", "closed", "renamed", "duplicates", "failure"])
def test_cli_reconciliation_uses_exact_issue_and_never_closes(monkeypatch, tmp_path, state):
    prior = report(monkeypatch, ["cisa-jcdc-ai-playbook"])
    value = report(monkeypatch, ["cisa-jcdc-ai-playbook", "nist-agent-standards-initiative"])
    if state == "unchanged":
        value = prior
    if state == "clear":
        value = report(monkeypatch)
    old_body = "Owner note\n" + updater.reconcile_body(None, *block(prior))
    issue = {"number": 12, "title": updater.TITLE, "body": old_body}
    mutations = []
    def run(command, **kwargs):
        assert "close" not in command and "comment" not in command
        if "list" in command:
            rows = [] if state == "create" else [issue]
            if state == "duplicates":
                rows.append({**issue, "number": 13})
            return SimpleNamespace(stdout=json.dumps(rows))
        if "view" in command:
            return SimpleNamespace(stdout=json.dumps({"body": old_body + ("new human note" if state == "race" else ""),
                                                      "state": "CLOSED" if state == "closed" else "OPEN",
                                                      "title": "Retitled by owner" if state == "renamed" else updater.TITLE}))
        if state == "failure":
            raise subprocess.CalledProcessError(1, command)
        mutations.append((command, kwargs["input"]))
        return SimpleNamespace(stdout="")
    monkeypatch.setattr(updater.subprocess, "run", run)
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repository")
    source, body = tmp_path / "report.json", tmp_path / "body.md"
    source.write_text(json.dumps(value))
    body.write_text(freshness.issue_markdown(value))
    expected = 2 if state in ("race", "closed", "renamed", "duplicates", "failure") else 0
    assert updater.main([str(source), str(body)]) == expected
    if state in ("race", "closed", "renamed", "duplicates", "failure", "unchanged"):
        assert not mutations
    else:
        assert len(mutations) == 1
        command, written = mutations[0]
        assert command[-2:] == ["--body-file", "-"]
        if state != "create":
            assert command[2:4] == ["edit", "12"]
            assert written.startswith("Owner note")
