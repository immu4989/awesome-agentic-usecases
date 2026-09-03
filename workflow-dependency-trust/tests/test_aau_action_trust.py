import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "workflow-dependency-trust" / "aau_action_trust.py"
LOCK = ROOT / "workflow-dependency-trust" / "action-trust-lock.json"


def module():
    spec = importlib.util.spec_from_file_location("aau_action_trust", SCRIPT)
    assert spec and spec.loader
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_committed_lock_covers_every_external_action_use():
    trust = module()
    lock = trust.load_json(LOCK)
    dependencies = trust.validate_lock(lock)
    assert lock["summary"]["workflow_use_count"] >= 46
    assert len(dependencies) >= 12
    assert all(item["repository_membership"] == "verified_by_github_commit_api" for item in dependencies)


def test_lock_digest_and_workflow_coverage_fail_closed():
    trust = module()
    lock = trust.load_json(LOCK)
    changed = json.loads(json.dumps(lock))
    changed["dependencies"][0]["commit_sha"] = "0" * 40
    try:
        trust.validate_lock(changed)
    except trust.ActionTrustError:
        pass
    else:
        raise AssertionError("a changed Action commit passed the trust lock")


def test_live_check_requires_exact_repository_membership():
    trust = module()
    dependency = trust.load_json(LOCK)["dependencies"][0]

    def wrong_repository(repository, commit, token):
        return {
            "repository_membership": "verified_by_github_commit_api",
            "commit_verification": {"verified": True, "reason": "valid"},
            "commit_url": f"https://github.com/attacker/fork/commit/{commit}",
        }

    try:
        trust.verify_online([dependency], "", fetcher=wrong_repository)
    except trust.ActionTrustError as exc:
        assert "membership drifted" in str(exc)
    else:
        raise AssertionError("a commit from the wrong repository passed live verification")


def test_snapshot_is_deterministic_with_observed_commit_metadata(monkeypatch):
    trust = module()

    def observed(repository, commit, token):
        return {
            "repository_membership": "verified_by_github_commit_api",
            "commit_verification": {"verified": False, "reason": "unsigned"},
            "commit_url": f"https://github.com/{repository}/commit/{commit}",
        }

    monkeypatch.setattr(trust, "github_commit", observed)
    first = trust.build_lock("2026-09-03T00:00:00Z", "")
    second = trust.build_lock("2026-09-03T00:00:00Z", "")
    assert first == second
    assert first["lock_sha256"] == trust.digest(
        {key: value for key, value in first.items() if key != "lock_sha256"}
    )
