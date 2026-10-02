"""Recompute service-result diagnostics without treating stored scores as ground truth."""

from .agent_bom import AgentBomError, digest
from .public_value_review import assess_public_value_batch, _label


def review_service_results(source: dict) -> dict:
    if not isinstance(source, dict):
        raise AgentBomError("service results must be an object")
    scenarios, repeats = source.get("n_scenarios"), source.get("n_repeats")
    if (type(scenarios) is not int or type(repeats) is not int or scenarios < 1 or repeats < 1
            or scenarios * repeats > 500):
        raise AgentBomError("service review requires 1 to 500 declared scenario-repeat observations")
    rows = source.get("results")
    if not isinstance(rows, list) or len(rows) != scenarios * repeats:
        raise AgentBomError("service results do not cover the declared observation count")
    seen, contracts, predictions, metrics = set(), {}, {}, {}
    suite = {"suite_version": "aau-public-value-suite/1.0", "cases": []}
    traces = {"trace_version": "aau-public-value-traces/1.0", "observations": []}
    mapping = []
    for row in rows:
        if not isinstance(row, dict) or not _label(row.get("scenario_id")):
            raise AgentBomError("invalid service scenario ID")
        scenario, repeat = row["scenario_id"], row.get("repeat")
        if type(repeat) is not int or not 0 <= repeat < repeats or (scenario, repeat) in seen:
            raise AgentBomError("invalid or duplicate scenario-repeat observation")
        seen.add((scenario, repeat))
        detail = row.get("detail")
        if not isinstance(detail, dict) or "public_value_trace" not in detail:
            raise AgentBomError("service result lacks an explicit portable trace; rerun with the current harness")
        if detail.get("error") is not None:
            raise AgentBomError("service execution errors are not reviewable measurements")
        contract = detail.get("contract")
        if scenario in contracts and digest(contract) != digest(contracts[scenario]):
            raise AgentBomError("service contract changed across repeats of one scenario")
        contracts[scenario] = contract
        prediction = detail.get("predicted")
        if not isinstance(prediction, dict) or set(prediction) != {"outcome"}:
            raise AgentBomError("service prediction must explicitly record an outcome")
        if prediction["outcome"] is not None and not _label(prediction["outcome"]):
            raise AgentBomError("invalid service predicted outcome")
        case_id = digest([scenario, repeat])
        predictions[case_id], metrics[case_id] = prediction["outcome"], row.get("metrics")
        mapping.append({"case_id": case_id, "scenario_id": scenario, "repeat": repeat})
        suite["cases"].append({"case_id": case_id, "contract": contract})
        traces["observations"].append({"case_id": case_id, "trace": detail["public_value_trace"]})
    if len(contracts) != scenarios:
        raise AgentBomError("service scenario count does not match declaration")
    # Unique bounded repeat indices and the exact product/count imply complete repeat coverage.
    batch = assess_public_value_batch(suite, traces)
    source_traces = {row["case_id"]: row["trace"] for row in traces["observations"]}
    source_contracts = {row["case_id"]: row["contract"] for row in suite["cases"]}
    record_findings, failed = [], []
    for case in batch["cases"]:
        case_id, assessment = case["case_id"], case["assessment"]
        trace = source_traces[case_id]
        terminal = trace["terminal_events"][0] if len(trace["terminal_events"]) == 1 else None
        fidelity = float(trace["submitted"] and predictions[case_id] == terminal)
        accuracy = float(trace["submitted"] and predictions[case_id] == source_contracts[case_id]["expected_terminal"])
        expected = {key: value for key, value in assessment["metrics"].items() if key != "public_value_exact"}
        expected.update(record_fidelity=fidelity, outcome_accuracy=accuracy,
                        service_exact=assessment["metrics"]["public_value_exact"] * fidelity * accuracy)
        supplied = metrics[case_id]
        if (not isinstance(supplied, dict) or set(supplied) != set(expected)
                or any(type(supplied[key]) not in (int, float) or supplied[key] != value for key, value in expected.items())):
            raise AgentBomError("service per-observation metrics do not recompute")
        if not fidelity or not accuracy:
            record_findings.append({"case_id": case_id, "record_fidelity": fidelity,
                                    "outcome_accuracy": accuracy, "predicted_outcome": predictions[case_id]})
        if not expected["service_exact"]:
            failed.append(case_id)
    return {
        "report_version": "aau-service-result-review/1.0", "source_sha256": digest(source),
        "scenario_count": scenarios, "repeats": repeats,
        "observations": sorted(mapping, key=lambda item: (item["scenario_id"], item["repeat"])),
        "public_value": batch, "record_findings": record_findings,
        "failed_observation_ids": sorted(failed),
        "status": "evidence_failed" if failed else "evidence_passed",
        "boundary": "Recomputed declared scenario-repeat coverage and per-observation service metrics only. Aggregate means, confidence intervals, cost, latency, provider availability, and provenance are not verified. Source and normalized traces are supplied evidence, not authenticated execution. Historical results without explicit submission traces must be rerun, not inferred. No production safety or public-benefit claim.",
    }
