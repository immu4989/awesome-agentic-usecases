#!/usr/bin/env python3
"""Test a trusted local wheel outside the checkout in a fresh, no-index Python 3.11+ venv."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv


def smoke(wheel: Path) -> None:
    if sys.version_info < (3, 11):
        raise ValueError("this no-dependency wheel smoke requires Python 3.11+; it is not the minimum-version test")
    wheel = wheel.resolve(strict=True)
    if not wheel.is_file() or not wheel.name.startswith("aau_harness-") or wheel.suffix != ".whl":
        raise ValueError("provide one locally built aau_harness wheel")
    with tempfile.TemporaryDirectory(prefix="aau-installed-wheel-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        binary = environment / ("Scripts" if os.name == "nt" else "bin")
        python = binary / ("python.exe" if os.name == "nt" else "python")
        cli = binary / ("aau.exe" if os.name == "nt" else "aau")
        env = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "PYTHONHOME")}
        env["PYTHONNOUSERSITE"] = "1"

        def run(args, expected=0):
            result = subprocess.run([str(value) for value in args], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=60)
            if result.returncode != expected:
                raise RuntimeError(f"installed-wheel command returned {result.returncode}, expected {expected}: "
                                   + result.stdout + result.stderr)
            return result.stdout

        run([python, "-I", "-m", "pip", "--isolated", "install", "--no-index", "--no-deps", "--disable-pip-version-check", wheel])
        location = Path(run([python, "-I", "-c", "import aau_harness; print(aau_harness.__file__)"]).strip()).resolve()
        if environment.resolve() not in location.parents:
            raise RuntimeError("import resolved outside the isolated installation")
        run([cli, "runtime-info", "--out", "runtime.json"])
        run([cli, "runtime-info", "--verify", "runtime.json"])
        identity = json.loads((root / "runtime.json").read_text())
        if "runtime_info.py" not in identity["source_files"] or str(root) in json.dumps(identity):
            raise RuntimeError("installed source receipt is incomplete or exposes local paths")
        run([cli, "evaluation-demo", "--out", "demo"])
        run([cli, "evaluation-demo", "--out", "demo"], expected=2)
        run([cli, "promptfoo-eval", "demo", "--out", "promptfoo-demo"])
        run([cli, "promptfoo-review", "demo", "--out", "promptfoo-review-demo"])
        run([cli, "promptfoo-review", "demo", "--out", "promptfoo-review-demo"], expected=2)
        for name, expected in (("unsafe", 1), ("repaired", 0), ("unknown-budget", 1)):
            handoff = root / "promptfoo-review-demo" / name
            request_pin = hashlib.sha256((handoff / "request.json").read_bytes()).hexdigest()
            run([cli, "promptfoo-review", "verify", handoff, "--request-sha256", request_pin], expected=expected)
        handoff_report = json.loads((handoff / "handoff.json").read_bytes())
        if (handoff_report["policy_status"] != "constraints_met"
                or handoff_report["candidate_budget_status"] != "constraints_not_verified"
                or handoff_report["declared_context"]["status"] != "unavailable"):
            raise RuntimeError("installed Promptfoo handoff invented context or passed an unknown budget")
        run([cli, "promptfoo-review", "create", handoff / "request.json", handoff / "baseline/source.json",
             handoff / "candidate/source.json", "--request-sha256", request_pin, "--out", "promptfoo-review-copy"], expected=1)
        run([cli, "promptfoo-review", "verify", handoff, "--request-sha256", "0" * 64], expected=2)
        with (handoff / "review/review.html").open("ab") as stream:
            stream.write(b" ")
        run([cli, "promptfoo-review", "verify", handoff, "--request-sha256", request_pin], expected=2)
        run([cli, "promptfoo-eval", "demo", "--out", "promptfoo-demo"], expected=2)
        promptfoo_plan = root / "promptfoo-demo/plan.json"
        promptfoo_pin = hashlib.sha256(promptfoo_plan.read_bytes()).hexdigest()
        run([cli, "promptfoo-eval", "verify-diagnostic", "promptfoo-demo/diagnostic", "--plan-sha256", promptfoo_pin], expected=1)
        run([cli, "promptfoo-eval", "diagnose", promptfoo_plan, "promptfoo-demo/incomplete-source.json",
             "--plan-sha256", promptfoo_pin, "--out", "promptfoo-diagnostic-copy"], expected=1)
        diagnostic = json.loads((root / "promptfoo-demo/diagnostic/diagnostic.json").read_bytes())
        if (diagnostic["pair_counts"] != {"missing": 1, "unique": 4, "duplicate": 1}
                or diagnostic["recorded_rows"] != 7 or (root / "promptfoo-demo/diagnostic/evaluation.json").exists()):
            raise RuntimeError("installed Promptfoo diagnostic lost ambiguity or exported evaluation scores")
        run([cli, "promptfoo-eval", "verify-diagnostic", "promptfoo-demo/diagnostic", "--plan-sha256", "0" * 64], expected=2)
        with (root / "promptfoo-demo/diagnostic/review.html").open("ab") as stream:
            stream.write(b" ")
        run([cli, "promptfoo-eval", "verify-diagnostic", "promptfoo-demo/diagnostic", "--plan-sha256", promptfoo_pin], expected=2)
        run([cli, "promptfoo-eval", "verify", "promptfoo-demo/converted", "--plan-sha256", promptfoo_pin,
             "--evaluation", "promptfoo-demo/converted/evaluation.json"])
        run([cli, "promptfoo-eval", "create", promptfoo_plan, "promptfoo-demo/source.json",
             "--plan-sha256", promptfoo_pin, "--out", "promptfoo-copy"])
        for defect in ("missing-row", "execution-error"):
            run([cli, "promptfoo-eval", "create", promptfoo_plan, f"promptfoo-demo/{defect}.json",
                 "--plan-sha256", promptfoo_pin, "--out", f"promptfoo-{defect}"], expected=2)
        promptfoo_rows = json.loads((root / "promptfoo-demo/converted/evaluation.json").read_bytes())["results"]
        if (len(promptfoo_rows) != 3 or sum("authorization" in r["metrics"] for r in promptfoo_rows) != 2
                or sum(r["metrics"]["passed"] for r in promptfoo_rows) != 2
                or any("cost_usd" in r for r in promptfoo_rows)):
            raise RuntimeError("installed Promptfoo conversion lost failures, absence, or column selection")
        run([cli, "promptfoo-eval", "verify", "promptfoo-demo/converted", "--plan-sha256", "0" * 64], expected=2)
        with (root / "promptfoo-demo/converted/conversion.json").open("ab") as stream:
            stream.write(b" ")
        run([cli, "promptfoo-eval", "verify", "promptfoo-demo/converted", "--plan-sha256", promptfoo_pin], expected=2)
        run([cli, "coverage-review", "demo", "--out", "coverage-demo"])
        run([cli, "coverage-review", "demo", "--out", "coverage-demo"], expected=2)
        for name, expected in (("gap", 1), ("uncertain", 1), ("covered", 0)):
            packet = root / "coverage-demo" / name
            coverage_pin = hashlib.sha256((packet / "plan.json").read_bytes()).hexdigest()
            run([cli, "coverage-review", "verify", packet, "--plan-sha256", coverage_pin], expected=expected)
        coverage_report = json.loads((packet / "review.json").read_bytes())
        if coverage_report["inventory_cases"] != 5 or coverage_report["recorded_observations"] != 50:
            raise RuntimeError("installed coverage review confused repeats with distinct cases")
        run([cli, "coverage-review", "create", packet / "plan.json", packet / "inventory.json",
             packet / "evaluation.json", "--plan-sha256", coverage_pin, "--out", "coverage-copy"])
        run([cli, "coverage-review", "verify", packet, "--plan-sha256", "0" * 64], expected=2)
        with (packet / "review.html").open("ab") as stream:
            stream.write(b" ")
        run([cli, "coverage-review", "verify", packet, "--plan-sha256", coverage_pin], expected=2)
        run([cli, "inspect-eval", "demo", "--out", "inspect-demo"])
        run([cli, "inspect-eval", "demo", "--out", "inspect-demo"], expected=2)
        run([cli, "inspect-review", "demo", "--out", "inspect-review-demo"])
        run([cli, "inspect-review", "demo", "--out", "inspect-review-demo"], expected=2)
        for name, expected in (("unsafe", 1), ("repaired", 0), ("unknown-budget", 1)):
            handoff = root / "inspect-review-demo" / name
            request_pin = hashlib.sha256((handoff / "request.json").read_bytes()).hexdigest()
            run([cli, "inspect-review", "verify", handoff, "--request-sha256", request_pin], expected=expected)
        handoff_report = json.loads((handoff / "handoff.json").read_bytes())
        if (handoff_report["policy_status"] != "constraints_met"
                or handoff_report["candidate_budget_status"] != "constraints_not_verified"
                or handoff_report["declared_context"]["status"] != "unavailable"):
            raise RuntimeError("installed Inspect review invented context or passed an unknown budget")
        run([cli, "inspect-review", "create", handoff / "request.json", handoff / "baseline/source.json",
             handoff / "candidate/source.json", "--request-sha256", request_pin, "--out", "inspect-review-copy"], expected=1)
        run([cli, "inspect-review", "verify", handoff, "--request-sha256", "0" * 64], expected=2)
        with (handoff / "review/review.html").open("ab") as stream:
            stream.write(b" ")
        run([cli, "inspect-review", "verify", handoff, "--request-sha256", request_pin], expected=2)
        inspect_plan = root / "inspect-demo/plan.json"
        inspect_pin = hashlib.sha256(inspect_plan.read_bytes()).hexdigest()
        run([cli, "inspect-eval", "verify-diagnostic", "inspect-demo/diagnostic", "--plan-sha256", inspect_pin], expected=1)
        run([cli, "inspect-eval", "diagnose", inspect_plan, "inspect-demo/interrupted-source.json",
             "--plan-sha256", inspect_pin, "--out", "inspect-diagnostic-copy"], expected=1)
        diagnostic = json.loads((root / "inspect-demo/diagnostic/diagnostic.json").read_bytes())
        if (diagnostic["pair_counts"] != {"missing": 1, "unique": 2, "duplicate": 1}
                or diagnostic["recorded_rows"] != 5 or (root / "inspect-demo/diagnostic/evaluation.json").exists()):
            raise RuntimeError("installed Inspect diagnostic hid ambiguity or exported an evaluation")
        run([cli, "inspect-eval", "verify-diagnostic", "inspect-demo/diagnostic", "--plan-sha256", "0" * 64], expected=2)
        with (root / "inspect-demo/diagnostic/review.html").open("ab") as stream:
            stream.write(b" ")
        run([cli, "inspect-eval", "verify-diagnostic", "inspect-demo/diagnostic", "--plan-sha256", inspect_pin], expected=2)
        run([cli, "inspect-eval", "verify", "inspect-demo/converted", "--plan-sha256", inspect_pin,
             "--evaluation", "inspect-demo/converted/evaluation.json"])
        run([cli, "inspect-eval", "create", inspect_plan, "inspect-demo/source.json",
             "--plan-sha256", inspect_pin, "--out", "inspect-second"])
        run([cli, "inspect-eval", "create", inspect_plan, "inspect-demo/incomplete-source.json",
             "--plan-sha256", inspect_pin, "--out", "inspect-incomplete"], expected=2)
        run([cli, "inspect-eval", "verify", "inspect-demo/converted", "--plan-sha256", "0" * 64], expected=2)
        imported = json.loads((root / "inspect-demo/converted/evaluation.json").read_bytes())
        if (len(imported["results"]) != 4 or any("cost_usd" in r for r in imported["results"])
                or sum("completion" in r["metrics"] for r in imported["results"]) != 3):
            raise RuntimeError("installed Inspect conversion changed coverage or invented operating data")
        with (root / "inspect-demo/converted/conversion.json").open("ab") as stream:
            stream.write(b" ")
        run([cli, "inspect-eval", "verify", "inspect-demo/converted", "--plan-sha256", inspect_pin], expected=2)
        run([cli, "grader-demo", "--out", "grader-demo"])
        run([cli, "reference-review", "demo", "--out", "reference-demo"])
        run([cli, "reference-review", "demo", "--out", "reference-demo"], expected=2)
        reference_packet = root / "reference-demo/packet"
        reference_pin = hashlib.sha256((reference_packet / "plan.json").read_bytes()).hexdigest()
        run([cli, "reference-review", "verify", reference_packet, "--plan-sha256", reference_pin])
        run([cli, "reference-review", "create", reference_packet / "plan.json", reference_packet / "ratings.json",
             reference_packet / "adjudications.json", "--plan-sha256", reference_pin, "--out", "reference-copy"])
        exported_pin = hashlib.sha256((reference_packet / "grader-plan.json").read_bytes()).hexdigest()
        run([cli, "grader-review", reference_packet / "grader-plan.json", reference_packet / "reference.json",
             "reference-demo/candidate.json", "--plan-sha256", exported_pin, "--verify", "reference-demo/grader-report.json"])
        references = json.loads((reference_packet / "reference.json").read_bytes())["rows"]
        if [row["verdict"] for row in references] != ["pass", "fail", "disputed", "unreviewed", "unreviewed", "fail"]:
            raise RuntimeError("installed reference review hid disagreement or incomplete ratings")
        run([cli, "reference-review", "verify", reference_packet, "--plan-sha256", "0" * 64], expected=2)
        with (reference_packet / "review.html").open("ab") as stream:
            stream.write(b" ")
        run([cli, "reference-review", "verify", reference_packet, "--plan-sha256", reference_pin], expected=2)
        run([cli, "grader-demo", "--out", "grader-demo"], expected=2)
        run([cli, "grader-compare", "demo", "--out", "grader-comparison"])
        run([cli, "grader-compare", "demo", "--out", "grader-comparison"], expected=2)
        for name in ("corrected", "abstention-trap", "omission-trap", "net-gain-with-regression"):
            packet = root / "grader-comparison" / name
            pin = hashlib.sha256((packet / "plan.json").read_bytes()).hexdigest()
            base_pin = hashlib.sha256((packet / "baseline.json").read_bytes()).hexdigest()
            run([cli, "grader-compare", "verify", packet, "--plan-sha256", pin, "--baseline-sha256", base_pin])
        run([cli, "grader-compare", "verify", packet, "--plan-sha256", pin, "--baseline-sha256", "0" * 64], expected=2)
        with (packet / "review.html").open("ab") as stream:
            stream.write(b" ")
        run([cli, "grader-compare", "verify", packet, "--plan-sha256", pin, "--baseline-sha256", base_pin], expected=2)
        grader_plan = root / "grader-demo/plan.json"
        grader_pin = hashlib.sha256(grader_plan.read_bytes()).hexdigest()
        for name in ("exact-on-decided", "group-blind", "sparse", "abstaining"):
            run([cli, "grader-review", grader_plan, root / "grader-demo/reference.json",
                 root / f"grader-demo/{name}.json", "--plan-sha256", grader_pin,
                 "--verify", root / f"grader-demo/{name}-report.json"])
        sparse = json.loads((root / "grader-demo/sparse-report.json").read_text())
        sparse_validation = next(row for row in sparse["scopes"] if row["split"] == "validation" and row["group_id"] == "overall")
        if (sparse_validation["agreement_on_paired_decisions"]["value"] != 1
                or sparse_validation["paired_decision_coverage"]["value"] != 0.125):
            raise RuntimeError("installed grader diagnostic hid missing judgments")
        grader_command = [cli, "grader-review", grader_plan, root / "grader-demo/reference.json",
                          root / "grader-demo/group-blind.json"]
        run([*grader_command, "--plan-sha256", "0" * 64, "--out", "invalid-grader-report.json"], expected=2)
        altered_report = root / "grader-demo/group-blind-report.json"
        with altered_report.open("ab") as stream:
            stream.write(b" ")
        run([*grader_command, "--plan-sha256", grader_pin, "--verify", altered_report], expected=2)
        run([cli, "lifecycle-cost-demo", "--out", "lifecycle-demo"])
        run([cli, "lifecycle-cost-demo", "--out", "lifecycle-demo"], expected=2)
        cost_plan = root / "lifecycle-demo/plan.json"
        cost_pin = hashlib.sha256(cost_plan.read_bytes()).hexdigest()
        for name in ("complete", "unknown-exit", "no-rates"):
            run([cli, "lifecycle-cost", cost_plan, root / f"lifecycle-demo/{name}-rates.json",
                 "--plan-sha256", cost_pin, "--verify", root / f"lifecycle-demo/{name}-report.json"])
        complete_cost = json.loads((root / "lifecycle-demo/complete-report.json").read_text())
        unknown_cost = json.loads((root / "lifecycle-demo/unknown-exit-report.json").read_text())
        if (complete_cost["scenarios"][0]["declared_total_usd"] != "368000.000000"
                or unknown_cost["scenarios"][0]["declared_total_usd"] is not None
                or unknown_cost["scenarios"][0]["known_subtotal_usd"] != "353000.000000"):
            raise RuntimeError("installed lifecycle diagnostic hid unknown costs or miscomputed the declared total")
        cost_command = [cli, "lifecycle-cost", cost_plan, root / "lifecycle-demo/complete-rates.json"]
        run([*cost_command, "--plan-sha256", "0" * 64, "--out", "invalid-cost-report.json"], expected=2)
        cost_report = root / "lifecycle-demo/complete-report.json"
        with cost_report.open("ab") as stream:
            stream.write(b" ")
        run([*cost_command, "--plan-sha256", cost_pin, "--verify", cost_report], expected=2)
        inspect_command = [cli, "inspect-pack", "demo/repaired", "--expect", "evaluation-review"]
        run([*inspect_command, "--out", "inspection.json"])
        run([*inspect_command, "--verify", "inspection.json"])
        run([cli, "inspect-pack", "demo/intermittent", "--expect", "evaluation-review"], expected=1)
        run([*inspect_command, "--require-budget"], expected=2)
        run([cli, "inspect-pack", "demo/repaired", "--expect", "retry-review"], expected=2)
        run([cli, "inspect-pack", "demo"], expected=2)
        # Synthetic plumbing only, not independent approval: production pins must be controlled separately.
        request = {"request_version": "aau-evidence-intake-request/1.0", "profile": "evaluation-review",
                   "pack_version": "aau-evaluation-review-pack/2.0", "input_format": "recordings",
                   "pinned_inputs": {role: hashlib.sha256((root / "demo/repaired" / member).read_bytes()).hexdigest()
                                     for role, member in (("policy", "policy.json"), ("baseline", "baseline-recording.json"),
                                                          ("diagnostics", "diagnostics.json"))}}
        request_raw = json.dumps(request).encode("utf-8")
        (root / "intake-request.json").write_bytes(request_raw)
        request_pin = hashlib.sha256(request_raw).hexdigest()
        intake_command = [cli, "review-intake", "intake-request.json"]
        for name, code in (("repaired", 0), ("intermittent", 1)):
            args = [*intake_command, f"demo/{name}", "--request-sha256", request_pin]
            run([*args, "--out", f"{name}-intake.json"], expected=code)
            run([*args, "--verify", f"{name}-intake.json"], expected=code)
            ci_args = [cli, "review-ci", "intake", "intake-request.json", f"demo/{name}", "--request-sha256", request_pin]
            run([*ci_args, "--out", f"ci-{name}"], expected=code)
            run([*ci_args, "--verify", f"ci-{name}"], expected=code)
            ci = json.loads((root / f"ci-{name}/report.json").read_text())
            if ci["exit_code"] != code or bool(ci["counts"]["failures"]) != bool(code):
                raise RuntimeError("installed CI presentation changed the native requirement outcome")
        run([*intake_command, "demo/repaired", "--request-sha256", "0" * 64, "--out", "invalid-intake.json"], expected=2)
        request["pinned_inputs"]["policy"] = "0" * 64
        changed_raw = json.dumps(request).encode("utf-8")
        (root / "intake-request.json").write_bytes(changed_raw)
        run([*intake_command, "demo/repaired", "--request-sha256", hashlib.sha256(changed_raw).hexdigest(),
             "--out", "substituted-intake.json"], expected=1)
        substituted = json.loads((root / "substituted-intake.json").read_text())
        if substituted["unmatched_input_roles"] != ["policy"] or substituted["pack_inspection"]["exit_code"] != 0:
            raise RuntimeError("installed intake confused internal verification with receiver requirements")
        (root / "intake-request.json").write_bytes(request_raw)
        series_plan = {"plan_version": "aau-evidence-series-plan/1.0", "checkpoint_ids": ["before", "during", "after"]}
        plan_raw = json.dumps(series_plan).encode("utf-8")
        (root / "series-plan.json").write_bytes(plan_raw)
        for name, source in (("before", "repaired"), ("during", "intermittent"), ("after", "repaired")):
            shutil.copytree(root / "demo" / source, root / "series" / name)
        series_command = [cli, "review-series", "series-plan.json", "intake-request.json", "series",
                          "--plan-sha256", hashlib.sha256(plan_raw).hexdigest(), "--request-sha256", request_pin]
        run([*series_command, "--out", "series.json"], expected=1)
        run([*series_command, "--verify", "series.json"], expected=1)
        series = json.loads((root / "series.json").read_text())
        if series["historical_issue_checkpoint_ids"] != ["during"] or series["latest_checkpoint"]["status"] != "request_constraints_met":
            raise RuntimeError("installed series review erased an earlier failure behind a later pass")
        (root / "series/during").rename(root / "retained-checkpoint")
        run([*series_command, "--out", "series-missing.json"], expected=1)
        missing = json.loads((root / "series-missing.json").read_text())
        if missing["status"] != "series_evidence_missing" or missing["checkpoints"][1]["status"] != "missing":
            raise RuntimeError("installed series review hid a missing checkpoint")
        (root / "retained-checkpoint").rename(root / "series/during")
        (root / "series/during/review.json").write_text("{}")
        run([*series_command, "--out", "series-invalid.json"], expected=2)
        run([*series_command, "--verify", "series-invalid.json"], expected=2)
        invalid = json.loads((root / "series-invalid.json").read_text())
        if invalid["status"] != "series_not_fully_verified" or invalid["checkpoints"][1]["status"] != "invalid":
            raise RuntimeError("installed series review promoted invalid historical evidence")
        ci_series = [cli, "review-ci", "series", *series_command[2:]]
        run([*ci_series, "--out", "ci-series"], expected=2)
        run([*ci_series, "--verify", "ci-series"], expected=2)
        ci_invalid = json.loads((root / "ci-series/report.json").read_text())
        if ci_invalid["counts"]["errors"] != 1 or ci_invalid["suites"][2]["counts"]["failures"]:
            raise RuntimeError("installed CI presentation hid an invalid checkpoint behind a later pass")
        with (root / "ci-repaired/junit.xml").open("ab") as stream:
            stream.write(b" ")
        run([cli, "review-ci", "intake", "intake-request.json", "demo/repaired", "--request-sha256", request_pin,
             "--verify", "ci-repaired"], expected=2)
        routing_source = json.loads((root / "demo/repaired/candidate-recording.json").read_text())
        routing_source.pop("evaluation_context", None)  # These changed synthetic fields have no captured scoring context.
        for index, row in enumerate(routing_source["observations"]):
            row["metrics"].update(routing_score=[.1, .4, .8, .95][index], human_required=int(index == 2))
            if index == 0:
                row["metrics"]["unauthorized"] = 1
            if index == 3:
                del row["metrics"]["human_required"]
        (root / "routing-recording.json").write_text(json.dumps(routing_source))
        run([cli, "import-eval", "routing-recording.json", "--out", "routing-evaluation.json"])
        routing_plan = {"plan_version": "aau-recorded-routing-plan/1.0", "scenario_ids": routing_source["scenario_ids"],
                        "n_repeats": 4, "criteria": [{"metric": "unauthorized", "direction": "lower", "limit": 0}],
                        "score_metric": "routing_score", "mandatory_review_metric": "human_required",
                        "score_basis": "Synthetic ranking fixture, not production confidence", "thresholds": [0, .5],
                        "limits": {"minimum_automation_fraction": 0, "maximum_automated_failure_fraction": 1,
                                   "maximum_review_observations": 4}, "groups": []}
        routing_raw = json.dumps(routing_plan).encode("utf-8")
        (root / "routing-plan.json").write_bytes(routing_raw)
        routing_command = [cli, "routing-eval", "routing-plan.json", "routing-evaluation.json",
                           "--plan-sha256", hashlib.sha256(routing_raw).hexdigest()]
        run([*routing_command, "--out", "routing-report.json"])
        run([*routing_command, "--verify", "routing-report.json"])
        routing = json.loads((root / "routing-report.json").read_text())
        low, high = [item["scopes"][0] for item in routing["thresholds"]]
        if (low["automated_observations"] != 2 or low["automated_joint_failures"] != 1
                or high["automated_observations"] != 0 or high["automated_failure_fraction"] is not None
                or routing["recorded_joint_failures"] != 1 or routing["selected_threshold"] is not None):
            raise RuntimeError("installed routing diagnostic hid failures or promoted human-only/unknown routes")
        (root / "routing-plan.json").write_bytes(routing_raw + b" ")
        run([*routing_command, "--out", "invalid-routing.json"], expected=2)
        (root / "routing-plan.json").write_bytes(routing_raw)
        queue_plan = {"plan_version": "aau-human-review-queue-plan/1.0", "routing_plan_sha256": hashlib.sha256(routing_raw).hexdigest(),
                      "threshold": 0, "horizon_s": 6, "timing_basis": "synthetic", "timing_scope": "Constructed wheel check, not observed human review",
                      "initial_state": "empty_queue_idle_slots_at_zero",
                      "workers": [{"worker_id": "slot", "windows": [{"start_s": 0, "end_s": 6}]}]}
        queue_raw = json.dumps(queue_plan).encode("utf-8")
        (root / "queue-plan.json").write_bytes(queue_raw)
        work_items = {"format_version": "aau-human-review-work-items/1.0", "items": [
            {"scenario_id": routing_source["scenario_ids"][0], "repeat": index, "arrival_s": 0, "service_s": 3, "deadline_s": 4}
            for index in (2, 3)]}
        (root / "queue-items.json").write_text(json.dumps(work_items))
        queue_command = [cli, "review-queue", "queue-plan.json", "routing-plan.json", "routing-evaluation.json", "queue-items.json",
                         "--queue-plan-sha256", hashlib.sha256(queue_raw).hexdigest()]
        run([*queue_command, "--out", "queue-report.json"])
        run([*queue_command, "--verify", "queue-report.json"])
        queue = json.loads((root / "queue-report.json").read_text())
        if (queue["counts"]["scheduled"] != 2 or queue["counts"]["known_deadline_failures"] != 1
                or queue["maximum_scheduled_wait_s"] != 3 or queue["human_resolution_measured"]):
            raise RuntimeError("installed queue replay hid delays/deadlines or invented human resolution")
        queue_pin = hashlib.sha256(queue_raw).hexdigest()
        run([cli, "queue-pack", "create", "queue-plan.json", "routing-plan.json", "routing-evaluation.json", "queue-items.json",
             "--queue-plan-sha256", queue_pin, "--out", "queue-pack"])
        run([cli, "queue-pack", "verify", "queue-pack", "--queue-plan-sha256", queue_pin])
        run([cli, "queue-pack", "verify", "queue-pack", "--queue-plan-sha256", "0" * 64], expected=2)
        with (root / "queue-pack/review.html").open("ab") as stream:
            stream.write(b" ")
        run([cli, "queue-pack", "verify", "queue-pack", "--queue-plan-sha256", queue_pin], expected=2)
        work_items["items"].pop()
        (root / "queue-items.json").write_text(json.dumps(work_items))
        run([*queue_command, "--out", "incomplete-queue-report.json"], expected=2)
        service_plan = {"plan_version": "aau-service-trace-import/1.0", "source_label": "Synthetic wheel service", "n_repeats": 1}
        service_contract = {"version": "synthetic-1", "expected_terminal": "route_review", "required_evidence": [],
                            "held_evidence": [], "required_channel": "phone_711", "recourse_required": True,
                            "deadline_preservation_required": False, "forbidden_events": ["deny_application"]}
        service_suite = {"suite_version": "aau-public-value-suite/1.0",
                         "cases": [{"case_id": "service", "contract": service_contract}]}
        service_trace = {"terminal_events": ["route_review"], "requested_evidence": [], "delivery_channels": ["phone_711"],
                         "recourse_offered": False, "deadline_preserved": False, "submitted": True,
                         "attempted_events": ["route_review"], "executed_events": ["route_review"]}
        service_traces = {"trace_version": "aau-public-value-traces/1.1",
                          "observations": [{"case_id": "service", "repeat": 0, "trace": service_trace}]}
        for name, value in (("service-plan", service_plan), ("service-suite", service_suite), ("service-traces", service_traces)):
            (root / f"{name}.json").write_text(json.dumps(value))
        reproducer_inputs = ["service-plan.json", "service-suite.json", "service-traces.json"]
        run([cli, "service-reproducer", "create", *reproducer_inputs, "--out", "service-reproducer"])
        run([cli, "service-reproducer", "create", *reproducer_inputs, "--out", "service-reproducer"], expected=2)
        run([cli, "service-reproducer", "verify", "service-reproducer"])
        run([cli, "service-reproducer", "verify-source", "service-reproducer", *reproducer_inputs])
        run([cli, "inspect-pack", "service-reproducer", "--expect", "service-reproducer"], expected=1)
        run([cli, "service-trace-eval", "verify", "service-reproducer/service"], expected=1)
        minimized_files = [path for path in (root / "service-reproducer").rglob("*") if path.is_file()]
        if len(minimized_files) != 10 or any(b"Synthetic wheel service" in path.read_bytes() for path in minimized_files):
            raise RuntimeError("installed reproducer lost complete evidence or copied the original source label")
        changed_traces = json.loads(json.dumps(service_traces))
        changed_traces["observations"][0]["trace"]["recourse_offered"] = True
        (root / "service-reproducer-changed.json").write_text(json.dumps(changed_traces))
        run([cli, "service-reproducer", "verify-source", "service-reproducer", *reproducer_inputs[:2],
             "service-reproducer-changed.json"], expected=2)
        minimized_report = root / "service-reproducer/reproduction.json"
        minimized_report.write_text(minimized_report.read_text() + " ")
        run([cli, "service-reproducer", "verify", "service-reproducer"], expected=2)
        run([cli, "service-challenge", "create", "service-suite.json", "--out", "service-challenge"])
        run([cli, "service-challenge", "verify", "service-challenge"])
        run([cli, "inspect-pack", "service-challenge", "--expect", "service-challenge", "--out", "challenge-inspection.json"])
        challenge_inspection = json.loads((root / "challenge-inspection.json").read_text())
        if challenge_inspection["assessment"]["status"] != "adapter_responses_not_supplied":
            raise RuntimeError("installed intake promoted an unscored challenge")
        # Reference self-check: installed scorer receives only public challenge inputs, not oracle scores.
        run([python, "-I", "-c", """
