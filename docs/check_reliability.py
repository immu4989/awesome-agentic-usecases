"""Fail CI when the reliability report, data, or public workbench drifts."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    payload = json.loads((ROOT / "docs" / "reliability-data.json").read_text())
    evaluations = payload["evaluations"]
    stats = payload["stats"]
    html = (ROOT / "docs" / "index.html").read_text()
    script = (ROOT / "docs" / "explorer.js").read_text()
    report = (ROOT / "STATE_OF_AGENT_RELIABILITY_2026.md").read_text()

    assert payload["version"] == "aau-reliability-report/1.0"
    assert not payload["methodology"]["universal_score"]
    assert stats["evaluations"] == len(evaluations)
    assert stats["labs"] == len({item["lab_path"] for item in evaluations})
    assert stats["models"] == len({item["model"] for item in evaluations})
    assert stats["scenario_trials"] == sum(item["scenario_trials"] for item in evaluations)
    assert stats["recorded_spend_usd"] == round(
        sum(item["total_cost_usd"] for item in evaluations), 6
    )
    assert all((ROOT / item["result_path"]).is_file() for item in evaluations)
    assert all(item["result_url"].endswith(item["result_path"]) for item in evaluations)
    assert sum(item["dimensions"]["exact"] is not None for item in evaluations) == stats[
        "exact_endpoint_coverage"
    ]
    assert payload["failure_patterns"]

    with (ROOT / "docs" / "reliability-data.csv").open(newline="") as handle:
        assert sum(1 for _row in csv.DictReader(handle)) == len(evaluations)

    for element_id in (
        "reliability",
        "reliability-chart",
        "reliability-metric",
        "reliability-model",
        "reliability-industry",
        "reliability-contract",
        "reliability-models",
        "reliability-patterns",
    ):
        assert f'id="{element_id}"' in html, f"reliability workbench is missing #{element_id}"
    for behavior in (
        "loadReliability",
        "renderReliabilityChart",
        "renderReliabilityModels",
        "renderReliabilityPatterns",
        "syncReliabilityUrl",
    ):
        assert behavior in script, f"reliability script is missing {behavior}"
    assert "No universal reliability score" in html
    assert "reliability-data.csv" in html and "reliability-data.json" in html
    assert "social-card-reliability-2026.png" in html
    assert (ROOT / "docs" / "assets" / "social-card-reliability-2026.png").is_file()
    assert f"**{stats['scenario_trials']:,}**" in report
    assert f"**{stats['failure_modes']}**" in report
    assert f"{stats['mean_completion_exact_gap_points']:.1f}" in report

    print(
        "reliability report integrity OK: "
        f"{stats['evaluations']} evals, {stats['scenario_trials']} trials, "
        f"{stats['failure_modes']} failures"
    )


if __name__ == "__main__":
    main()
