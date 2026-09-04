import importlib.util
import json
from pathlib import Path

import pytest


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


def test_scope_ordinal_locators_ignore_unrelated_line_shifts(tmp_path):
    trust = module()
    workflow = tmp_path / ".github" / "workflows" / "test.yml"
    workflow.parent.mkdir(parents=True)
    before = """name: test
on: push
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
      - name: setup
        uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1
"""
    workflow.write_text(before)
    first = trust.scan_dependencies(tmp_path)
    workflow.write_text(
        before.replace(
            "    steps:\n",
            "    # A comment and run step do not change external dependency identity.\n"
            "    steps:\n"
            "      - run: echo local\n",
        )
    )
    assert trust.scan_dependencies(tmp_path) == first
    uses = [use for item in first for use in item["uses"]]
    assert {use["scope"] for use in uses} == {"job:verify"}
    assert {use["ordinal"] for use in uses} == {1, 2}


def test_external_action_insertion_and_job_rename_change_identity(tmp_path):
    trust = module()
    workflow = tmp_path / ".github" / "workflows" / "test.yml"
    workflow.parent.mkdir(parents=True)
    original = """jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
"""
    workflow.write_text(original)
    first = trust.scan_dependencies(tmp_path)
    workflow.write_text(original.replace("verify:", "assure:"))
    assert trust.scan_dependencies(tmp_path) != first
    workflow.write_text(
        original.replace(
            "      - uses:",
            "      - uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1\n"
            "      - uses:",
        )
    )
    assert trust.scan_dependencies(tmp_path) != first


def test_local_action_forms_do_not_consume_external_ordinals(tmp_path):
    trust = module()
    workflow = tmp_path / ".github" / "workflows" / "test.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        """jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: ./.github/actions/local
      - uses: $/.github/actions/at-running-commit
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
"""
    )
    dependencies = trust.scan_dependencies(tmp_path)
    assert len(dependencies) == 1
    assert dependencies[0]["uses"][0]["ordinal"] == 1


def test_job_level_reusable_workflow_gets_stable_job_scope(tmp_path):
    trust = module()
    workflow = tmp_path / ".github" / "workflows" / "test.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        """jobs:
  delegate:
    uses: trusted/workflows/.github/workflows/verify.yml@0123456789abcdef0123456789abcdef01234567
"""
    )
    dependency = trust.scan_dependencies(tmp_path)[0]
    assert dependency["uses"] == [
        {
            "path": ".github/workflows/test.yml",
            "scope": "job:delegate",
            "ordinal": 1,
            "coordinate": "trusted/workflows/.github/workflows/verify.yml",
        }
    ]


@pytest.mark.parametrize(
    "fragment",
    [
        "      - *external_step\n",
        "      - <<: *external_step\n",
        "  verify: *external_job\n",
    ],
)
def test_yaml_aliases_cannot_hide_action_uses(tmp_path, fragment):
    trust = module()
    workflow = tmp_path / ".github" / "workflows" / "test.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("jobs:\n  verify:\n    runs-on: ubuntu-latest\n    steps:\n" + fragment)
    with pytest.raises(trust.ActionTrustError, match="YAML aliases"):
        trust.scan_dependencies(tmp_path)


def test_trailing_uses_tokens_and_inline_jobs_fail_closed(tmp_path):
    trust = module()
    workflow = tmp_path / ".github" / "workflows" / "test.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        """jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 trailing
"""
    )
    with pytest.raises(trust.ActionTrustError, match="full lowercase commit SHA"):
        trust.scan_dependencies(tmp_path)
    workflow.write_text("jobs:\n  verify: {uses: attacker/action@main}\n")
    with pytest.raises(trust.ActionTrustError, match="expanded mapping"):
        trust.scan_dependencies(tmp_path)


def test_scalar_text_cannot_create_phantom_action_uses(tmp_path):
    trust = module()
    workflow = tmp_path / ".github" / "workflows" / "test.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        """jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - run: |
          cat <<'TEXT'
          uses: attacker/phantom@main
          <<: *also_not_structure
          TEXT
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
"""
    )
    dependencies = trust.scan_dependencies(tmp_path)
    assert len(dependencies) == 1
    assert dependencies[0]["repository"] == "actions/checkout"


@pytest.mark.parametrize(
    "fragment",
    [
        "    steps: [{uses: attacker/action@main}]\n",
        "    steps:\n      - {name: hidden, uses: attacker/action@main}\n",
        '    steps:\n      - "uses": attacker/action@main\n',
    ],
)
def test_noncanonical_use_mappings_fail_closed(tmp_path, fragment):
    trust = module()
    workflow = tmp_path / ".github" / "workflows" / "test.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("jobs:\n  verify:\n    runs-on: ubuntu-latest\n" + fragment)
    with pytest.raises(trust.ActionTrustError, match="canonical expanded mapping"):
        trust.scan_dependencies(tmp_path)


def test_noncanonical_composite_use_mapping_fails_closed(tmp_path):
    trust = module()
    action = tmp_path / ".github" / "actions" / "local" / "action.yml"
    action.parent.mkdir(parents=True)
    action.write_text(
        """name: local
runs:
  using: composite
  steps:
    - {uses: attacker/action@main}
"""
    )
    with pytest.raises(trust.ActionTrustError, match="canonical expanded mapping"):
        trust.scan_dependencies(tmp_path)
