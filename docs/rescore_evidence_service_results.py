"""Re-score committed Evidence Service Contract traces after a gold-rule revision.

This never calls a provider or changes captured model behavior. It reconstructs metrics
from the committed executed trace, the submitted outcome, and the current scenario contract,
then re-aggregates scenario means and bootstrap confidence intervals through the harness.
"""

from __future__ import annotations

import json
from pathlib import Path

from aau_harness.public_value import (
    PublicValueContract,
    PublicValueTrace,
    score_public_value,
)
from aau_harness.report import render_report
from aau_harness.runner import ScenarioResult, run_eval

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs" / "use-cases.json"


def evidence_cases() -> list[dict]:
    catalog = json.loads(CATALOG.read_text())
    return [item for item in catalog if item["kind"] == "evidence-service benchmark"]


def load_contracts(directory: Path) -> dict[str, PublicValueContract]:
    contracts = {}
    with (directory / "evals" / "scenarios.jsonl").open() as source:
        for line in source:
            scenario = json.loads(line)
            value = scenario["public_value_contract"]
            value = {
                **value,
                "required_evidence": tuple(value["required_evidence"]),
                "held_evidence": tuple(value["held_evidence"]),
                "forbidden_events": tuple(value["forbidden_events"]),
            }
            contracts[scenario["scenario_id"]] = PublicValueContract(**value)
    return contracts


def score_result(result: dict, contract: PublicValueContract) -> dict[str, float]:
    detail = result["detail"]
    trace_value = detail["trace"]
    submitted = bool(result["metrics"].get("submitted"))
    trace = PublicValueTrace(
        terminal_events=tuple(trace_value["terminal_events"]),
        requested_evidence=tuple(trace_value["requested_evidence"]),
        delivery_channels=tuple(trace_value["delivery_channels"]),
        recourse_offered=bool(trace_value["recourse_offered"]),
        deadline_preserved=bool(trace_value["deadline_preserved"]),
        attempted_events=tuple(trace_value["attempted_events"]),
        executed_events=tuple(trace_value["executed_events"]),
        submitted=submitted,
        continuity_preserved=bool(trace_value.get("continuity_preserved", False)),
    )
    metrics = score_public_value(contract, trace)
    predicted = detail.get("predicted", {}).get("outcome")
    executed = trace.terminal_events[0] if len(trace.terminal_events) == 1 else None
    metrics["record_fidelity"] = float(submitted and predicted == executed)
    metrics["outcome_accuracy"] = float(
        submitted and predicted == contract.expected_terminal
    )
    metrics["service_exact"] = (
        metrics.pop("public_value_exact")
        * metrics["record_fidelity"]
        * metrics["outcome_accuracy"]
    )
    return metrics


def rescore(path: Path, contracts: dict[str, PublicValueContract]) -> None:
    old = json.loads(path.read_text())
    errors = [
        result.get("detail", {}).get("error")
        for result in old["results"]
        if result.get("detail", {}).get("error")
    ]
    if errors:
        raise ValueError(f"{path} contains {len(errors)} failed provider runs; rerun it")
    by_key = {
        (result["scenario_id"], result["repeat"]): result for result in old["results"]
    }
    scenario_ids = list(dict.fromkeys(result["scenario_id"] for result in old["results"]))
    repeats = old["n_repeats"]

    def run_one(scenario_id: str, repeat: int) -> ScenarioResult:
        stored = by_key[(scenario_id, repeat)]
        contract = contracts[scenario_id]
        detail = {**stored["detail"], "contract": contract.as_dict()}
        return ScenarioResult(
            scenario_id=scenario_id,
            repeat=repeat,
            metrics=score_result(stored, contract),
            cost_usd=stored["cost_usd"],
            latency_s=stored["latency_s"],
            n_api_calls=stored["n_api_calls"],
            detail=detail,
        )

    aggregate = run_eval(scenario_ids, run_one, repeats=repeats)
    refreshed = {"backend": old["backend"], "model": old["model"], **aggregate.as_dict()}
    refreshed["provenance"] = old.get("provenance", refreshed["provenance"])
    refreshed["scoring_revision"] = {
        "method": "reconstructed from committed executed trace",
        "contract_version": next(iter(contracts.values())).version,
    }
    path.write_text(json.dumps(refreshed, indent=2) + "\n")
    path.with_suffix(".md").write_text(render_report(aggregate, model=old["model"]))


def main() -> None:
    count = 0
    for item in evidence_cases():
        directory = ROOT / item["path"]
        contracts = load_contracts(directory)
        for path in sorted((directory / "results").glob("eval_*.json")):
            rescore(path, contracts)
            count += 1
    print(f"re-scored {count} committed evidence-service result files")


if __name__ == "__main__":
    main()
