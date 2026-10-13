from copy import deepcopy
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError
from aau_harness.catalog_cli import main
from aau_harness import eval_demo
from aau_harness.eval_pack import verify_pack


def test_demo_is_complete_deterministic_and_preserves_both_outcomes(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    eval_demo.create_demo(first)
    assert main(["evaluation-demo", "--out", str(second)]) == 0
    assert sorted(path.name for path in first.iterdir()) == ["README.txt", "intermittent", "repaired"]
    files = [path.relative_to(first) for path in first.rglob("*") if path.is_file()]
    assert len(files) == 27
    assert all((first / path).read_bytes() == (second / path).read_bytes() for path in files)
    for name, expected, unit_cost in (("intermittent", "constraints_not_met", .4), ("repaired", "constraints_met", .25)):
        report = verify_pack(first / name, require_recordings=True, require_diagnostics=True)
        assert report["status"] == expected
        assert report["comparisons"][0]["context_match"]["status"] == "matched"
        operating = json.loads((first / name / "candidate-operations.json").read_text())
        assert operating["declared_cost_basis"] == "synthetic"
        assert operating["overall"]["cost"]["total_per_passing_attempt_usd"] == unit_cost
        source = json.loads((first / name / "candidate-recording.json").read_text())
        assert source["format_version"] == "aau-recorded-observations/1.1"
        assert "Synthetic" in source["source_label"]
        assert len(source["observations"]) == 4
    guide = (first / "README.txt").read_text()
    assert "intermittent=1, repaired=0" in guide
    assert "not measured service outcomes" in guide
    assert "same installed harness" in guide


@pytest.mark.parametrize("kind", ["directory", "file", "symlink"])
def test_demo_does_not_overwrite_existing_destinations(tmp_path, kind):
    destination = tmp_path / "existing"
    if kind == "directory":
        destination.mkdir()
        (destination / "user.txt").write_text("keep")
    elif kind == "file":
        destination.write_text("keep")
    else:
        target = tmp_path / "target"
        target.mkdir()
        destination.symlink_to(target, target_is_directory=True)
    assert main(["evaluation-demo", "--out", str(destination)]) == 2
    if kind == "directory":
        assert list(destination.iterdir()) == [destination / "user.txt"]
        assert (destination / "user.txt").read_text() == "keep"
    elif kind == "file":
        assert destination.read_text() == "keep"
    else:
        assert destination.is_symlink()
        assert not list(destination.iterdir())


def test_demo_guide_is_not_written_if_verification_fails(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise AgentBomError("synthetic interrupted verification")
    monkeypatch.setattr(eval_demo, "verify_pack", fail)
    destination = tmp_path / "partial"
    assert main(["evaluation-demo", "--out", str(destination)]) == 2
    assert not (destination / "README.txt").exists()
    assert (destination / "intermittent").is_dir()


def test_demo_checks_expected_negative_twin_not_just_file_verification(tmp_path, monkeypatch):
    original = eval_demo.verify_pack
    def wrong_outcome(*args, **kwargs):
        report = deepcopy(original(*args, **kwargs))
        report["status"] = "constraints_met"
        return report
    monkeypatch.setattr(eval_demo, "verify_pack", wrong_outcome)
    assert main(["evaluation-demo", "--out", str(tmp_path / "unexpected")]) == 2
    assert not (tmp_path / "unexpected/README.txt").exists()


def test_release_validates_installed_wheel_before_attestation_and_publication():
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/harness-release.yml").read_text()
    assert workflow.index("python -m build harness") < workflow.index("smoke_installed_wheel.py")
    assert workflow.index("smoke_installed_wheel.py") < workflow.index("Upload package distributions")
    assert workflow.index("smoke_installed_wheel.py") < workflow.index("Attest package provenance")
    assert "needs: build" in workflow.split("publish-pypi:", 1)[1]


def test_installed_smoke_checks_artifact_without_source_path_or_index_fallback():
    script = (Path(__file__).resolve().parents[1] / "tools/smoke_installed_wheel.py").read_text()
    assert '"--no-index", "--no-deps"' in script
    assert '"PYTHONPATH", "PYTHONHOME"' in script
    assert 'cwd=root' in script
    assert 'environment.resolve() not in location.parents' in script
    assert '"--require-recordings", "--require-diagnostics"' in script
    assert 'expected=2' in script
