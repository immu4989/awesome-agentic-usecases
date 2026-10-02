import json
import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError
from aau_harness.catalog_cli import main
from aau_harness.eval_audit import audit_evaluation
from aau_harness.runner import ScenarioResult, run_eval


def fixture():
    def run_one(scenario, repeat):
        metrics = {"accuracy": float(scenario == "one")}
        if scenario == "one" and repeat == 0:
            metrics["partial"] = -2.0
        return ScenarioResult(scenario, repeat, metrics, 0, 0.1, 0)
    return run_eval(["one", "two"], run_one, repeats=2).as_dict()


def test_audit_recomputes_partial_metrics_without_zero_imputation():
    source = fixture()
    report = audit_evaluation(source)
    assert report["status"] == "consistent"
    assert report["recomputed"]["metric_means"] == {"accuracy": 0.5, "partial": -2.0}
    assert report["metric_coverage"]["partial"]["reporting_observations"] == 1
    assert report == audit_evaluation(source)
    del source["metric_coverage"]
    legacy = audit_evaluation(source)
    assert legacy["status"] == "consistent"
    assert not legacy["coverage_was_recorded"]


@pytest.mark.parametrize("field", ["metric_means", "metric_ci95", "metric_coverage"])
def test_audit_exposes_changed_or_invented_summaries(field):
    source = fixture()
    source[field] = {"invented": None}
    report = audit_evaluation(source)
    assert report["status"] == "inconsistent"
    assert any(row["field"] == field for row in report["mismatches"])


@pytest.mark.parametrize("change", ["missing", "duplicate", "repeat", "count", "nan", "bool", "no-summary"])
def test_audit_refuses_malformed_measurement_sets(change):
    source = fixture()
    if change == "missing":
        source["results"].pop()
    elif change == "duplicate":
        source["results"][1] = deepcopy(source["results"][0])
    elif change == "repeat":
        source["results"][0]["repeat"] = True
    elif change == "count":
        source["n_scenarios"] = 1
    elif change == "nan":
        source["results"][0]["metrics"]["accuracy"] = float("nan")
    elif change == "bool":
        source["results"][0]["metrics"]["accuracy"] = True
    else:
        del source["metric_ci95"]
    with pytest.raises(AgentBomError):
        audit_evaluation(source)


@pytest.mark.parametrize("mismatch", [False, True])
def test_audit_cli_exit_status_and_offline_reverification(tmp_path, mismatch):
    source = fixture()
    if mismatch:
        source["metric_means"]["accuracy"] = 1.0
    original, report = tmp_path / "evaluation.json", tmp_path / "audit.json"
    original.write_text(json.dumps(source))
    args = ["audit-eval", str(original), "--out", str(report)]
    assert main(args) == int(mismatch)
    saved = report.read_bytes()
    assert main(args) == 2
    assert report.read_bytes() == saved
    verify = ["audit-eval", str(original), "--verify", str(report)]
    assert main(verify) == int(mismatch)
    value = json.loads(saved)
    value["observation_count"] = 0
    report.write_text(json.dumps(value))
    assert main(verify) == 2


def test_existing_committed_lab_result_has_recomputable_metric_summaries():
    path = Path(__file__).resolve().parents[2] / "home-field-services/service-visit-readiness-coordinator/results/eval_mock.json"
    source = json.loads(path.read_text())
    assert audit_evaluation(source)["status"] == "consistent"


def test_full_precision_legacy_summaries_are_compared_at_declared_precision():
    source = run_eval(["one", "two", "three"], lambda scenario, repeat:
                      ScenarioResult(scenario, repeat, {"accuracy": float(scenario == "one")}, 0, 0.1, 0),
                      repeats=1).as_dict()
    source["metric_means"]["accuracy"] = 1 / 3
    assert audit_evaluation(source)["status"] == "consistent"
    source["metric_means"]["accuracy"] = True
    assert audit_evaluation(source)["status"] == "inconsistent"


def test_corpus_audit_binds_files_and_excludes_unpublished_assets(tmp_path):
    script = Path(__file__).resolve().parents[1] / "tools/audit_repository_evals.py"
    spec = importlib.util.spec_from_file_location("repository_eval_audit", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / "industry/lab/results/eval_mock.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(fixture()))
    original = path.read_bytes()
    for directory in ("output", "social-assets", "tmp"):
        excluded = tmp_path / directory / "lab/results/eval_private.json"
        excluded.parent.mkdir(parents=True)
        excluded.write_text("private unparsed material")
    first = module.audit_repository(tmp_path)
    assert first["file_count"] == 1
    assert first["counts"] == {"consistent": 1}
    assert path.read_bytes() == original
    path.write_bytes(original + b"\n")
    second = module.audit_repository(tmp_path)
    assert first["files"][0]["file_sha256"] != second["files"][0]["file_sha256"]
    assert second["counts"] == {"consistent": 1}