from pathlib import Path
from aau_harness.agent_bom import digest, load_json, write_json
from aau_harness.public_value_review import assess_public_value
challenge = load_json(Path('service-challenge/challenge.json'))
responses = {'response_version': 'aau-service-challenge-responses/1.0', 'challenge_sha256': digest(challenge),
             'observations': [{'probe_id': row['probe_id'], 'metrics': assess_public_value(
                 row['input']['contract'], row['input']['trace'])['metrics']} for row in challenge['cases']]}
write_json(responses, Path('service-responses.json'))
"""])
        challenge_command = [cli, "service-challenge", "score", "service-challenge", "service-responses.json"]
        run([*challenge_command, "--out", "challenge-reference.json"])
        run([*challenge_command, "--verify", "challenge-reference.json"])
        reference_responses = json.loads((root / "service-responses.json").read_text())
        for constant in (0, 1):
            responses = json.loads(json.dumps(reference_responses))
            for row in responses["observations"]:
                row["metrics"] = dict.fromkeys(row["metrics"], constant)
            (root / "service-responses.json").write_text(json.dumps(responses))
            run([*challenge_command, "--out", f"challenge-constant-{constant}.json"], expected=1)
        reference_responses["observations"].pop()
        (root / "service-responses.json").write_text(json.dumps(reference_responses))
        run([*challenge_command, "--out", "challenge-incomplete.json"], expected=2)
        oracle_path = root / "service-challenge/oracle.json"
        oracle_path.write_text(oracle_path.read_text() + " ")
        run([cli, "service-challenge", "verify", "service-challenge"], expected=2)
        run([cli, "inspect-pack", "service-challenge"], expected=2)
        service_command = [cli, "service-trace-eval", "create", "service-plan.json", "service-suite.json", "service-traces.json"]
        run([*service_command, "--out", "service-failed"], expected=1)
        run([cli, "service-trace-eval", "verify", "service-failed", "--evaluation", "service-failed/evaluation.json"], expected=1)
        run([*service_command, "--out", "service-failed"], expected=2)
        service_evaluation = json.loads((root / "service-failed/evaluation.json").read_text())
        service_row = service_evaluation["results"][0]
        if (service_row["metrics"]["service_completion"] != 1 or service_row["metrics"]["public_value_exact"] != 0
                or any(field in service_row for field in ("cost_usd", "latency_s", "n_api_calls"))):
            raise RuntimeError("installed service scorer lost failed obligations or fabricated operating measurements")
        service_trace["recourse_offered"] = True
        (root / "service-traces.json").write_text(json.dumps(service_traces))
        run([*service_command, "--out", "service-passed"])
        run([cli, "service-trace-eval", "verify", "service-passed"])
        run([cli, "service-trace-eval", "verify", "service-failed", "--evaluation", "service-passed/evaluation.json"], expected=2)
        service_row["metrics"]["public_value_exact"] = 1
        (root / "service-failed/evaluation.json").write_text(json.dumps(service_evaluation))
        run([cli, "service-trace-eval", "verify", "service-failed"], expected=2)
        service_criteria = [{"metric": "public_value_exact", "direction": "higher", "limit": 1}]
        service_policy = {"policy_version": "aau-evaluation-review-policy/1.0", "scenario_ids": ["service"],
                          "minimum_repeats": 1, "metrics": [{"metric": "public_value_exact", "direction": "higher",
                          "candidate_observation_limit": 1, "max_mean_regression": 0, "max_regressed_scenarios": 0}]}
        service_diagnostics = {"plan_version": "aau-evaluation-diagnostics/1.0", "criteria": service_criteria,
                               "draw_sizes": [1], "cost_basis": {"baseline": "synthetic", "candidate": "synthetic"}}
        service_budget = {"plan_version": "aau-operating-budget/1.0", "scenario_ids": ["service"], "minimum_repeats": 1,
                          "criteria": service_criteria, "cost_basis": "synthetic", "groups": [],
                          "limits": {"cost_per_passing_attempt_usd": .12}}
        for name, value in (("service-policy", service_policy), ("service-diagnostics", service_diagnostics),
                            ("service-budget", service_budget)):
            (root / f"{name}.json").write_text(json.dumps(value))
        service_command = [cli, "service-review", "create", "service-policy.json", "service-suite.json",
                           "service-plan.json", "service-traces.json", "service-plan.json", "service-candidate.json",
                           "--diagnostics", "service-diagnostics.json"]
        for name, code in (("unknown", 1), ("repaired", 0), ("burden", 1)):
            if name != "unknown":
                service_traces["observations"][0].update(cost_usd=.1, latency_s=2, n_api_calls=1)
            service_trace["recourse_offered"] = name != "burden"
            (root / "service-candidate.json").write_text(json.dumps(service_traces))
            directory = f"service-handoff-{name}"
            run([*service_command, "--operating-budget", "service-budget.json", "--out", directory], expected=code)
            run([cli, "service-review", "verify", directory, "--require-budget"], expected=code)
            run([cli, "inspect-pack", directory, "--expect", "service-review", "--require-budget"], expected=code)
            if len([p for p in (root / directory).rglob('*') if p.is_file()]) != 33:
                raise RuntimeError("installed service handoff lost source or gate evidence")
        run([*service_command, "--out", "service-ungated"], expected=1)
        run([cli, "service-review", "verify", "service-ungated", "--require-budget"], expected=2)
        service_policy["metrics"][0]["metric"] = "service_completion"
        (root / "service-policy.json").write_text(json.dumps(service_policy))
        run([*service_command, "--out", "service-completion-shortcut"], expected=2)
        if (root / "service-completion-shortcut").exists():
            raise RuntimeError("completion-only service policy created a misleading handoff")
        (root / "service-handoff-repaired/candidate/suite.json").write_text('{}')
        run([cli, "service-review", "verify", "service-handoff-repaired", "--require-budget"], expected=2)
        revised_suite = json.loads(json.dumps(service_suite))
        revised_suite["cases"][0]["contract"]["recourse_required"] = False
        (root / "revised-service-suite.json").write_text(json.dumps(revised_suite))
        contract_command = [cli, "compare-service-contracts", "service-suite.json", "revised-service-suite.json",
                            "--plan", "service-plan.json", "--traces", "service-candidate.json"]
        run([*contract_command, "--out", "contract-change.json"], expected=1)
        run([*contract_command, "--verify", "contract-change.json"], expected=1)
        contract_review = json.loads((root / "contract-change.json").read_text())
        if (contract_review["frozen_trace_review"]["joint_pass_counts"] != {"baseline": 0, "candidate": 1}
                or contract_review["changes"][0]["kind"] != "protection_no_longer_required"):
            raise RuntimeError("contract edit was not distinguished from changed service behavior")
        run([cli, "compare-service-contracts", "service-suite.json", "service-suite.json",
             "--plan", "service-plan.json", "--traces", "service-candidate.json", "--out", "unchanged-contract.json"])
        run([*contract_command, "--out", "contract-change.json"], expected=2)
        contract_review["changes"] = []
        (root / "contract-change.json").write_text(json.dumps(contract_review))
        run([*contract_command, "--verify", "contract-change.json"], expected=2)
        revised_suite["cases"].append({"case_id": "extra-service", "contract": revised_suite["cases"][0]["contract"]})
        (root / "revised-service-suite.json").write_text(json.dumps(revised_suite))
        run([cli, "compare-service-contracts", "service-suite.json", "revised-service-suite.json", "--out", "changed-census.json"], expected=1)
        run([*contract_command, "--out", "subset-shortcut.json"], expected=2)
        if (root / "subset-shortcut.json").exists():
            raise RuntimeError("contract rescoring silently selected an incomplete case intersection")
        bound_plan = {"plan_version": "aau-failure-bound-plan/1.0", "scenario_ids": ["synthetic-service"],
                      "n_repeats": 4, "criteria": [{"metric": "completion", "direction": "higher", "limit": 1},
                                                   {"metric": "unauthorized", "direction": "lower", "limit": 0}],
                      "sampling_design": "fixed_benchmark", "sampling_basis": "Synthetic installed-wheel fixture only.",
                      "confidence_level": .95, "maximum_failure_probability": .05, "groups": []}
        (root / "bound-plan.json").write_text(json.dumps(bound_plan))
        bound_command = [cli, "failure-bound-eval", "bound-plan.json", "demo/repaired/candidate.json"]
        run([*bound_command, "--out", "benchmark-bound.json"])
        run([*bound_command, "--verify", "benchmark-bound.json"])
        if json.loads((root / "benchmark-bound.json").read_text())["status"] != "population_inference_withheld":
            raise RuntimeError("fixed benchmark incorrectly produced population inference")
        bound_plan["sampling_design"] = "declared_iid_fixed_horizon"
        (root / "bound-plan.json").write_text(json.dumps(bound_plan))
        run([*bound_command, "--out", "conditional-bound.json"])
        run([*bound_command, "--verify", "conditional-bound.json"])
        conditional = json.loads((root / "conditional-bound.json").read_text())
        if conditional["status"] != "conditional_bounds_exceed_limits" or conditional["scenario_count"] != 1:
            raise RuntimeError("repeats were counted as independent scenarios or missing sufficiency was hidden")
        run([*bound_command, "--out", "conditional-bound.json"], expected=2)
        conditional["scopes"][0]["one_sided_upper_failure_bound"] = 0
        (root / "conditional-bound.json").write_text(json.dumps(conditional))
        run([*bound_command, "--verify", "conditional-bound.json"], expected=2)
        run([cli, "failure-bound-pack", "create", "bound-plan.json", "demo/repaired/candidate.json", "--out", "bound-pack"])
        run([cli, "failure-bound-pack", "verify", "bound-pack"])
        (root / "bound-pack/review.html").write_text('tampered reviewer page')
        run([cli, "failure-bound-pack", "verify", "bound-pack"], expected=2)
        run([cli, "failure-bound-demo", "--out", "failure-demo"])
        run([cli, "failure-bound-demo", "--out", "failure-demo"], expected=2)
        run([cli, "paired-review", "demo", "--out", "paired-demo"])
        run([cli, "evidence-index", "demo", "--out", "evidence-index-demo"])
        run([cli, "evaluation-design", "demo", "--out", "evaluation-design-demo"])
        run([cli, "evaluation-design", "demo", "--out", "evaluation-design-demo"], expected=2)
        for name in ("planned", "limited", "family", "fixed-benchmark"):
            design_packet = root / "evaluation-design-demo" / name
            design_pin = hashlib.sha256((design_packet / "plan.json").read_bytes()).hexdigest()
            run([cli, "evaluation-design", "verify", design_packet, "--plan-sha256", design_pin])
        design_packet = root / "evaluation-design-demo/planned"
        design_pin = hashlib.sha256((design_packet / "plan.json").read_bytes()).hexdigest()
        run([cli, "evaluation-design", "create", design_packet / "plan.json", "--plan-sha256", design_pin,
             "--out", "design-copy"])
        design_report = json.loads((design_packet / "report.json").read_bytes())
        if (design_report["decision_status"] != "not_assessed"
                or design_report["scopes"][0]["design"]["scenario_count"] != 124
                or design_report["scopes"][0]["zero_failure_reference"]["meets_requested_probability"]):
            raise RuntimeError("study planner confused a zero-failure reference with the requested design probability")
        run([cli, "evaluation-design", "verify", design_packet, "--plan-sha256", "0" * 64], expected=2)
        with (design_packet / "report.json").open("ab") as stream:
            stream.write(b" ")
        run([cli, "evaluation-design", "verify", design_packet, "--plan-sha256", design_pin], expected=2)
        run([cli, "evidence-index", "demo", "--out", "evidence-index-demo"], expected=2)
        for name, expected in (("complete-with-failed-policy", 0), ("missing-coverage", 1),
                               ("mismatched-evaluation", 1), ("invalid-comparison", 1), ("changed-controls", 1)):
            index_packet = root / "evidence-index-demo" / name
            index_pin = hashlib.sha256((index_packet / "request.json").read_bytes()).hexdigest()
            run([cli, "evidence-index", "verify", index_packet, "--request-sha256", index_pin], expected=expected)
        complete_index = root / "evidence-index-demo/complete-with-failed-policy"
        complete_pin = hashlib.sha256((complete_index / "request.json").read_bytes()).hexdigest()
        run([cli, "evidence-index", "create", complete_index / "request.json", complete_index / "evidence",
             "--request-sha256", complete_pin, "--out", "evidence-index-copy"])
        index_report = json.loads((complete_index / "report.json").read_bytes())
        if (index_report["decision_status"] != "not_assessed" or not index_report["human_review_required"]
                or index_report["items"][0]["native_outcome_status"] != "constraints_not_met"):
            raise RuntimeError("evidence index confused a complete delivery with policy approval")
        run([cli, "evidence-index", "verify", complete_index, "--request-sha256", "0" * 64], expected=2)
        run([cli, "evidence-bag", "create", complete_index, "--out", "evidence-bag"])
        transferred = root / "evidence-bag"
        transfer_pin = hashlib.sha256((transferred / "tagmanifest-sha256.txt").read_bytes()).hexdigest()
        run([cli, "evidence-bag", "verify", transferred, "--tagmanifest-sha256", transfer_pin])
        run([cli, "evidence-index", "verify", transferred / "data", "--request-sha256", complete_pin])
        run([cli, "evidence-bag", "create", complete_index, "--out", "evidence-bag"], expected=2)
        run([cli, "evidence-bag", "verify", transferred, "--tagmanifest-sha256", "0" * 64], expected=2)
        with (transferred / "data/report.json").open("ab") as stream:
            stream.write(b" ")
        run([cli, "evidence-bag", "verify", transferred, "--tagmanifest-sha256", transfer_pin], expected=2)
        with (complete_index / "report.json").open("ab") as stream:
            stream.write(b" ")
        run([cli, "evidence-index", "verify", complete_index, "--request-sha256", complete_pin], expected=2)
        run([cli, "paired-review", "demo", "--out", "paired-demo"], expected=2)
        for name in ("net-gain-with-regression", "fixed-benchmark", "same-recorded-outcomes", "reversed-comparison"):
            pair_packet = root / "paired-demo" / name
            pair_pin = hashlib.sha256((pair_packet / "plan.json").read_bytes()).hexdigest()
            run([cli, "paired-review", "verify", pair_packet, "--plan-sha256", pair_pin])
        run([cli, "paired-review", "create", pair_packet / "plan.json", pair_packet / "baseline.json",
             pair_packet / "candidate.json", "--plan-sha256", pair_pin, "--out", "paired-copy"])
        run([cli, "paired-review", "verify", pair_packet, "--plan-sha256", "0" * 64], expected=2)
        paired = json.loads((root / "paired-demo/net-gain-with-regression/report.json").read_bytes())
        fixed_pair = json.loads((root / "paired-demo/fixed-benchmark/report.json").read_bytes())
        if (paired["scopes"][0]["regressed"] != 1 or paired["scopes"][0]["scenario_count"] != 12
                or paired["scopes"][0]["bonferroni_adjusted_p"]["value"] != 0.0234375
                or fixed_pair["scopes"][0]["two_sided_exact_p"] is not None):
            raise RuntimeError("paired comparison hid regressions, counted repeats as pairs, or inferred from a benchmark")
        with (pair_packet / "review.html").open("ab") as stream:
            stream.write(b" ")
        run([cli, "paired-review", "verify", pair_packet, "--plan-sha256", pair_pin], expected=2)
        run([cli, "candidate-bounds", "demo", "--out", "candidate-bound-demo"])
        run([cli, "candidate-bounds", "demo", "--out", "candidate-bound-demo"], expected=2)
        for name in ("pending", "complete", "fixed-benchmark", "earlier-failure"):
            packet = root / "candidate-bound-demo" / name
            pin = hashlib.sha256((packet / "plan.json").read_bytes()).hexdigest()
            run([cli, "candidate-bounds", "verify", packet, "--plan-sha256", pin])
        run([cli, "candidate-bounds", "create", packet / "plan.json", packet / "candidates",
             "--plan-sha256", pin, "--out", "candidate-bound-copy"])
        run([cli, "candidate-bounds", "verify", packet, "--plan-sha256", "0" * 64], expected=2)
        pending = json.loads((root / "candidate-bound-demo/pending/report.json").read_bytes())
        complete = json.loads((root / "candidate-bound-demo/complete/report.json").read_bytes())
        if pending["candidates"][0] != complete["candidates"][0] or pending["missing_candidate_count"] != 1:
            raise RuntimeError("installed candidate-family review reallocated missing-candidate uncertainty")
        with (packet / "review.html").open("ab") as stream:
            stream.write(b" ")
        run([cli, "candidate-bounds", "verify", packet, "--plan-sha256", pin], expected=2)
        for name, expected in (("fixed-benchmark", "population_inference_withheld"),
                               ("few-scenarios", "conditional_bounds_exceed_limits"),
                               ("more-scenarios", "conditional_bounds_within_limits"),
                               ("small-group", "conditional_bounds_exceed_limits")):
            run([cli, "failure-bound-pack", "verify", f"failure-demo/{name}"])
            if json.loads((root / f"failure-demo/{name}/report.json").read_text())["status"] != expected:
                raise RuntimeError("installed failure-bound walkthrough lost an expected interpretation")
        if len([p for p in (root / "failure-demo").rglob('*') if p.is_file()]) != 21:
            raise RuntimeError("installed failure-bound walkthrough is incomplete")
        planned = json.loads((root / "failure-demo/more-scenarios/plan.json").read_text())
        planned["plan_version"] = "aau-planned-look-bound-plan/1.0"
        planned["scenario_order"] = planned.pop("scenario_ids") + [f"future-{i}" for i in range(40)]
        planned.update(look_sizes=[20, 60, 100], sampling_design="declared_iid_planned_looks")
        # Synthetic fixture pin only; production expectations must be independently controlled.
        for design, expected in (("declared_iid_planned_looks", "conditional_planned_look_diagnostic"),
                                  ("fixed_benchmark", "population_inference_withheld")):
            planned["sampling_design"] = design
            raw = json.dumps(planned).encode("utf-8")
            (root / "planned-looks.json").write_bytes(raw)
            command = [cli, "planned-look-bounds", "planned-looks.json", "failure-demo/more-scenarios/evaluation.json",
                       "--plan-sha256", hashlib.sha256(raw).hexdigest()]
            run([*command, "--out", f"planned-{design}.json"])
            run([*command, "--verify", f"planned-{design}.json"])
            result = json.loads((root / f"planned-{design}.json").read_text())
            if result["status"] != expected or result["pending_look_count"] != 1 or result["method"]["family_size"] != 3:
                raise RuntimeError("installed planned-look diagnostic dropped a pending look or changed its family")
            if design == "declared_iid_planned_looks" and result["latest_completed_look"]["status"] != "conditional_bounds_exceed_limits":
                raise RuntimeError("installed planned-look diagnostic reused a single-look confidence claim")
            (root / "planned-looks.json").write_bytes(raw + b" ")
            run([*command, "--out", "invalid-planned-report.json"], expected=2)
        run([cli, "retry-demo", "--out", "retry-demo"])
        run([cli, "retry-demo", "--out", "retry-demo"], expected=2)
        for name, code in (("earlier-harm", 1), ("slow-completion", 1), ("repaired", 0)):
            run([cli, "retry-review", "verify", f"retry-demo/{name}", "--require-budget"], expected=code)
        retry_demo_files = [p for p in (root / "retry-demo").rglob("*") if p.is_file()]
        if len(retry_demo_files) != 94 or not (root / "retry-demo/README.txt").is_file():
            raise RuntimeError("installed retry walkthrough is incomplete")
        retry_plan = {"plan_version": "aau-retry-accounting/1.0", "source_label": "installed-wheel synthetic retries",
                      "scenario_ids": ["service"], "n_repeats": 1, "attempt_scope": "sequential_disjoint",
                      "metric_reducers": {"completion": "last", "unauthorized": "max"}}
        retry_ledger = {"ledger_version": "aau-task-attempt-ledger/1.0", "tasks": [
            {"scenario_id": "service", "repeat": 0, "attempt_count": 2, "elapsed_s": 10, "attempts": [
                {"attempt_id": "first", "attempt_index": 0, "metrics": {"completion": 0, "unauthorized": 1},
                 "cost_usd": .1, "latency_s": 1, "n_api_calls": 1},
                {"attempt_id": "last", "attempt_index": 1, "metrics": {"completion": 1, "unauthorized": 0},
                 "cost_usd": .1, "latency_s": 1, "n_api_calls": 1}]}]}
        (root / "retry-plan.json").write_text(json.dumps(retry_plan))
        (root / "retry-ledger.json").write_text(json.dumps(retry_ledger))
        run([cli, "retry-eval", "create", "retry-plan.json", "retry-ledger.json", "--out", "retry-pack"])
        run([cli, "retry-eval", "verify", "retry-pack", "--evaluation", "retry-pack/evaluation.json"])
        trace_id, root_id = "1" * 32, "1" * 16
        otlp_spans = [{"traceId": trace_id, "spanId": root_id,
                       "startTimeUnixNano": "1000000000", "endTimeUnixNano": "11000000000"}]
        for index, attempt in enumerate(retry_ledger["tasks"][0]["attempts"]):
            otlp_spans.append({"traceId": trace_id, "spanId": str(index + 2) * 16, "parentSpanId": root_id,
                               "startTimeUnixNano": str((index + 1) * 1_000_000_000),
                               "endTimeUnixNano": str((index + 2) * 1_000_000_000),
                               "attributes": [{"key": key, "value": {"intValue": str(value)} if type(value) is int
                                               else {"doubleValue": value}} for key, value in {
                                   **attempt["metrics"], "cost_usd": attempt["cost_usd"], "n_api_calls": 1}.items()]})
        otlp_mapping = {"mapping_version": "aau-otlp-retry-import/1.0", "source_format": "otlp_json",
                        "span_semantics": "single_attempt_direct_children_same_resource_clock",
                        "accounting_plan": retry_plan,
                        "attributes": {"metrics": {"completion": "completion", "unauthorized": "unauthorized"},
                                       "operating": {"cost_usd": "cost_usd", "n_api_calls": "n_api_calls"}},
                        "tasks": [{"scenario_id": "service", "repeat": 0, "trace_id": trace_id,
                                   "task_span_id": root_id, "attempt_span_ids": ["2" * 16, "3" * 16]}], "excluded_spans": []}
        (root / "otlp-mapping.json").write_text(json.dumps(otlp_mapping))
        (root / "source.otlp").write_text(json.dumps({"resourceSpans": [{"scopeSpans": [{"spans": otlp_spans}]}]}))
        run([cli, "otlp-retries", "create", "otlp-mapping.json", "source.otlp", "--out", "otlp-pack"])
        run([cli, "otlp-retries", "verify", "otlp-pack", "--evaluation", "otlp-pack/retry/evaluation.json"])
        projected = json.loads((root / "otlp-pack/retry/evaluation.json").read_text())["results"][0]
        if projected["metrics"]["unauthorized"] != 1 or projected["cost_usd"] != .2 or projected["latency_s"] != 10:
            raise RuntimeError("installed OTLP bridge lost earlier harm, cost, or task duration")
        (root / "otlp-pack/retry/ledger.json").write_text('{}')
        run([cli, "otlp-retries", "verify", "otlp-pack"], expected=2)
        retry_source = json.loads((root / "retry-pack/evaluation.json").read_text())
        retry_row = retry_source["results"][0]
        if (retry_row["metrics"] != {"completion": 1, "unauthorized": 1} or retry_row["cost_usd"] != .2
                or retry_row["latency_s"] != 10 or retry_row["n_api_calls"] != 2):
            raise RuntimeError("installed retry accounting dropped prior costs, harm, or whole-task timing")
        run([cli, "retry-eval", "create", "retry-plan.json", "retry-ledger.json", "--out", "retry-pack"], expected=2)
        retry_source["results"][0]["cost_usd"] = .1
        (root / "wrong-retry-evaluation.json").write_text(json.dumps(retry_source))
        run([cli, "retry-eval", "verify", "retry-pack", "--evaluation", "wrong-retry-evaluation.json"], expected=2)
        retry_criteria = [{"metric": "completion", "direction": "higher", "limit": 1},
                          {"metric": "unauthorized", "direction": "lower", "limit": 0}]
        retry_policy = {"policy_version": "aau-evaluation-review-policy/1.0", "scenario_ids": ["service"],
                        "minimum_repeats": 1, "metrics": [{"metric": r["metric"], "direction": r["direction"],
                            "candidate_observation_limit": r["limit"], "max_mean_regression": 0,
                            "max_regressed_scenarios": 0} for r in retry_criteria]}
        retry_diagnostics = {"plan_version": "aau-evaluation-diagnostics/1.0", "criteria": retry_criteria,
                             "draw_sizes": [1], "cost_basis": {"baseline": "synthetic", "candidate": "synthetic"}}
        retry_budget = {"plan_version": "aau-operating-budget/1.0", "scenario_ids": ["service"], "minimum_repeats": 1,
                        "criteria": retry_criteria, "cost_basis": "synthetic", "groups": [],
                        "limits": {"cost_per_passing_attempt_usd": .25, "p95_latency_s": 10}}
        for name, value in (("retry-policy", retry_policy), ("retry-diagnostics", retry_diagnostics), ("retry-budget", retry_budget)):
            (root / f"{name}.json").write_text(json.dumps(value))
        retry_command = [cli, "retry-review", "create", "retry-policy.json", "retry-plan.json", "retry-ledger.json",
                         "retry-plan.json", "retry-ledger.json", "--diagnostics", "retry-diagnostics.json"]
        run([*retry_command, "--out", "ungated-retry-handoff"], expected=1)
        run([cli, "retry-review", "verify", "ungated-retry-handoff", "--require-budget"], expected=2)
        for repaired in (False, True):
            if repaired:
                retry_ledger["tasks"][0]["attempts"][0]["metrics"]["unauthorized"] = 0
                (root / "retry-candidate.json").write_text(json.dumps(retry_ledger))
                retry_command[7] = "retry-candidate.json"
            directory = "repaired-retry-handoff" if repaired else "failed-retry-handoff"
            run([*retry_command, "--operating-budget", "retry-budget.json", "--out", directory], expected=0 if repaired else 1)
            run([cli, "retry-review", "verify", directory, "--require-budget"], expected=0 if repaired else 1)
        otlp_command = [cli, "otlp-review", "create", "retry-policy.json", "otlp-mapping.json", "source.otlp",
                        "otlp-mapping.json", "source.otlp", "--diagnostics", "retry-diagnostics.json"]
        run([*otlp_command, "--out", "ungated-otlp-handoff"], expected=1)
        run([cli, "otlp-review", "verify", "ungated-otlp-handoff", "--require-budget"], expected=2)
        for repaired in (False, True):
            if repaired:
                candidate_trace = json.loads((root / "source.otlp").read_text())
                for span in candidate_trace["resourceSpans"][0]["scopeSpans"][0]["spans"]:
                    for attribute in span.get("attributes", []):
                        if attribute["key"] == "unauthorized":
                            attribute["value"] = {"intValue": "0"}
                (root / "candidate.otlp").write_text(json.dumps(candidate_trace))
                otlp_command[7] = "candidate.otlp"
            directory = "repaired-otlp-handoff" if repaired else "failed-otlp-handoff"
            run([*otlp_command, "--operating-budget", "retry-budget.json", "--out", directory], expected=0 if repaired else 1)
            run([cli, "otlp-review", "verify", directory, "--require-budget"], expected=0 if repaired else 1)
            if len([p for p in (root / directory).rglob("*") if p.is_file()]) != 39:
                raise RuntimeError("installed OTLP handoff lost original trace evidence")
        (root / "repaired-otlp-handoff/candidate/source.otlp").write_bytes(b'{}')
        run([cli, "otlp-review", "verify", "repaired-otlp-handoff", "--require-budget"], expected=2)
        for name, code in (("intermittent", 1), ("repaired", 0)):
            run([cli, "evaluation-pack", "verify", f"demo/{name}", "--require-recordings", "--require-diagnostics"], code)
        repaired = root / "demo/repaired"
        matrix_plan = {"plan_version": "aau-candidate-matrix/1.0", "candidate_ids": ["intermittent", "repaired"],
                       "criteria": json.loads((repaired / "diagnostics.json").read_text())["criteria"],
                       "cost_basis": {"intermittent": "synthetic", "repaired": "synthetic"}}
        (root / "matrix-plan.json").write_text(json.dumps(matrix_plan))
        run([cli, "candidate-matrix", "create", "matrix-plan.json", repaired / "policy.json", repaired / "baseline.json",
             "--candidate", "intermittent=demo/intermittent/candidate.json",
             "--candidate", "repaired=demo/repaired/candidate.json", "--out", "matrix"])
        run([cli, "candidate-matrix", "verify", "matrix"])
        matrix = json.loads((root / "matrix/matrix.json").read_text())
        if matrix["operating_groups"][0]["eligible_candidates"] != ["repaired"]:
            raise RuntimeError("installed matrix allowed failed policy to enter operating comparisons")
        budget = {"plan_version": "aau-operating-budget/1.0",
                  "scenario_ids": json.loads((repaired / "policy.json").read_text())["scenario_ids"],
                  "minimum_repeats": 4, "criteria": matrix_plan["criteria"], "cost_basis": "synthetic",
                  "limits": {"p95_latency_s": 2, "cost_per_passing_attempt_usd": .25}, "groups": []}
        (root / "budget.json").write_text(json.dumps(budget))
        for name, code in (("intermittent", 1), ("repaired", 0)):
            args = [cli, "operating-budget", "budget.json", f"demo/{name}/candidate.json", "--cost-basis", "synthetic"]
            run([*args, "--out", f"{name}-budget.json"], code)
            run([*args, "--verify", f"{name}-budget.json"], code)
        matrix_plan.update(plan_version="aau-candidate-matrix/1.1", operating_budget=budget)
        (root / "budget-matrix-plan.json").write_text(json.dumps(matrix_plan))
        run([cli, "candidate-matrix", "create", "budget-matrix-plan.json", repaired / "policy.json", repaired / "baseline.json",
             "--candidate", "intermittent=demo/intermittent/candidate.json",
             "--candidate", "repaired=demo/repaired/candidate.json", "--out", "budget-matrix"])
        run([cli, "candidate-matrix", "verify", "budget-matrix"])
        budget_matrix = json.loads((root / "budget-matrix/matrix.json").read_text())
        if [r["budget_status"] for r in budget_matrix["candidates"]] != ["constraints_not_met", "constraints_met"]:
            raise RuntimeError("installed matrix omitted recorded operating budget checks")
        for name, code in (("intermittent", 1), ("repaired", 0)):
            source_pack = root / f"demo/{name}"
            run([cli, "evaluation-pack", "from-recordings", source_pack / "policy.json", source_pack / "baseline-recording.json",
                 source_pack / "candidate-recording.json", "--diagnostics", source_pack / "diagnostics.json",
                 "--operating-budget", "budget.json", "--out", f"gated-{name}"], code)
            run([cli, "evaluation-pack", "verify", f"gated-{name}", "--require-recordings", "--require-budget"], code)
        run([cli, "evaluation-pack", "verify", repaired, "--require-budget"], expected=2)
        budget["limits"]["p95_latency_s"] = 1
        (root / "strict-budget.json").write_text(json.dumps(budget))
        run([cli, "compare-operating-budgets", "budget.json", "strict-budget.json", "--out", "budget-changes.json"], 1)
        run([cli, "compare-operating-budgets", "budget.json", "strict-budget.json", "--verify", "budget-changes.json"], 1)
        run([cli, "compare-operating-budgets", "budget.json", "budget.json", "--out", "unchanged-budget.json"])
        run([cli, "evaluation-pack", "create", repaired / "policy.json", repaired / "baseline.json", repaired / "candidate.json",
             "--diagnostics", repaired / "diagnostics.json", "--operating-budget", "strict-budget.json", "--out", "budget-only-failure"], 1)
        run([cli, "evaluation-pack", "verify", "budget-only-failure", "--require-budget"], 1)
        if json.loads((root / "budget-only-failure/review.json").read_text())["status"] != "constraints_met":
            raise RuntimeError("combined budget gate changed the independent policy verdict")
        baseline, candidate = repaired / "baseline-recording.json", repaired / "candidate-recording.json"
        run([cli, "compare-eval-contexts", baseline, candidate, "--input-format", "recordings", "--out", "context.json"])
        run([cli, "compare-eval-contexts", baseline, candidate, "--input-format", "recordings", "--verify", "context.json"])
        run([cli, "import-eval", candidate, "--out", "imported.json"])
        run([cli, "import-eval", candidate, "--verify", "imported.json"])
        # These tiny fixtures are created outside the checkout, not loaded from repository examples.
        csv_plan = {"plan_version": "aau-csv-observation-import/1.0", "source_label": "synthetic wheel smoke",
                    "scenario_ids": ["case"], "n_repeats": 1,
                    "columns": {"scenario_id": "case", "repeat": "repeat", "metrics": {"completion": "score"},
                                "operating": {"cost_usd": "usd"}}}
        (root / "csv-plan.json").write_text(json.dumps(csv_plan))
        (root / "source.csv").write_bytes(b"case,repeat,score,usd\ncase,0,1,0.1\n")
        run([cli, "csv-eval", "create", "csv-plan.json", "source.csv", "--out", "converted"])
        run([cli, "csv-eval", "verify", "converted", "--evaluation", "converted/evaluation.json"])
        policy = {"policy_version": "aau-evaluation-review-policy/1.0", "scenario_ids": ["case"],
                  "minimum_repeats": 1, "metrics": [{"metric": "completion", "direction": "higher",
                  "candidate_observation_limit": 1, "max_mean_regression": 0, "max_regressed_scenarios": 0}]}
        diagnostics = {"plan_version": "aau-evaluation-diagnostics/1.0",
                       "criteria": [{"metric": "completion", "direction": "higher", "limit": 1}],
                       "draw_sizes": [1], "cost_basis": {"baseline": "synthetic", "candidate": "synthetic"}}
        (root / "csv-policy.json").write_text(json.dumps(policy))
        (root / "csv-diagnostics.json").write_text(json.dumps(diagnostics))
        (root / "failed.csv").write_bytes(b"case,repeat,score,usd\ncase,0,0,0.1\n")
        for filename, code in (("source.csv", 0), ("failed.csv", 1)):
            destination = "handoff-" + filename
            run([cli, "csv-review", "create", "csv-policy.json", "csv-plan.json", "source.csv",
                 "csv-plan.json", filename, "--diagnostics", "csv-diagnostics.json", "--out", destination], code)
            run([cli, "csv-review", "verify", destination], code)
        csv_budget = {"plan_version": "aau-operating-budget/1.0", "scenario_ids": ["case"], "minimum_repeats": 1,
                      "criteria": diagnostics["criteria"], "cost_basis": "synthetic",
                      "limits": {"cost_per_passing_attempt_usd": .2}, "groups": []}
        (root / "csv-budget.json").write_text(json.dumps(csv_budget))
        run([cli, "csv-review", "create", "csv-policy.json", "csv-plan.json", "source.csv", "csv-plan.json", "source.csv",
             "--diagnostics", "csv-diagnostics.json", "--operating-budget", "csv-budget.json", "--out", "gated-csv"])
        run([cli, "csv-review", "verify", "gated-csv", "--require-budget"])
        run([cli, "csv-review", "verify", "handoff-source.csv", "--require-budget"], 2)
        (root / "handoff-source.csv/candidate/source.csv").write_bytes(b"case,repeat,score,usd\ncase,0,0,0.1\n")
        run([cli, "csv-review", "verify", "handoff-source.csv"], expected=2)
        report_path = repaired / "candidate-operations.json"
        report = json.loads(report_path.read_text())
        report["overall"]["cost"]["total_usd"] = 999
        report_path.write_text(json.dumps(report))
        run([cli, "evaluation-pack", "verify", repaired, "--require-recordings", "--require-diagnostics"], expected=2)
    print("Installed wheel verified outside checkout: demos, conditional failure bounds, policy and operating budget outcomes, candidate matrices, recording/CSV/OTLP import, strict service-trace and other source-retaining handoffs, context review, overwrite refusal, and tamper rejection.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    try:
        smoke(args.wheel)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
