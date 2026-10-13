from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from aau_harness.agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_csv import verify_csv_pack
from aau_harness.eval_csv_review import create_handoff, handoff_payloads, verify_handoff
from aau_harness.eval_pack import verify_pack
from aau_harness.evaluation_context import capture_context


EXAMPLES = Path(__file__).resolve().parents[1] / "examples/evaluation-review"


def inputs():
    plan = json.loads((EXAMPLES / "csv-plan.json").read_text())
    return [json.loads((EXAMPLES / "csv-review-policy.json").read_text()), plan,
            (EXAMPLES / "scored-observations.csv").read_bytes(), deepcopy(plan),
            (EXAMPLES / "scored-observations-repaired.csv").read_bytes(),
            json.loads((EXAMPLES / "csv-review-diagnostics.json").read_text())]


def test_complete_deterministic_handoff_binds_originals_and_standalone_components(tmp_path):
    args = inputs()
    args[2] = b"\xef\xbb\xbf" + args[2].replace(b"\n", b"\r\n")
    before = deepcopy(args)
    pack = tmp_path / "handoff"
    report = create_handoff(*args, pack)
    assert args == before
    assert report == verify_handoff(pack)
    assert report["status"] == "constraints_met"
    assert report["sources"]["baseline"]["source_csv_sha256"] == digest(args[2])
    assert (pack / "baseline/source.csv").read_bytes() == args[2]
    paths = [path for path in pack.rglob("*") if path.is_file()]
    assert len(paths) == 28
    expected = handoff_payloads(*args)[1]
    assert expected == handoff_payloads(*args)[1]
    assert all(path.read_bytes() == expected[path.relative_to(pack).as_posix()] for path in paths)
    for side in ("baseline", "candidate"):
        verify_csv_pack(pack / side, evaluation_path=pack / f"review/{side}.json")
    review = verify_pack(pack / "review", require_recordings=True, require_diagnostics=True)
    assert review["status"] == report["status"]
    assert review["comparisons"][0]["context_match"]["status"] != "matched"
    baseline = json.loads((pack / "review/baseline-operations.json").read_text())
    candidate = json.loads((pack / "review/candidate-operations.json").read_text())
    assert baseline["overall"]["cost"]["total_usd"] is None
    assert candidate["overall"]["cost"]["total_per_passing_attempt_usd"] == .25


