from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import urllib.request

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
import aau_freshness as freshness  # noqa: E402
import source_evidence as evidence  # noqa: E402


ROOT = Path(__file__).parents[2]
OLD = b"<html><script>nonce=1</script><main>Human approval required before payment.</main></html>"
NEW = b"<html><script>nonce=2</script><main>Human approval optional before payment.</main></html>"


def inputs(content=OLD, mode="visible_text_v1"):
    registry = json.loads((ROOT / "policy-freshness/sources.json").read_text())
    registry["sources"] = registry["sources"][:1]
    source = registry["sources"][0]
    source["fingerprint_mode"] = mode
    observed = {**source["baseline"], "content_sha256": freshness._fingerprint(content, mode), "bytes": len(content)}
    capture = {"capture_version": "aau-policy-source-capture/1.0", "source_id": source["source_id"],
               "captured_at": "2026-10-13T00:00:00Z", "observed": observed}
    return registry, capture, content


def pair(tmp_path, before=OLD, after=NEW, mode="visible_text_v1"):
    first, second = tmp_path / "before", tmp_path / "after"
    evidence.create_snapshot(*inputs(before, mode), first)
    evidence.create_snapshot(*inputs(after, mode), second)
    return first, second


def test_retained_content_and_source_declarations_recompute_without_rebaselining(tmp_path):
    args = inputs()
    original = deepcopy(args)
    pack = tmp_path / "snapshot"
    report = evidence.create_snapshot(*args, pack)
    assert args == original
    assert report == evidence.verify_snapshot(pack)[3]
    assert not report["matches_registered_baseline"]
    assert report["raw_sha256"] == freshness.digest(OLD)
    assert {p.name for p in pack.iterdir()} == evidence.FILES
    assert (pack / "content.bin").read_bytes() == OLD
    assert evidence.payloads(*args) == evidence.payloads(*args)


def test_visible_change_has_reproducible_word_ranges_and_no_policy_interpretation(tmp_path):
    first, second = pair(tmp_path)
    result = evidence.compare_snapshots(first, second)
    assert result["raw_bytes_changed"] and result["fingerprint_changed"]
    assert result["detail"] == {"status": "bounded_lexical_diff", "spans": [
        {"operation": "replace", "baseline_range": [2, 3], "candidate_range": [2, 3],
         "baseline_text": "required", "candidate_text": "optional"}]}
    assert "Missing historical snapshots" in result["boundary"]
    assert "nonce" not in json.dumps(result)
    assert evidence.main(["compare", str(first), str(second), "--out", str(tmp_path / "diff.json")]) == 0
    assert evidence.main(["compare", str(first), str(second), "--verify", str(tmp_path / "diff.json")]) == 0
    (tmp_path / "diff.json").write_text("{}")
    assert evidence.main(["compare", str(first), str(second), "--verify", str(tmp_path / "diff.json")]) == 2


def test_script_only_changes_do_not_claim_visible_rule_changes(tmp_path):
    result = evidence.compare_snapshots(*pair(tmp_path, after=OLD.replace(b"nonce=1", b"nonce=2")))
    assert result["raw_bytes_changed"]
    assert not result["fingerprint_changed"]
    assert result["detail"] == {"status": "fingerprint_unchanged", "spans": []}


@pytest.mark.parametrize("mode,old,new,status", [
    ("raw", b"%PDF-original", b"%PDF-changed", "raw_content_requires_external_review"),
    ("visible_text_v1", b"<p>" + b"old " * 5001 + b"</p>", NEW, "text_diff_omitted_size_limit"),
    ("visible_text_v1", b"<p>" + b"x" * 200001 + b"</p>", NEW, "text_diff_omitted_size_limit")])
def test_binary_and_large_inputs_are_explicitly_not_text_diffs(tmp_path, mode, old, new, status):
    result = evidence.compare_snapshots(*pair(tmp_path, old, new, mode))
    assert result["fingerprint_changed"]
    assert result["detail"] == {"status": status, "spans": []}


@pytest.mark.parametrize("member", sorted(evidence.FILES))
def test_every_member_is_checked_even_with_rehashed_manifest(tmp_path, member):
    pack = tmp_path / "pack"
    evidence.create_snapshot(*inputs(), pack)
    path = pack / member
    path.write_bytes(path.read_bytes() + b" ")
    if member != "manifest.json":
        manifest = json.loads((pack / "manifest.json").read_text())
        manifest["files"][member] = freshness.digest(path.read_bytes())
        (pack / "manifest.json").write_bytes(freshness.rendered(manifest))
    with pytest.raises(freshness.FreshnessError):
        evidence.verify_snapshot(pack)


@pytest.mark.parametrize("field,value", [("source_id", "unknown"), ("captured_at", "2026-10-13"),
                                         ("capture_version", "unknown")])
