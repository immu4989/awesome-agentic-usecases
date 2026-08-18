"""Build AAU Studio's evidence index from committed repository artifacts.

The browser experience never guesses which labs are runnable or verified. This generator
derives every proof badge, failure-pattern link, contract, and command from the catalog and
the files that CI already protects.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs" / "use-cases.json"
TAXONOMY = ROOT / "docs" / "assets" / "taxonomy.json"
OUTPUT = ROOT / "docs" / "studio-data.json"

CONTRACTS = (
    ("federal-assurance", "Federal Mission Assurance", "federal-mission-assurance/README.md"),
    ("rights-continuity", "Rights Continuity", "RIGHTS_CONTINUITY_CONTRACT.md"),
    ("critical-event", "Critical Event Fan-Out", "CRITICAL_EVENT_FANOUT_CONTRACT.md"),
    ("clock-collision", "Obligation Graph", "OBLIGATION_GRAPH_CONTRACT.md"),
    ("public-protection", "Protection Receipt", "PROTECTION_RECEIPT_CONTRACT.md"),
    ("proof-before-action", "Decision Gate", "DECISION_GATE_CONTRACT.md"),
    ("decision-gate", "Decision Gate", "DECISION_GATE_CONTRACT.md"),
    ("evidence-service", "Evidence Service", "EVIDENCE_SERVICE_CONTRACT.md"),
    ("public-value", "Public Value", "PUBLIC_VALUE_CONTRACT.md"),
)


def contract_for(item: dict) -> dict[str, str]:
    haystack = f"{item['kind']} {' '.join(item['capabilities'])}".lower()
    for needle, name, path in CONTRACTS:
        if needle in haystack:
            return {"name": name, "path": path}
    if "controlled" in haystack or "a/b" in haystack:
        return {"name": "Controlled Experiment", "path": "VERIFICATION.md"}
    return {"name": "Core Evaluation", "path": "VERIFICATION.md"}


def result_evidence(directory: Path) -> dict:
    real_results: list[dict] = []
    mock_results: list[dict] = []
    for path in sorted((directory / "results").glob("eval_*.json")):
        data = json.loads(path.read_text())
        # Some early controlled experiments intentionally committed partial provider
        # evidence. It remains real evidence and its failures are the point of the lab;
        # surface it in Studio rather than silently pretending the artifact does not exist.
        (mock_results if data.get("backend") == "mock" else real_results).append(data)

    models = sorted(
        {
            str(data.get("provenance", {}).get("served_model") or data.get("model"))
            for data in real_results
        }
    )
    scenario_runs = sum(
        int(data.get("n_scenarios", 0)) * int(data.get("n_repeats", 1))
        for data in real_results
    )
    scenario_count = max(
        (int(data.get("n_scenarios", 0)) for data in [*real_results, *mock_results]),
        default=0,
    )
    mock_supported = bool(mock_results) or any(
        "MockBackend" in path.read_text() or '"mock"' in path.read_text()
        for path in (directory / "src").glob("*/*.py")
    )
    return {
        "real_result_artifacts": len(real_results),
        "real_scenario_runs": scenario_runs,
        "models": models,
        "model_count": len(models),
        "mock_available": mock_supported,
        "scenario_count": scenario_count,
    }


def count_failure_modes(directory: Path) -> int:
    text = (directory / "FAILURE_MODES.md").read_text()
    return len(re.findall(r"^###\s+\d+\.", text, re.MULTILINE))


def source_grounded(readme: str) -> bool:
    return "## Primary-source grounding" in readme and "https://" in readme


def reproducible_scenarios(directory: Path) -> bool:
    if any(
        path.is_file()
        for path in (
            directory / "evals" / "scenarios.jsonl",
            directory / "scenarios.json",
            directory / "scenarios.jsonl",
        )
    ):
        return True
    # Controlled experiments reuse their local baseline's committed scenario generator.
    # A package dependency with a sibling repository directory is a checkable declaration
    # of that reuse; CI already regenerates the baseline scenarios for the matrix job.
    pyproject = (directory / "pyproject.toml").read_text()
    dependencies = re.findall(r'"([a-z0-9-]+)"', pyproject.split("dependencies", 1)[-1])
    projects = {
        re.search(r'^name = "([^"]+)"', path.read_text(), re.MULTILINE).group(1): path.parent
        for path in ROOT.glob("*/*/pyproject.toml")
        if re.search(r'^name = "([^"]+)"', path.read_text(), re.MULTILINE)
    }
    return any(
        dependency in projects and any((projects[dependency] / "evals").glob("scenarios.*"))
        for dependency in dependencies
    )


def main() -> None:
    cases = json.loads(CATALOG.read_text())
    taxonomy = json.loads(TAXONOMY.read_text())
    patterns = {item["id"]: item for item in taxonomy["index"]}
    patterns_by_case: dict[str, list[dict]] = {item["path"]: [] for item in cases}
    for pattern in patterns.values():
        for path in pattern["use_cases"]:
            if path in patterns_by_case:
                patterns_by_case[path].append(
                    {
                        "id": pattern["id"],
                        "name": pattern["name"],
                        "one_liner": pattern["one_liner"],
                    }
                )

    studio_cases = []
    for item in cases:
        directory = ROOT / item["path"]
        readme = (directory / "README.md").read_text()
        evidence = result_evidence(directory)
        capabilities = [capability.lower() for capability in item["capabilities"]]
        human_boundary = any("human" in capability for capability in capabilities) or any(
            phrase in readme.lower()
            for phrase in ("authority boundary", "the agent may never", "human-owned")
        )
        studio_cases.append(
            {
                "path": item["path"],
                "title": item["title"],
                "icon": item["icon"],
                "industry": item["industry"],
                "kind": item["kind"],
                "question": item["question"],
                "capabilities": item["capabilities"],
                "cli": item["cli"],
                "featured": bool(item.get("featured")),
                "contract": contract_for(item),
                "failure_patterns": sorted(
                    patterns_by_case[item["path"]], key=lambda pattern: pattern["name"]
                ),
                "evidence": {
                    **evidence,
                    "observed_failure_modes": count_failure_modes(directory),
                    "official_sources": source_grounded(readme),
                    "reproducible_scenarios": reproducible_scenarios(directory),
                    "human_boundary": human_boundary,
                },
                "commands": {
                    "discover": f"aau start {item['cli']}",
                    "install": f"python -m pip install -e harness -e {item['path']}",
                    "evaluate": f"{item['cli']} eval --backend mock --repeats 3",
                },
            }
        )

    output = {
        "version": "aau-studio/1.0",
        "proof": {
            "use_cases": len(cases),
            "industries": len({item["industry"] for item in cases}),
            "failure_patterns": taxonomy["patterns"],
            "failure_modes": taxonomy["failure_modes"],
        },
        "cases": studio_cases,
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n")
    print(
        "wrote studio-data.json — "
        f"{len(cases)} cases, {taxonomy['patterns']} patterns, "
        f"{sum(item['evidence']['real_result_artifacts'] for item in studio_cases)} real results"
    )


if __name__ == "__main__":
    main()
