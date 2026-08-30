import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
import aau_freshness as freshness  # noqa: E402


ROOT = Path(__file__).parents[2]
REGISTRY = ROOT / "policy-freshness" / "sources.json"
LEDGER = ROOT / "policy-freshness" / "compatibility-ledger.json"
COMPATIBILITY_REPORT = ROOT / "policy-freshness" / "compatibility-report.json"


def registry():
    return json.loads(REGISTRY.read_text())


def ledger():
    return json.loads(LEDGER.read_text())


def test_committed_registry_is_complete_and_not_due():
    value = registry()
    freshness.validate_registry(value, ROOT)
    report = freshness.offline_report(value, ROOT, date(2026, 8, 30))
    assert report["source_count"] == 10
    assert report["baseline_missing_count"] == 0
    assert report["review_due_count"] == 0


def test_equal_fingerprint_is_current(monkeypatch):
    value = registry()
    monkeypatch.setattr(freshness, "_fetch", lambda source, timeout: source["baseline"])
    report = freshness.scan_registry(value, ROOT, 1, date(2026, 8, 30))
    assert report["summary"]["current_count"] == 10
    assert report["summary"]["human_review_required_count"] == 0


def test_changed_fingerprint_requires_human_review(monkeypatch):
    value = registry()

    def changed(source, timeout):
        observed = dict(source["baseline"])
        if source["source_id"] == "nist-agent-standards-initiative":
            observed["content_sha256"] = "0" * 64
        return observed

    monkeypatch.setattr(freshness, "_fetch", changed)
    report = freshness.scan_registry(value, ROOT, 1, date(2026, 8, 30))
    assert report["summary"]["source_changed_count"] == 1
    assert "does not prove that policy meaning changed" in freshness.issue_markdown(report)


def test_unreachable_source_is_not_treated_as_current(monkeypatch):
    value = registry()

    def unavailable(source, timeout):
        raise TimeoutError

    monkeypatch.setattr(freshness, "_fetch", unavailable)
    report = freshness.scan_registry(value, ROOT, 1, date(2026, 8, 30))
    assert report["summary"]["unreachable_count"] == 10
    assert all(row["interpretation"] == "human_review_required" for row in report["sources"])


def test_visible_text_fingerprint_ignores_scripts_but_not_policy_text():
    first = b"<html><script>nonce=1</script><main>Human approval required.</main></html>"
    same = b"<html><script>nonce=2</script><main>Human approval required.</main></html>"
    changed = b"<html><script>nonce=2</script><main>Human approval optional.</main></html>"
    assert freshness._fingerprint(first, "visible_text_v1") == freshness._fingerprint(same, "visible_text_v1")
    assert freshness._fingerprint(first, "visible_text_v1") != freshness._fingerprint(changed, "visible_text_v1")


def test_registry_rejects_unknown_fingerprint_mode():
    value = registry()
    value["sources"][0]["fingerprint_mode"] = "semantic_guess"
    with pytest.raises(freshness.FreshnessError):
        freshness.validate_registry(value, ROOT)


def test_compatibility_report_records_closed_protocol_migrations():
    value = freshness.compatibility_report(ledger(), registry(), ROOT, date(2026, 8, 30))
    assert value == json.loads(COMPATIBILITY_REPORT.read_text())
    assert value["summary"] == {
        "binding_count": 10,
        "source_lock_changed_count": 0,
        "migration_required_count": 0,
        "review_due_count": 0,
        "evidence_ready_count": 10,
        "human_review_required_count": 0,
    }
    mcp = next(row for row in value["bindings"] if row["source_id"] == "mcp-authorization")
    assert mcp["evaluated_revision"] == mcp["source_revision"] == "2026-07-28"
    assert "portable-agent-assurance/examples/mcp-2026-authorization-receipt.json" in mcp[
        "evidence_paths"
    ]
    a2a = next(row for row in value["bindings"] if row["source_id"] == "a2a-specification")
    assert a2a["evaluated_revision"] == a2a["source_revision"] == "1.0@v1.0.1"
    assert "portable-agent-assurance/examples/a2a-1-interface-authorization-receipt.json" in a2a[
        "evidence_paths"
    ]
    identity = next(
        row for row in value["bindings"]
        if row["source_id"] == "nist-agent-identity-concept-paper"
    )
    assert identity["evaluated_revision"] == "NCCoE-concept-paper-2026-02"
    assert identity["status"] == "evidence_ready"
    assert "reproduction-challenges/a2a-mcp-authority-relay/challenge.json" in identity[
        "evidence_paths"
    ]