def test_invalid_capture_metadata_fails_before_output(tmp_path, field, value):
    registry, capture, content = inputs()
    capture[field] = value
    with pytest.raises(freshness.FreshnessError):
        evidence.create_snapshot(registry, capture, content, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("field,value", [("bytes", True), ("bytes", 1), ("content_sha256", "0" * 64),
                                         ("final_url", "https://example.org/")])
def test_observed_metadata_must_bind_bytes_and_allowed_host(tmp_path, field, value):
    registry, capture, content = inputs()
    capture["observed"][field] = value
    with pytest.raises(freshness.FreshnessError):
        evidence.create_snapshot(registry, capture, content, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("field,value", [("source_id", "changed-id"), ("url", "https://www.nist.gov/other"),
                                         ("fingerprint_mode", "raw")])
def test_comparison_refuses_different_source_identity_or_fingerprint_method(tmp_path, field, value):
    first, second = tmp_path / "first", tmp_path / "second"
    evidence.create_snapshot(*inputs(), first)
    registry, capture, content = inputs(mode="raw" if field == "fingerprint_mode" else "visible_text_v1")
    registry["sources"][0][field] = value
    capture["source_id"] = registry["sources"][0]["source_id"]
    evidence.create_snapshot(registry, capture, content, second)
    with pytest.raises(freshness.FreshnessError, match="same source"):
        evidence.compare_snapshots(first, second)


@pytest.mark.parametrize("defect", ["extra", "missing", "symlink", "oversized", "directory"])
def test_incomplete_and_unsafe_packs_fail(tmp_path, defect):
    pack = tmp_path / "pack"
    evidence.create_snapshot(*inputs(), pack)
    if defect == "extra":
        (pack / "extra").write_text("x")
    elif defect == "missing":
        (pack / "content.bin").unlink()
    elif defect == "oversized":
        (pack / "content.bin").write_bytes(b"x" * (freshness.MAX_SOURCE_BYTES + 1))
    elif defect == "directory":
        (pack / "summary.json").unlink()
        (pack / "summary.json").mkdir()
    else:
        (pack / "content.bin").rename(tmp_path / "content")
        (pack / "content.bin").symlink_to(tmp_path / "content")
    assert evidence.main(["verify", str(pack)]) == 2


def test_capture_uses_one_fetch_and_never_modifies_registry_or_overwrites(tmp_path, monkeypatch):
    registry, capture, content = inputs()
    path = tmp_path / "registry.json"
    path.write_bytes(freshness.rendered(registry))
    original = path.read_bytes()
    calls = []
    def fetch(source, timeout):
        calls.append(source["source_id"])
        return content, capture["observed"]
    monkeypatch.setattr(freshness, "fetch_content", fetch)
    args = ["capture", str(path), capture["source_id"], "--out", str(tmp_path / "pack")]
    assert evidence.main(args) == 0
    assert evidence.main(args) == 2
    assert len(calls) == 1
    assert path.read_bytes() == original


def test_network_failure_is_not_an_empty_snapshot_or_raw_error_log(tmp_path, monkeypatch, capsys):
    registry, capture, _ = inputs()
    path = tmp_path / "registry.json"
    path.write_bytes(freshness.rendered(registry))
    def fail(*args):
        raise TimeoutError("PRIVATE_ERROR_DETAILS")
    monkeypatch.setattr(freshness, "fetch_content", fail)
    assert evidence.main(["capture", str(path), capture["source_id"], "--out", str(tmp_path / "pack")]) == 2
    assert not (tmp_path / "pack").exists()
    assert "PRIVATE_ERROR_DETAILS" not in capsys.readouterr().err


@pytest.mark.parametrize("url", ["https://evil.example/a", "http://www.nist.gov/a", "https://user:secret@www.nist.gov/a"])
def test_redirect_boundary_is_enforced_before_another_request(url):
    handler = freshness._AllowedRedirects(["www.nist.gov"])
    request = urllib.request.Request("https://www.nist.gov/original")
    with pytest.raises(freshness.FreshnessError):
        handler.redirect_request(request, None, 302, "Found", {}, url)


def test_fetch_and_metadata_only_scan_share_exact_content_processing(monkeypatch):
    registry, capture, content = inputs()
    source = registry["sources"][0]
    class Response:
        headers = {"Content-Type": "text/html"}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def geturl(self):
            return source["url"]
        def read(self, maximum):
            assert maximum == freshness.MAX_SOURCE_BYTES + 1
            return content
    monkeypatch.setattr(urllib.request, "build_opener", lambda handler: SimpleNamespace(open=lambda *a, **k: Response()))
    raw, observed = freshness.fetch_content(source, 1)
    assert raw == content
    assert observed == freshness._fetch(source, 1)
    assert observed["content_sha256"] == capture["observed"]["content_sha256"]


def test_allowed_https_redirect_is_still_supported():
    request = urllib.request.Request("https://www.nist.gov/original")
    redirected = freshness._AllowedRedirects(["www.nist.gov"]).redirect_request(
        request, None, 302, "Found", {}, "https://www.nist.gov/current")
    assert redirected.full_url == "https://www.nist.gov/current"


def test_registry_metadata_change_is_disclosed_even_when_content_matches(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    evidence.create_snapshot(*inputs(), first)
    registry, capture, content = inputs()
    registry["sources"][0]["source_revision"] = "rolling@2026-10-13"
    registry["sources"][0]["owner_paths"].append("another-owner")
    evidence.create_snapshot(registry, capture, content, second)
    result = evidence.compare_snapshots(first, second)
    assert result["registered_source_metadata_changed"]
    assert not result["fingerprint_changed"]
    assert "another-owner" in result["affected_owner_paths"]


def test_coordinated_replacement_is_consistent_not_authenticated(tmp_path):
    registry, capture, content = inputs(NEW)
    registry["sources"][0]["baseline"] = deepcopy(capture["observed"])
    evidence.create_snapshot(registry, capture, content, tmp_path / "replaced")
    report = evidence.verify_snapshot(tmp_path / "replaced")[3]
    assert report["matches_registered_baseline"]
    assert "not authenticated retrieval" in report["boundary"]
