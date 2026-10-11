import importlib.util
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, load_json
from aau_harness.catalog_cli import main
from aau_harness.eval_pack import create_pack, pack_payloads, verify_pack
from aau_harness.runner import ScenarioResult, run_eval


def sources(unsafe=False, label="ordinary"):
    policy = {"policy_version": "aau-evaluation-review-policy/1.0", "scenario_ids": [label],
              "minimum_repeats": 2, "metrics": [{"metric": "authorization", "direction": "higher",
              "candidate_observation_limit": 1, "max_mean_regression": 0, "max_regressed_scenarios": 0}]}
    def result(bad):
        return run_eval([label], lambda scenario, repeat: ScenarioResult(
            scenario, repeat, {"authorization": float(not (bad and repeat == 0))},
            0, 0.1, 0, {"synthetic_note": "Source details remain in the pack."}), repeats=2).as_dict()
    return policy, result(False), result(unsafe)


@pytest.mark.parametrize("unsafe", [False, True])
def test_complete_pack_recomputes_byte_for_byte_and_preserves_source_details(tmp_path, unsafe):
    inputs = sources(unsafe)
    destination = tmp_path / "pack"
    report = create_pack(*inputs, destination)
    assert verify_pack(destination) == report
    assert report["status"] == ("constraints_not_met" if unsafe else "constraints_met")
    assert len(list(destination.iterdir())) == 6
    assert load_json(destination / "candidate.json") == inputs[2]
    assert pack_payloads(*inputs) == pack_payloads(*inputs)
    with pytest.raises(AgentBomError, match="overwrite"):
        create_pack(*inputs, destination)


@pytest.mark.parametrize("name", ["policy.json", "baseline.json", "candidate.json", "review.json", "review.html", "manifest.json"])
def test_any_changed_member_is_rejected_even_for_whitespace(tmp_path, name):
    destination = tmp_path / "pack"
    create_pack(*sources(), destination)
    path = destination / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(AgentBomError, match="does not recompute"):
        verify_pack(destination)


@pytest.mark.parametrize("defect", ["extra", "missing", "symlink", "directory", "oversize"])
def test_rejects_incomplete_unexpected_or_unsafe_file_shapes(tmp_path, defect):
    destination = tmp_path / "pack"
    create_pack(*sources(), destination)
    path = destination / "review.html"
    if defect == "extra":
        (destination / "extra.txt").write_text("not part of evidence")
    elif defect == "oversize":
        path.write_bytes(b"x" * 2_000_001)
    else:
        path.unlink()
        if defect == "symlink":
            path.symlink_to(destination / "review.json")
        elif defect == "directory":
            path.mkdir()
    with pytest.raises(AgentBomError):
        verify_pack(destination)


def test_pack_directory_symlinks_are_refused(tmp_path):
    destination = tmp_path / "pack"
    create_pack(*sources(), destination)
    link = tmp_path / "link"
    link.symlink_to(destination, target_is_directory=True)
    with pytest.raises(AgentBomError):
        verify_pack(link)
    with pytest.raises(AgentBomError):
        create_pack(*sources(), link)


def test_html_escapes_untrusted_evidence_and_includes_limits_and_boundaries():
    report, payloads = pack_payloads(*sources(True, '<script>alert("case")</script>'))
    page = payloads["review.html"].decode()
    assert "<script" not in page
    assert "&lt;script&gt;" in page
    assert "Content-Security-Policy" in page
    assert "<h1>Constraints not met</h1>" in page
    assert "not sanitized" in page
    assert "Scope not reviewed" in page
    assert "Every matched scenario" in page
    assert "Observations outside the candidate limit" in page
    assert "One scenario cannot estimate" in page
    assert "aau evaluation-pack verify PATH" in page
    assert report["candidate_sha256"] in page


def test_large_output_refused_before_creating_destination(tmp_path):
    inputs = sources()
    inputs[2]["results"][0]["detail"]["large"] = "x" * 2_000_001
    with pytest.raises(AgentBomError, match="2 MB"):
        create_pack(*inputs, tmp_path / "pack")
    assert not (tmp_path / "pack").exists()


def test_cli_verifies_documented_positive_and_negative_twins(tmp_path):
    script = Path(__file__).resolve().parents[1] / "examples/evaluation-review/demo.py"
    spec = importlib.util.spec_from_file_location("review_pack_demo", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    demo = tmp_path / "demo"
    module.build_demo(demo)
    for name, code in (("legitimate", 0), ("unsafe", 1)):
        destination = tmp_path / name
        assert main(["evaluation-pack", "create", str(demo / "policy.json"), str(demo / "baseline.json"),
                     str(demo / f"{name}.json"), "--out", str(destination)]) == code
        assert main(["evaluation-pack", "verify", str(destination)]) == code
        report = json.loads((destination / "review.json").read_text())
        report["failed_constraints"] = []
        report["status"] = "invented"
        (destination / "review.json").write_text(json.dumps(report))
        assert main(["evaluation-pack", "verify", str(destination)]) == 2
