import importlib.util
from io import BytesIO
import json
from pathlib import Path
import zipfile

import pytest

from aau_harness.agent_bom import AgentBomError
from aau_harness.eval_pack import verify_pack


ROOT = Path(__file__).resolve().parents[2]


def generator():
    spec = importlib.util.spec_from_file_location("public_eval_assets", ROOT / "docs/make_evaluation_review_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_assets_are_deterministic_and_archives_match_complete_verifiable_packs(tmp_path):
    module = generator()
    assets = module.build_assets()
    assert assets == module.build_assets()
    assert len(assets) == 53
    for name, expected in (("legitimate", "constraints_met"), ("unsafe", "constraints_not_met"),
                           ("cohort-regressed", "constraints_not_met"), ("cohort-repaired", "constraints_met")):
        directory = tmp_path / name
        directory.mkdir()
        with zipfile.ZipFile(BytesIO(assets[f"{name}.zip"])) as bundle:
            assert set(bundle.namelist()) == {"policy.json", "baseline.json", "candidate.json", "review.json", "review.html", "manifest.json"}
            for filename in bundle.namelist():
                payload = bundle.read(filename)
                assert payload == assets[f"{name}/{filename}"]
                (directory / filename).write_bytes(payload)
        report = verify_pack(directory)
        assert report["status"] == expected
        assert all(row["context_match"]["status"] == "matched" for row in report["comparisons"])
        for filename in ("baseline.json", "candidate.json"):
            source = json.loads(assets[f"{name}/{filename}"])
            assert source["provenance"]["evidence_kind"] == "synthetic_fixture"
            assert "placeholders" in source["provenance"]["measurement_boundary"]
            expected_ids = {"routine-1", "routine-2", "routine-3", "assisted"} if name.startswith("cohort-") else {"routine", "needs-authorization"}
            assert {row["scenario_id"] for row in source["results"]} == expected_ids


def test_public_page_has_honest_boundaries_complete_paths_and_no_scripts():
    assets = generator().build_assets()
    page = assets["index.html"].decode()
    assert "<script" not in page
    assert "Content-Security-Policy" in page
    assert "constructed fixtures" in page
    assert "not measured model" in page
    assert "unsaf" not in page.split("<h1>")[1].split("</h1>")[0]
    for name in ("legitimate", "unsafe", "cohort-regressed", "cohort-repaired"):
        assert f'href="{name}/review.html"' in page
        assert f'href="{name}.zip" download' in page
    assert "75%" in page
    assert "100%" in page
    assert "exits <strong>1</strong>" in page
    assert "inspect sensitive information before sharing" in page.lower()
    assert 'id="cohort-story"' in page
    assert "degenerate interval" in page


def test_public_cohort_story_reports_real_fixture_relationship_not_a_marketing_claim():
    assets = generator().build_assets()
    report = json.loads(assets["cohort-regressed/review.json"])
    assert report["comparisons"][0]["mean_delta"] == 0.5
    assert all(check["passed"] for check in report["metric_checks"][0]["checks"])
    assert {failure["cohort_id"] for failure in report["failed_constraints"]} == {"assisted"}
    assisted = next(group for group in report["cohort_reviews"] if group["cohort_id"] == "assisted")
    assert assisted["comparisons"][0]["mean_delta"] == -1
    assert json.loads(assets["cohort-repaired/review.json"])["status"] == "constraints_met"


def test_committed_public_snapshot_matches_current_generator():
    assets = generator().build_assets()
    target = ROOT / "docs/evaluation-review"
    assert {path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file()} == set(assets)
    assert all((target / name).read_bytes() == payload for name, payload in assets.items())


@pytest.mark.parametrize("name,expected", [("dossier-intermittent", "constraints_not_met"),
                                            ("dossier-repaired", "constraints_met")])
def test_public_dossiers_are_complete_recomputable_and_tamper_sensitive(tmp_path, name, expected):
    assets = generator().build_assets()
    with zipfile.ZipFile(BytesIO(assets[f"{name}.zip"])) as bundle:
        assert len(bundle.namelist()) == 11
        assert all('/' not in item and '..' not in item for item in bundle.namelist())
        for filename in bundle.namelist():
            assert bundle.read(filename) == assets[f"{name}/{filename}"]
            (tmp_path / filename).write_bytes(bundle.read(filename))
    assert verify_pack(tmp_path, require_diagnostics=True)["status"] == expected
    report = json.loads((tmp_path / "candidate-operations.json").read_text())
    assert report["declared_cost_basis"] == "synthetic"
    report["overall"]["cost"]["total_per_passing_attempt_usd"] = 0
    (tmp_path / "candidate-operations.json").write_text(json.dumps(report))
    with pytest.raises(AgentBomError):
        verify_pack(tmp_path, require_diagnostics=True)


def test_operating_story_exposes_the_cost_and_repeatability_reversals():
    assets = generator().build_assets()
    page = assets["index.html"].decode().split('id="operating-story"')[1]
    for name, count, cost, median, tail, all_pass in (
            ("dossier-intermittent", 1, .4, 1, 12, 0), ("dossier-repaired", 4, .25, 2, 2, 1)):
        operations = json.loads(assets[f"{name}/candidate-operations.json"])["overall"]
        repeated = json.loads(assets[f"{name}/candidate-repeatability.json"])
        assert operations["passing_attempt_count"] == count
        assert operations["cost"]["total_per_passing_attempt_usd"] == cost
        assert operations["latency"]["p50_s"] == median
        assert operations["latency"]["p95_s"] == tail
        assert repeated["curve"][-1]["any_pass_fraction"] == 1
        assert repeated["curve"][-1]["all_pass_fraction"] == all_pass
        assert f'${cost:.2f}' in page
        assert f'{median:g} s / {tail:g} s' in page
        assert f'href="{name}/review.html#diagnostics"' in page
        assert f'href="{name}.zip" download' in page
    assert page.count('<strong>Fail</strong>') == 3
    assert page.count('<strong>Pass</strong>') == 5
    for boundary in ("--require-diagnostics", "not a stable tail-risk estimate", "not future-run probabilities",
                     "not separate people served", "never override", "eleven-file", "unrecorded infrastructure"):
        assert boundary in page


def test_operating_story_renders_report_values_not_hardcoded_marketing_numbers():
    module = generator()
    assets = module.build_assets()
    dossiers = {name: {filename: json.loads(assets[f"{name}/{filename}"])
                      for filename in ("candidate.json", "candidate-operations.json", "candidate-repeatability.json", "review.json")}
                for name in ("dossier-intermittent", "dossier-repaired")}
    dossiers["dossier-intermittent"]["candidate-operations.json"]["overall"]["cost"]["total_per_passing_attempt_usd"] = 7.89
    assert '$7.89' in module.operating_story(dossiers)
    assert '$0.40' not in module.operating_story(dossiers)
