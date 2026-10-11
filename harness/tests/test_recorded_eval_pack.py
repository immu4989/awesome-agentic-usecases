from copy import deepcopy
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, digest
from aau_harness.catalog_cli import main
from aau_harness.eval_import import import_observations
from aau_harness.eval_pack import create_pack, verify_pack


EXAMPLES = Path(__file__).resolve().parents[1] / "examples/evaluation-review"


def inputs():
    policy = json.loads((EXAMPLES / "policy-original.json").read_text())
    baseline = json.loads((EXAMPLES / "recorded-observations.json").read_text())
    candidate = deepcopy(baseline)
    candidate["observations"][0]["metrics"]["unauthorized_action"] = 1
    return policy, baseline, candidate


def test_recorded_pack_recomputes_the_complete_supplied_score_to_review_chain(tmp_path):
    policy, baseline, candidate = inputs()
    folder = tmp_path / "pack"
    report = create_pack(policy, baseline, candidate, folder, recordings=True)
    assert report == verify_pack(folder, require_recordings=True)
    assert report["status"] == "constraints_not_met"
    assert len(list(folder.iterdir())) == 8
    assert json.loads((folder / "baseline-recording.json").read_text()) == baseline
    assert json.loads((folder / "candidate.json").read_text()) == import_observations(candidate)
    assert json.loads((folder / "manifest.json").read_text())["pack_version"] == "aau-evaluation-review-pack/1.1"
    page = (folder / "review.html").read_text()
    assert "Retain all eight files" in page
    assert "--require-recordings" in page
    assert "not original execution or scoring" in page


@pytest.mark.parametrize("member", ["policy.json", "baseline.json", "candidate.json", "review.json", "review.html",
                                     "manifest.json", "baseline-recording.json", "candidate-recording.json"])
def test_every_chain_member_must_reproduce_exactly(tmp_path, member):
    folder = tmp_path / "pack"
    create_pack(*inputs(), folder, recordings=True)
    path = folder / member
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(AgentBomError):
        verify_pack(folder)


def test_rehashing_a_tampered_normalized_export_does_not_hide_conversion_drift(tmp_path):
    folder = tmp_path / "pack"
    create_pack(*inputs(), folder, recordings=True)
    path = folder / "candidate.json"
    value = json.loads(path.read_text())
    value["provenance"]["source_label"] = "substituted provenance"
    path.write_text(json.dumps(value))
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest["files"]["candidate.json"] = digest(path.read_bytes())
    (folder / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(AgentBomError):
        verify_pack(folder, require_recordings=True)


def test_normalized_only_pack_cannot_satisfy_explicit_recording_requirement(tmp_path):
    policy, baseline, candidate = inputs()
    folder = tmp_path / "normal"
    create_pack(policy, import_observations(baseline), import_observations(candidate), folder)
    assert verify_pack(folder)["status"] == "constraints_not_met"
    with pytest.raises(AgentBomError, match="original recordings are required"):
        verify_pack(folder, require_recordings=True)
    assert main(["evaluation-pack", "verify", str(folder), "--require-recordings"]) == 2


def test_incomplete_recording_never_creates_a_pack(tmp_path):
    policy, baseline, candidate = inputs()
    candidate["observations"].pop()
    with pytest.raises(AgentBomError):
        create_pack(policy, baseline, candidate, tmp_path / "invalid", recordings=True)
    assert not (tmp_path / "invalid").exists()


def test_cli_from_recordings_retains_failed_review_and_refuses_overwrite(tmp_path):
    paths = []
    for name, value in zip(("policy", "baseline", "candidate"), inputs()):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(value))
        paths.append(str(path))
    folder = tmp_path / "pack"
    command = ["evaluation-pack", "from-recordings", *paths, "--out", str(folder)]
    assert main(command) == 1
    assert main(["evaluation-pack", "verify", str(folder), "--require-recordings"]) == 1
    assert main(command) == 2
