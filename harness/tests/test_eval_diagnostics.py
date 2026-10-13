from html.parser import HTMLParser
import importlib.util
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_pack import create_pack, pack_payloads, verify_pack
from aau_harness.eval_policy import review_evaluations


EXAMPLE = Path(__file__).resolve().parents[1] / "examples/evaluation-review/dossier.py"


def example():
    spec = importlib.util.spec_from_file_location("dossier_example", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs(recordings=False):
    policy, baseline, candidate, plan = example().demo_inputs()
    if recordings:
        def recording(source):
            return {"format_version": "aau-recorded-observations/1.0", "source_label": "synthetic supplied scores",
                    "scenario_ids": policy["scenario_ids"], "n_repeats": 4,
                    "evaluation_context": source["evaluation_context"],
                    "observations": [{key: row[key] for key in ("scenario_id", "repeat", "metrics")} for row in source["results"]]}
        baseline, candidate = recording(baseline), recording(candidate)
    return policy, baseline, candidate, plan


@pytest.mark.parametrize("recordings,count", [(False, 11), (True, 13)])
def test_complete_dossier_recomputes_every_view_and_input(recordings, count, tmp_path):
    policy, baseline, candidate, plan = inputs(recordings)
    folder = tmp_path / "pack"
    report = create_pack(policy, baseline, candidate, folder, recordings=recordings, diagnostics=plan)
    assert len(list(folder.iterdir())) == count
    assert verify_pack(folder, require_recordings=recordings, require_diagnostics=True) == report
    manifest = load_json(folder / "manifest.json")
    assert manifest["pack_version"] == "aau-evaluation-review-pack/2.0"
    assert manifest["input_format"] == ("recordings" if recordings else "evaluations")
    assert len(manifest["files"]) == count - 1
    assert load_json(folder / "diagnostics.json") == plan
    assert load_json(folder / "baseline-repeatability.json")["counts"]["mixed"] == 1
    assert load_json(folder / "candidate-repeatability.json")["counts"]["all_recorded_pass"] == 1
    operations = load_json(folder / "candidate-operations.json")
    assert operations["overall"]["cost"]["total_per_passing_attempt_usd"] == (None if recordings else .25)
    assert operations["overall"]["cost"]["status"] == ("unavailable" if recordings else "complete")
    assert f'Retain all {"thirteen" if recordings else "eleven"} files together' in (folder / "review.html").read_text()


def test_advisory_criteria_cannot_override_a_failed_policy_gate(tmp_path):
    policy, baseline, _, plan = inputs()
    plan["criteria"] = [plan["criteria"][0]]  # All completion passes; authorization deliberately unreviewed here.
    report = create_pack(policy, baseline, baseline, tmp_path / "pack", diagnostics=plan)
    assert report == review_evaluations(policy, baseline, baseline)
    assert report["status"] == "constraints_not_met"
    repeated = load_json(tmp_path / "pack/candidate-repeatability.json")
    assert repeated["counts"]["all_recorded_pass"] == 1
    assert repeated["unreviewed_metrics"] == ["unauthorized"]
    assert main(["evaluation-pack", "verify", str(tmp_path / "pack"), "--require-diagnostics"]) == 1


@pytest.mark.parametrize("name", ["policy.json", "baseline.json", "candidate.json", "review.json", "review.html",
    "diagnostics.json", "baseline-repeatability.json", "candidate-repeatability.json",
    "baseline-operations.json", "candidate-operations.json", "manifest.json"])
def test_any_member_change_fails_even_when_manifest_is_rehashed(tmp_path, name):
    policy, baseline, candidate, plan = inputs()
    folder = tmp_path / "pack"
    create_pack(policy, baseline, candidate, folder, diagnostics=plan)
    member = folder / name
    member.write_bytes(member.read_bytes() + b" ")
    if name != "manifest.json":
        manifest = load_json(folder / "manifest.json")
        manifest["files"][name] = digest(member.read_bytes())
        (folder / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match="does not recompute"):
        verify_pack(folder, require_diagnostics=True)


def test_coordinated_derived_report_and_manifest_change_cannot_fake_recomputation(tmp_path):
    policy, baseline, candidate, plan = inputs()
    folder = tmp_path / "pack"
    create_pack(policy, baseline, candidate, folder, diagnostics=plan)
    path = folder / "candidate-operations.json"
    report = load_json(path)
    report["overall"]["cost"]["total_per_passing_attempt_usd"] = 0
    path.write_bytes(rendered(report))
    manifest = load_json(folder / "manifest.json")
    manifest["files"][path.name] = digest(path.read_bytes())
    (folder / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match="candidate-operations"):
        verify_pack(folder)


@pytest.mark.parametrize("defect", ["missing", "extra", "symlink", "directory", "oversize"])
def test_diagnostic_file_shapes_fail_closed(tmp_path, defect):
    policy, baseline, candidate, plan = inputs()
    folder = tmp_path / "pack"
    create_pack(policy, baseline, candidate, folder, diagnostics=plan)
    member = folder / "candidate-repeatability.json"
    if defect == "extra":
        (folder / "extra.json").write_text("{}")
    elif defect == "oversize":
        member.write_bytes(b"x" * 2_000_001)
    else:
        member.unlink()
        if defect == "symlink":
            member.symlink_to(folder / "baseline-repeatability.json")
        elif defect == "directory":
            member.mkdir()
    with pytest.raises(AgentBomError):
        verify_pack(folder)


def test_require_flags_detect_valid_downgrades(tmp_path):
    policy, baseline, candidate, _ = inputs()
    create_pack(policy, baseline, candidate, tmp_path / "legacy")
    with pytest.raises(AgentBomError, match="diagnostic dossier required"):
        verify_pack(tmp_path / "legacy", require_diagnostics=True)
    _, _, _, plan = inputs()
    create_pack(policy, baseline, candidate, tmp_path / "dossier", diagnostics=plan)
    with pytest.raises(AgentBomError, match="original recordings"):
        verify_pack(tmp_path / "dossier", require_recordings=True)


@pytest.mark.parametrize("defect", ["extra", "version", "basis", "missing_basis", "draw_size", "criterion"])
def test_invalid_plan_refused_before_destination_exists(tmp_path, defect):
    policy, baseline, candidate, plan = inputs()
    if defect == "extra":
        plan["allow_failures"] = True
    elif defect == "version":
        plan["plan_version"] = "unrecognized"
    elif defect == "basis":
        plan["cost_basis"]["candidate"] = "free"
    elif defect == "missing_basis":
        del plan["cost_basis"]["baseline"]
    elif defect == "draw_size":
        plan["draw_sizes"] = [5]
    else:
        plan["criteria"][0]["metric"] = "unobserved"
    with pytest.raises(AgentBomError):
        create_pack(policy, baseline, candidate, tmp_path / "pack", diagnostics=plan)
    assert not (tmp_path / "pack").exists()


def test_corrupt_manifest_format_is_not_guessed(tmp_path):
    policy, baseline, candidate, plan = inputs()
    folder = tmp_path / "pack"
    create_pack(policy, baseline, candidate, folder, diagnostics=plan)
    manifest = load_json(folder / "manifest.json")
    del manifest["input_format"]
    (folder / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match="input_format"):
        verify_pack(folder)


class PageInventory(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.links, self.ids = [], [], set()

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        attrs = dict(attrs)
        if "href" in attrs:
            self.links.append(attrs["href"])
        if "id" in attrs:
            self.ids.add(attrs["id"])


def test_html_is_script_free_escapes_evidence_and_links_only_to_present_members():
    policy, baseline, candidate, plan = inputs()
    dangerous = '<script src="https://example.test/evil.js"></script>'
    # Change one metric consistently across all inputs; declared content never becomes markup.
    for source in (baseline, candidate):
        for row in source["results"]:
            row["metrics"][dangerous] = row["metrics"].pop("unauthorized")
        for field in ("metric_means", "metric_ci95", "metric_coverage"):
            source[field][dangerous] = source[field].pop("unauthorized")
    policy["metrics"][1]["metric"] = dangerous
    plan["criteria"][1]["metric"] = dangerous
    _, files = pack_payloads(policy, baseline, candidate, diagnostics=plan)
    page = files["review.html"].decode()
    parsed = PageInventory()
    parsed.feed(page)
    assert not set(parsed.tags) & {"script", "iframe", "img", "form"}
    assert "&lt;script" in page
    assert "Content-Security-Policy" in page
    assert "These diagnostics never change the policy verdict" in page
    assert "not inferred from the policy or its cohort limits" in page
    for link in parsed.links:
        assert link[1:] in parsed.ids if link.startswith("#") else link in files


def test_cli_demo_recomputes_both_twins_and_refuses_overwrite(tmp_path):
    module = example()
    module.build_demo(tmp_path / "demo")
    for name, code in (("intermittent", 1), ("repaired", 0)):
        assert main(["evaluation-pack", "verify", str(tmp_path / f"demo/{name}-pack"), "--require-diagnostics"]) == code
    with pytest.raises(FileExistsError):
        module.build_demo(tmp_path / "demo")
    folder = tmp_path / "cli"
    assert main(["evaluation-pack", "create", str(tmp_path / "demo/policy.json"), str(tmp_path / "demo/baseline.json"),
                 str(tmp_path / "demo/repaired.json"), "--diagnostics", str(tmp_path / "demo/diagnostics.json"),
                 "--out", str(folder)]) == 0
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == {
        p.name: p.read_bytes() for p in (tmp_path / "demo/repaired-pack").iterdir()}
    assert main(["evaluation-pack", "create", str(tmp_path / "demo/policy.json"), str(tmp_path / "demo/baseline.json"),
                 str(tmp_path / "demo/repaired.json"), "--diagnostics", str(tmp_path / "demo/diagnostics.json"),
                 "--out", str(folder)]) == 2


def test_only_display_aggregates_are_rounded_not_criterion_boundaries():
    policy, baseline, candidate, plan = inputs()
    plan["criteria"][1]["limit"] = 0.30000000000000004
    _, payloads = pack_payloads(policy, baseline, candidate, diagnostics=plan)
    page = payloads["review.html"].decode()
    assert page.count("0.30000000000000004") == 1  # Exact threshold, not repeated for the cost sum.
    assert "six significant digits" in page
