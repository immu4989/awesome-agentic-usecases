from copy import deepcopy
import json
from pathlib import Path

import pytest

from aau_harness import eval_retry_demo
from aau_harness.agent_bom import AgentBomError
from aau_harness.catalog_cli import main
from aau_harness.eval_retry_review import verify_handoff


def test_complete_demo_is_deterministic_and_works_outside_checkout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["retry-demo", "--out", "first"]) == 0
    eval_retry_demo.create_demo(Path("second"))
    files = [p.relative_to("first") for p in Path("first").rglob("*") if p.is_file()]
    assert len(files) == 94
    assert all((Path("first") / p).read_bytes() == (Path("second") / p).read_bytes() for p in files)
    for name, policy, budget in (("earlier-harm", False, False), ("slow-completion", True, False), ("repaired", True, True)):
        report = verify_handoff(Path("first") / name, require_budget=True)
        assert (report["policy_status"] == "constraints_met") == policy
        assert (report["candidate_budget_status"] == "constraints_met") == budget
        assert (report["status"] == "constraints_met") == (policy and budget)
        assert report["sources"]["candidate"]["task_count"] == 2
        assert report["sources"]["candidate"]["attempt_count"] == 4
    guide = Path("first/README.txt").read_text()
    assert "earlier-harm=1, slow-completion=1, repaired=0" in guide
    assert "not measured service outcomes" in guide
    assert "same installed harness" in guide


def test_packaged_fixture_preserves_documented_example_values():
    root = Path(__file__).resolve().parents[1] / "examples/evaluation-review"
    policy, plan, ledger, diagnostics, _, _ = eval_retry_demo.demo_inputs()
    del plan["evaluation_context"]
    for value, filename in ((policy, "csv-review-policy.json"), (plan, "retry-plan.json"),
                            (ledger, "retry-ledger.json"), (diagnostics, "csv-review-diagnostics.json")):
        assert value == json.loads((root / filename).read_text())


@pytest.mark.parametrize("kind", ["directory", "file", "symlink"])
def test_no_existing_output_is_overwritten(tmp_path, kind):
    target = tmp_path / "existing"
    if kind == "directory":
        target.mkdir()
        (target / "user.txt").write_text("keep")
    elif kind == "file":
        target.write_text("keep")
    else:
        (tmp_path / "original").mkdir()
        target.symlink_to(tmp_path / "original", target_is_directory=True)
    assert main(["retry-demo", "--out", str(target)]) == 2
    if kind == "directory":
        assert (target / "user.txt").read_text() == "keep" and len(list(target.iterdir())) == 1
    elif kind == "file":
        assert target.read_text() == "keep"
    else:
        assert target.is_symlink() and not list(target.iterdir())


@pytest.mark.parametrize("field", ["status", "policy_status", "candidate_budget_status"])
def test_guide_is_not_written_when_any_expected_verdict_changes(tmp_path, monkeypatch, field):
    original = eval_retry_demo.verify_handoff
    def wrong(*args, **kwargs):
        report = deepcopy(original(*args, **kwargs))
        report[field] = "constraints_met"
        return report
    monkeypatch.setattr(eval_retry_demo, "verify_handoff", wrong)
    assert main(["retry-demo", "--out", str(tmp_path / "wrong")]) == 2
    assert not (tmp_path / "wrong/README.txt").exists()


def test_interrupted_verification_never_creates_completion_guide(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise AgentBomError("synthetic verification interruption")
    monkeypatch.setattr(eval_retry_demo, "verify_handoff", fail)
    assert main(["retry-demo", "--out", str(tmp_path / "partial")]) == 2
    assert (tmp_path / "partial/earlier-harm").is_dir()
    assert not (tmp_path / "partial/README.txt").exists()
