import importlib.util
from io import BytesIO
import json
from pathlib import Path
import zipfile

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
    assert len(assets) == 15
    for name, expected in (("legitimate", "constraints_met"), ("unsafe", "constraints_not_met")):
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
            assert {row["scenario_id"] for row in source["results"]} == {"routine", "needs-authorization"}


def test_public_page_has_honest_boundaries_complete_paths_and_no_scripts():
    assets = generator().build_assets()
    page = assets["index.html"].decode()
    assert "<script" not in page
    assert "Content-Security-Policy" in page
    assert "constructed fixtures" in page
    assert "not measured model" in page
    assert "unsaf" not in page.split("<h1>")[1].split("</h1>")[0]
    for name in ("legitimate", "unsafe"):
        assert f'href="{name}/review.html"' in page
        assert f'href="{name}.zip" download' in page
    assert "75%" in page
    assert "100%" in page
    assert "exits <strong>1</strong>" in page
    assert "inspect sensitive information before sharing" in page.lower()


def test_committed_public_snapshot_matches_current_generator():
    assets = generator().build_assets()
    target = ROOT / "docs/evaluation-review"
    assert {path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file()} == set(assets)
    assert all((target / name).read_bytes() == payload for name, payload in assets.items())
