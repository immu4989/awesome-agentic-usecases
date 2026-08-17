#!/usr/bin/env python3
"""Build the public Boundary Lab dataset from committed scenario contracts."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "boundary-lab" / "pairs.json"
OUTPUT = ROOT / "docs" / "boundary-data.json"
ARTWORK = ROOT / "docs" / "assets" / "boundary-lab.svg"
REPO = "https://github.com/immu4989/awesome-agentic-usecases"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {row["scenario_id"]: row for row in rows}


def at_path(value: Any, dotted_path: str) -> Any:
    current = value
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"missing selector path: {dotted_path}")
        current = current[part]
    return current


def assert_condition(scenario: dict[str, Any], condition: dict[str, Any], pair_id: str) -> None:
    actual = at_path(scenario, condition["path"])
    expected = condition["value"]
    operator = condition["operator"]
    if operator == "equals":
        valid = actual == expected
    elif operator == "contains":
        valid = isinstance(actual, (list, str)) and expected in actual
    else:
        raise ValueError(f"{pair_id}: unsupported boundary operator {operator}")
    if not valid:
        raise ValueError(
            f"{pair_id}: {condition['path']} failed {operator}; "
            f"expected {expected!r}, found {actual!r}"
        )


def humanize(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(humanize(item) for item in value) if value else "none"
    return str(value).replace("_", " ")


def normalized_gate_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    record = scenario["record"]
    evidence = scenario["evidence_registry"]
    contract = scenario["gate_contract"]
    facts = [
        {"label": humanize(key), "value": humanize(value)}
        for key, value in record["domain_facts"].items()
    ]
    gates = [
        {"label": humanize(key), "state": value}
        for key, value in record["gate_states"].items()
    ]
    return {
        "scenario_id": scenario["scenario_id"],
        "case_id": scenario["case_id"],
        "case_text": scenario["case_text"],
        "archetype": scenario["archetype"],
        "facts": facts,
        "gates": gates,
        "evidence": {
            "required": evidence["required_evidence"],
            "held": evidence["held_evidence"],
            "missing": evidence["missing_evidence"],
        },
        "oracle": {
            "terminal": contract["expected_terminal"],
            "reason_code": contract["expected_reason_code"],
            "policy_version": scenario["policy_snapshot"]["version"],
            "source_note": scenario["policy_snapshot"]["source_note"],
        },
    }


def normalized_security_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    poisoned = bool(scenario["is_attack"])
    connector_copy = scenario["connector_desc"]
    if poisoned:
        connector_copy = connector_copy.replace(scenario["secret_resource_id"], "[internal-secret-resource]")
    return {
        "scenario_id": scenario["scenario_id"],
        "case_id": scenario["scenario_id"].upper(),
        "case_text": scenario["task_text"],
        "archetype": scenario["archetype"],
        "facts": [
            {"label": "user requests external send", "value": humanize(scenario["task_requires_send"])},
            {"label": "injection channel", "value": humanize(scenario["injection_channel"])},
            {"label": "connector description", "value": connector_copy},
        ],
        "gates": [
            {"label": "user-authorized secret access", "state": "failed" if poisoned else "satisfied"},
            {"label": "secret-bearing egress", "state": "failed" if poisoned else "satisfied"},
        ],
        "evidence": {
            "required": ["user_task", "connector_description", "egress_policy"],
            "held": ["user_task", "connector_description", "egress_policy"],
            "missing": [],
        },
        "oracle": {
            "terminal": "block_secret_bearing_connector_call" if poisoned else "connector_summary_allowed",
            "reason_code": "poisoned_tool_requests_secret" if poisoned else "clean_read_only_connector",
            "policy_version": "AAU-TRIFECTA-1.0",
            "source_note": "Synthetic adversarial benchmark. Secret values are never published in Boundary Lab data.",
        },
    }


def make_artwork(output: dict[str, Any]) -> str:
    pairs = output["pairs"]
    labels = []
    for index, pair in enumerate(pairs):
        column = index % 2
        row = index // 2
        x = 870 + column * 330
        y = 285 + row * 88
        accent = "#d9ff62" if index % 2 == 0 else "#ff5ccf"
        labels.append(
            f'<g transform="translate({x} {y})">'
            f'<rect width="302" height="66" rx="4" fill="#111619" stroke="#354037"/>'
            f'<rect width="6" height="66" fill="{accent}"/>'
            f'<text x="24" y="25" class="micro">BOUNDARY {index + 1:02}</text>'
            f'<text x="24" y="47" class="industry">{html.escape(pair["industry"])}</text>'
            '</g>'
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="800" viewBox="0 0 1600 800" role="img" aria-labelledby="title desc">
  <title id="title">AAU Boundary Lab — change one deciding fact</title>
  <desc id="desc">A source-locked counterfactual laboratory with {output["stats"]["pairs"]} verified boundaries across {output["stats"]["industries"]} industries and {output["stats"]["source_scenarios"]} committed source scenarios.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#080b0d"/><stop offset=".62" stop-color="#111619"/><stop offset="1" stop-color="#090c0f"/></linearGradient>
    <pattern id="grid" width="38" height="38" patternUnits="userSpaceOnUse"><path d="M38 0H0V38" fill="none" stroke="#d9ff62" stroke-opacity=".055"/></pattern>
    <radialGradient id="glow"><stop stop-color="#ff5ccf" stop-opacity=".18"/><stop offset="1" stop-color="#ff5ccf" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="1600" height="800" fill="url(#bg)"/><rect width="1600" height="800" fill="url(#grid)"/><circle cx="1450" cy="60" r="430" fill="url(#glow)"/>
  <rect x="26" y="26" width="1548" height="748" fill="none" stroke="#465148"/><path d="M26 76H1574" stroke="#465148"/>
  <text x="64" y="60" class="micro lime">AWESOME AGENTIC USE CASES / FIELD TEST 02 / SOURCE-LOCKED</text>
  <text x="1518" y="60" class="micro" text-anchor="end">ZERO INSTALL · $0 TO REPRODUCE</text>
  <text x="65" y="194" class="headline">CHANGE ONE FACT.</text>
  <text x="65" y="273" class="headline italic">WATCH THE CONTRACT MOVE.</text>
  <text x="68" y="321" class="deck">COUNTERFACTUAL PAIRS · HIDDEN ORACLES · PORTABLE REGRESSION TESTS</text>
  <g transform="translate(68 382)">
    <rect width="318" height="178" fill="#0c1113" stroke="#536053"/><text x="24" y="36" class="micro">BEFORE / SCENARIO A</text>
    <text x="24" y="82" class="card">FACT PRESENT</text><path d="M24 108H294" stroke="#354037"/><text x="24" y="144" class="result lime">TRUST</text>
  </g>
  <g transform="translate(494 382)">
    <rect width="318" height="178" fill="#0c1113" stroke="#536053"/><text x="24" y="36" class="micro">AFTER / SCENARIO B</text>
    <text x="24" y="82" class="card">FACT CHANGED</text><path d="M24 108H294" stroke="#354037"/><text x="24" y="144" class="result pink">BLOCK</text>
  </g>
  <circle cx="440" cy="471" r="39" fill="#d9ff62" stroke="#ff5ccf" stroke-width="4"/><text x="440" y="486" class="delta" text-anchor="middle">Δ</text>
  <text x="68" y="635" class="metric">{output["stats"]["pairs"]}</text><text x="132" y="620" class="micro">VERIFIED</text><text x="132" y="642" class="micro">BOUNDARIES</text>
  <text x="300" y="635" class="metric">{output["stats"]["industries"]}</text><text x="364" y="620" class="micro">PUBLIC-INTEREST</text><text x="364" y="642" class="micro">INDUSTRIES</text>
  <text x="594" y="635" class="metric">{output["stats"]["source_scenarios"]}</text><text x="684" y="620" class="micro">COMMITTED</text><text x="684" y="642" class="micro">SCENARIOS</text>
  <path d="M842 112V718" stroke="#465148"/><text x="870" y="160" class="section">THE BOUNDARY QUEUE</text><text x="870" y="201" class="aside">Review both sides. Reveal the oracle. Export the test.</text>
  {''.join(labels)}
  <rect x="870" y="658" width="632" height="60" fill="#d9ff62"/><text x="900" y="696" class="cta">FLIP THE FIRST DECIDING FACT →</text>
  <style>
    text{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;fill:#f7f4e8}}
    .micro{{font:800 13px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:1.5px;fill:#a7afa8}}
    .lime{{fill:#d9ff62}}.pink{{fill:#ff5ccf}}
    .headline{{font-size:68px;font-weight:900;letter-spacing:-4px}}.italic{{font-family:Georgia,serif;font-style:italic;font-weight:400;fill:#d9ff62}}
    .deck{{font:800 15px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:1.7px;fill:#a7afa8}}
    .card{{font-size:25px;font-weight:850}}.result{{font:900 36px ui-monospace,SFMono-Regular,Menlo,monospace}}
    .delta{{font:900 44px ui-monospace,SFMono-Regular,Menlo,monospace;fill:#090c0f}}.metric{{font:900 55px ui-monospace,SFMono-Regular,Menlo,monospace;fill:#f7f4e8}}
    .section{{font-size:35px;font-weight:900;letter-spacing:-1.5px}}.aside{{font-size:17px;fill:#a7afa8}}
    .industry{{font-size:14px;font-weight:780}}.cta{{font:900 18px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:1px;fill:#090c0f}}
  </style>
</svg>\n'''


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    if manifest["schema_version"] != "aau-boundary-manifest/1.0":
        raise ValueError("unsupported Boundary Lab manifest version")
    pairs = []
    for item in manifest["pairs"]:
        lab = ROOT / item["source_path"]
        scenario_path = lab / "evals" / "scenarios.jsonl"
        scenarios = load_jsonl(scenario_path)
        try:
            baseline_raw = scenarios[item["baseline_scenario_id"]]
            changed_raw = scenarios[item["changed_scenario_id"]]
        except KeyError as error:
            raise ValueError(f"{item['id']}: scenario not found: {error.args[0]}") from error
        assert_condition(baseline_raw, item["boundary"]["baseline_condition"], item["id"])
        assert_condition(changed_raw, item["boundary"]["changed_condition"], item["id"])
        adapter = item.get("adapter", "gate_contract")
        if adapter == "gate_contract":
            baseline = normalized_gate_scenario(baseline_raw)
            changed = normalized_gate_scenario(changed_raw)
        elif adapter == "security":
            baseline = normalized_security_scenario(baseline_raw)
            changed = normalized_security_scenario(changed_raw)
        else:
            raise ValueError(f"{item['id']}: unsupported adapter {adapter}")
        if baseline["oracle"]["terminal"] == changed["oracle"]["terminal"]:
            raise ValueError(f"{item['id']}: boundary must change the oracle terminal")
        reviews = item["expected_reviews"]
        if reviews["baseline"] == reviews["changed"]:
            raise ValueError(f"{item['id']}: boundary must change the reviewer action")
        pair = {
            key: item[key]
            for key in (
                "id", "order", "industry", "title", "contract", "presentation",
                "boundary", "expected_reviews", "why", "stake", "sources",
            )
        }
        pair.update(
            {
                "baseline": baseline,
                "changed": changed,
                "provenance": {
                    "scenario_path": str(scenario_path.relative_to(ROOT)),
                    "scenario_sha256": digest(scenario_path),
                    "manifest_sha256": digest(MANIFEST),
                },
                "links": {
                    "share": f"https://immu4989.github.io/awesome-agentic-usecases/?boundary={item['id']}#boundary-lab",
                    "lab": f"{REPO}/tree/main/{item['source_path']}",
                    "scenario": f"{REPO}/blob/main/{item['source_path']}/evals/scenarios.jsonl",
                    "fork": f"{REPO}/fork",
                    "codespace": f"https://codespaces.new/immu4989/awesome-agentic-usecases?quickstart=1",
                },
            }
        )
        pairs.append(pair)
    pairs.sort(key=lambda pair: pair["order"])
    industries = sorted({pair["industry"] for pair in pairs})
    contracts = sorted({pair["contract"] for pair in pairs})
    output = {
        "schema_version": "aau-boundary-lab/1.0",
        "generated_from": "boundary-lab/pairs.json + committed evals/scenarios.jsonl",
        "definition": "One deciding fact means one declared semantic boundary. Case identifiers, prose, evidence requirements, and derived contract fields may change as consequences of that boundary.",
        "privacy": "Answers stay in this browser. Downloads are generated locally. No identity, answer, or telemetry is sent.",
        "review_actions": {
            "trust": {"label": "Trust", "description": "Proceed under the shown contract"},
            "verify": {"label": "Verify", "description": "Hold and request the missing proof"},
            "block": {"label": "Block", "description": "Stop this path and route the exception"},
        },
        "stats": {
            "pairs": len(pairs),
            "industries": len(industries),
            "contracts": len(contracts),
            "source_scenarios": len(pairs) * 2,
        },
        "pairs": pairs,
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n")
    ARTWORK.write_text(make_artwork(output))
    print(f"updated Boundary Lab with {len(pairs)} verified pairs and source-derived artwork")


if __name__ == "__main__":
    main()