def test_blind_challenge_sources_are_watched_by_exact_owner_path():
    watched = {source["source_id"]: source for source in registry()["sources"]}
    identity = watched["nist-agent-identity-concept-paper"]
    assert identity["baseline"] == {
        "content_sha256": "b303f7fba8c916f440a9435fa48d0e4465553f6b974d3157a1494747589e0b71",
        "bytes": 406665,
        "etag": None,
        "last_modified": "Thu, 05 Feb 2026 14:44:53 GMT",
        "final_url": identity["url"],
        "content_type": "application/pdf",
    }
    for source_id in (
        "nist-agent-identity-concept-paper", "mcp-authorization", "a2a-specification",
    ):
        owners = watched[source_id]["owner_paths"]
        assert "reproduction-challenges/portable-agent-assurance-2026-02" in owners
        assert "reproduction-challenges/a2a-mcp-authority-relay" in owners


def test_stale_protocol_revision_becomes_a_migration_gap():
    stale = ledger()
    stale["profiles"][0]["bindings"][0]["evaluated_revision"] = "2025-06-18"
    report = freshness.compatibility_report(stale, registry(), ROOT, date(2026, 8, 30))
    gap = next(row for row in report["bindings"] if row["status"] == "migration_required")
    assert gap["evaluated_revision"] == "2025-06-18"
    assert gap["source_revision"] == "2026-07-28"


def test_mutable_a2a_main_claim_becomes_a_migration_gap():
    stale = ledger()
    stale["profiles"][0]["bindings"][1]["evaluated_revision"] = "rolling-main@2026-08-30"
    report = freshness.compatibility_report(stale, registry(), ROOT, date(2026, 8, 30))
    gap = next(row for row in report["bindings"] if row["status"] == "migration_required")
    assert gap["source_id"] == "a2a-specification"
    assert gap["evaluated_revision"] == "rolling-main@2026-08-30"
    assert gap["source_revision"] == "1.0@v1.0.1"


def test_source_rebaseline_never_silently_preserves_compatibility():
    changed = registry()
    changed["sources"][0]["baseline"]["content_sha256"] = "0" * 64
    report = freshness.compatibility_report(ledger(), changed, ROOT, date(2026, 8, 30))
    affected = [row for row in report["bindings"] if row["status"] == "source_lock_changed"]
    assert [row["source_id"] for row in affected] == ["nist-agent-standards-initiative"]


def test_claim_inflation_and_missing_evidence_fail_closed():
    inflated = ledger()
    inflated["profiles"][0]["bindings"][0]["claim_boundary"] = "certified"
    with pytest.raises(freshness.FreshnessError, match="nonconformance claim"):
        freshness.validate_compatibility_ledger(inflated, registry(), ROOT)
    missing = ledger()
    missing["profiles"][0]["bindings"][0]["evidence_paths"] = ["missing.json"]
    with pytest.raises(freshness.FreshnessError, match="evidence path is invalid"):
        freshness.validate_compatibility_ledger(missing, registry(), ROOT)


def test_review_issue_includes_revision_impact_without_calling_it_conformance():
    scan = freshness.offline_report(registry(), ROOT, date(2026, 8, 30))
    scan_report = {
        "report_sha256": "0" * 64,
        "summary": {"human_review_required_count": 0},
        "sources": [],
    }
    stale = ledger()
    stale["profiles"][0]["bindings"][0]["evaluated_revision"] = "2025-06-18"
    compatibility = freshness.compatibility_report(stale, registry(), ROOT, date(2026, 8, 30))
    body = freshness.issue_markdown(scan_report, compatibility)
    assert scan["review_due_count"] == 0
    assert "Standards revision impact" in body
    assert "2025-06-18" in body and "2026-07-28" in body
    assert "not implementation verification" in body