@pytest.mark.parametrize("member", sorted(handoff_payloads(*inputs())[1]))
def test_every_member_is_recomputed_not_just_rehashed(tmp_path, member):
    pack = tmp_path / "handoff"
    create_handoff(*inputs(), pack)
    path = pack / member
    path.write_bytes(path.read_bytes() + b" ")
    if member != "manifest.json":
        manifest = json.loads((pack / "manifest.json").read_text())
        manifest["files"][member] = digest(path.read_bytes())
        (pack / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        verify_handoff(pack)


@pytest.mark.parametrize("replacement", ["review", "candidate", "baseline"])
def test_individually_valid_but_unrelated_components_cannot_be_substituted(tmp_path, replacement):
    original, alternate = tmp_path / "original", tmp_path / "alternate"
    args = inputs()
    create_handoff(*args, original)
    # A source-label change does not change scores, but changes the retained recording contract.
    args[1]["source_label"] = "different baseline source"
    args[3]["source_label"] = "different candidate source"
    create_handoff(*args, alternate)
    for path in (alternate / replacement).iterdir():
        shutil.copyfile(path, original / replacement / path.name)
    if replacement == "review":
        verify_pack(original / replacement, require_recordings=True, require_diagnostics=True)
    else:
        verify_csv_pack(original / replacement)
    # Even a freshly hashed outer inventory cannot manufacture the broken cross-folder link.
    manifest = json.loads((original / "manifest.json").read_text())
    for name in manifest["files"]:
        manifest["files"][name] = digest((original / name).read_bytes())
    (original / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match="does not recompute"):
        verify_handoff(original)


@pytest.mark.parametrize("defect", ["root-extra", "nested-extra", "missing", "directory-member",
                                    "root-symlink", "group-symlink", "member-symlink", "oversized"])
def test_invalid_layouts_rejected(tmp_path, defect):
    pack = tmp_path / "pack"
    create_handoff(*inputs(), pack)
    if defect == "root-extra":
        (pack / "extra").write_text("x")
    elif defect == "nested-extra":
        (pack / "candidate/extra").write_text("x")
    elif defect == "missing":
        (pack / "manifest.json").unlink()
    elif defect == "directory-member":
        (pack / "handoff.json").unlink()
        (pack / "handoff.json").mkdir()
    elif defect == "oversized":
        (pack / "handoff.json").write_bytes(b"x" * (MAX_JSON_BYTES + 1))
    else:
        target = pack if defect == "root-symlink" else pack / ("review" if defect == "group-symlink" else "candidate/source.csv")
        moved = tmp_path / "moved"
        target.rename(moved)
        target.symlink_to(moved, target_is_directory=moved.is_dir())
    with pytest.raises(AgentBomError):
        verify_handoff(pack)


@pytest.mark.parametrize("defect", ["invalid-csv", "invalid-policy", "invalid-diagnostics", "missing-diagnostics", "context-drift"])
def test_invalid_sources_never_create_output(tmp_path, defect):
    args = inputs()
    if defect == "invalid-csv":
        args[4] += b"\n"
    elif defect == "invalid-policy":
        args[0]["minimum_repeats"] = False
    elif defect == "invalid-diagnostics":
        args[5]["draw_sizes"] = [100]
    elif defect == "missing-diagnostics":
        args[5] = None
    else:
        args[1]["evaluation_context"] = capture_context([{"scenario_id": "service"}], {"v": 1}, {"s.py": b"x"})
        args[3]["evaluation_context"] = capture_context([{"scenario_id": "service"}], {"v": 2}, {"s.py": b"x"})
    with pytest.raises(AgentBomError):
        create_handoff(*args, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("repaired,code", [(True, 0), (False, 1)])
def test_cli_retains_failed_policy_and_works_outside_checkout(tmp_path, monkeypatch, capsys, repaired, code):
    monkeypatch.chdir(tmp_path)
    candidate = "scored-observations-repaired.csv" if repaired else "scored-observations.csv"
    command = ["csv-review", "create", str(EXAMPLES / "csv-review-policy.json"), str(EXAMPLES / "csv-plan.json"),
               str(EXAMPLES / "scored-observations.csv"), str(EXAMPLES / "csv-plan.json"), str(EXAMPLES / candidate),
               "--diagnostics", str(EXAMPLES / "csv-review-diagnostics.json"), "--out", "handoff"]
    assert main(command) == code
    assert main(["csv-review", "verify", "handoff"]) == code
    assert main(command) == 2
    output = capsys.readouterr()
    assert "all 28 files recomputed" in output.out
    assert "case_id" not in output.out + output.err
    (tmp_path / "handoff/README.txt").write_text("tampered")
    assert main(["csv-review", "verify", "handoff"]) == 2


@pytest.mark.parametrize("kind", ["file", "directory", "symlink"])
def test_no_existing_destination_is_overwritten(tmp_path, kind):
    target = tmp_path / "existing"
    if kind == "file":
        target.write_text("keep")
    elif kind == "directory":
        target.mkdir()
    else:
        target.symlink_to(tmp_path / "not-created")
    with pytest.raises(AgentBomError, match="overwrite"):
        create_handoff(*inputs(), target)
    assert target.read_text() == "keep" if kind == "file" else target.is_symlink() if kind == "symlink" else not list(target.iterdir())


def test_different_explicit_maps_preserve_metric_meanings(tmp_path):
    args = inputs()
    args[3]["columns"]["metrics"]["completion"] = "task_finished"
    args[3]["columns"]["operating"]["cost_usd"] = "dollars"
    args[4] = args[4].replace(b"completed", b"task_finished").replace(b",usd,", b",dollars,")
    create_handoff(*args, tmp_path / "mapped")
    assert verify_handoff(tmp_path / "mapped")["status"] == "constraints_met"


def test_interrupted_write_never_leaves_a_complete_root_manifest(tmp_path, monkeypatch):
    original = Path.open
    def interrupted(path, mode="r", *args, **kwargs):
        if path.name == "review.html" and mode == "xb":
            raise OSError("simulated disk interruption")
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, "open", interrupted)
    with pytest.raises(OSError, match="interruption"):
        create_handoff(*inputs(), tmp_path / "partial")
    assert not (tmp_path / "partial/manifest.json").exists()
    with pytest.raises(AgentBomError):
        verify_handoff(tmp_path / "partial")


def test_coordinated_source_replacement_is_not_falsely_claimed_to_be_authenticated(tmp_path):
    args = inputs()
    args[2] = args[4]
    # Full replacement of source and derived evidence is internally consistent, not authenticated.
    create_handoff(*args, tmp_path / "replaced")
    assert verify_handoff(tmp_path / "replaced")["status"] == "constraints_met"
    assert "coordinated replacement" in (tmp_path / "replaced/README.txt").read_text()
