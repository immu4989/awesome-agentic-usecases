#!/usr/bin/env python3
"""Build source-bound public examples and contracts for the local Receipt Lab."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "receipt-lab" / "samples.json"
CATALOG_PATH = ROOT / "docs" / "use-cases.json"
RELIABILITY_PATH = ROOT / "docs" / "reliability-data.json"
OUTPUT_PATH = ROOT / "docs" / "receipt-lab-data.json"
ARTWORK_PATH = ROOT / "docs" / "assets" / "receipt-lab.svg"

HARD_CHECKS = [
    ("parse", "JSON parses as one object"),
    ("envelope", "Required evaluation envelope is present"),
    ("coverage", "Scenario and repeat counts are positive integers"),
    ("trial-count", "Trial count equals scenarios × repeats"),
    ("scenario-grid", "Declared scenario identities are complete"),
    ("repeat-grid", "Every scenario has the declared repeat set"),
    ("row-shape", "Every trial exposes metrics, cost, latency, and call count"),
    ("finite-values", "Trial metrics and operational values are finite"),
    ("metric-aggregation", "Published metric means recompute from trials"),
    ("cost-aggregation", "Published total cost recomputes from trials"),
]

DISCLOSURE_CHECKS = [
    ("metric-coverage", "Every non-error trial exposes every published metric"),
    ("interval-keys", "Confidence-interval keys match published metric keys"),
    ("interval-bounds", "Every declared interval is finite and contains its mean"),
    ("mean-cost", "Mean per-trial cost reconciles within declared precision"),
    ("median-latency", "Median latency reconciles within declared precision"),
    ("provider-errors", "Provider-error trials are counted and remain visible"),
    ("provenance", "Provider, requested/served model, and pinning are disclosed"),
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def error_value(row: dict[str, Any]) -> str | None:
    detail = row.get("detail")
    if isinstance(detail, dict) and detail.get("error"):
        return str(detail["error"])
    return None


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    optional = {key: result[key] for key in ("arm", "variant", "scoring_revision") if key in result}
    return {
        "backend": result["backend"],
        "model": result["model"],
        **optional,
        "provenance": result.get("provenance"),
        "n_scenarios": result["n_scenarios"],
        "n_repeats": result["n_repeats"],
        "metric_means": result["metric_means"],
        "metric_ci95": result["metric_ci95"],
        "mean_cost_per_scenario_usd": result["mean_cost_per_scenario_usd"],
        "total_cost_usd": result["total_cost_usd"],
        "p50_latency_s": result["p50_latency_s"],
        "results": [
            {
                "scenario_id": row["scenario_id"],
                "repeat": row["repeat"],
                "metrics": row["metrics"],
                "cost_usd": row["cost_usd"],
                "latency_s": row["latency_s"],
                "n_api_calls": row["n_api_calls"],
                "error": error_value(row),
                "archetype": row.get("detail", {}).get("archetype") if isinstance(row.get("detail"), dict) else None,
            }
            for row in result["results"]
        ],
    }


def make_artwork(stats: dict[str, int]) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="800" viewBox="0 0 1600 800" role="img" aria-labelledby="title desc">
  <title id="title">AAU Receipt Lab — inspect what an evaluation result actually proves</title>
  <desc id="desc">A local-first evidence inspector with {stats["hard_checks"]} hard integrity checks, {stats["disclosure_checks"]} disclosure checks, source binding, and zero file uploads.</desc>
  <defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#070b10"/><stop offset=".58" stop-color="#111923"/><stop offset="1" stop-color="#090c12"/></linearGradient><pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="#75e6ff" stroke-opacity=".055"/></pattern><radialGradient id="glow"><stop stop-color="#b69cff" stop-opacity=".22"/><stop offset="1" stop-color="#b69cff" stop-opacity="0"/></radialGradient></defs>
  <rect width="1600" height="800" fill="url(#bg)"/><rect width="1600" height="800" fill="url(#grid)"/><circle cx="1490" cy="30" r="450" fill="url(#glow)"/>
  <rect x="27" y="27" width="1546" height="746" fill="none" stroke="#46545e"/><path d="M27 82H1573M935 82V773" stroke="#46545e"/>
  <text x="66" y="63" class="micro cyan">AWESOME AGENTIC USE CASES / FIELD TOOL 04 / LOCAL-FIRST</text><text x="1525" y="63" class="micro" text-anchor="end">NO ACCOUNT · NO MODEL CALL · NO FILE UPLOAD</text>
  <text x="68" y="184" class="headline">BRING THE RECEIPT.</text><text x="68" y="264" class="headline italic">SEE WHAT IT PROVES.</text>
  <text x="70" y="316" class="deck">RECOMPUTE COUNTS · METRICS · COST · LATENCY · PROVENANCE</text>
  <g transform="translate(70 377)"><rect width="790" height="230" fill="#0b1117" stroke="#46545e"/><text x="28" y="38" class="micro">EVALUATION RECEIPT / SOURCE BINDING DECLARED</text>
    <g transform="translate(28 65)"><rect width="222" height="112" fill="#10171e" stroke="#3f4d56"/><text x="20" y="31" class="micro">TRIAL GRID</text><text x="20" y="79" class="value cyan">24 / 24</text><text x="20" y="101" class="tiny">8 SCENARIOS × 3 REPEATS</text></g>
    <g transform="translate(270 65)"><rect width="222" height="112" fill="#10171e" stroke="#3f4d56"/><text x="20" y="31" class="micro">EXACT</text><text x="20" y="79" class="value yellow">70.8%</text><text x="20" y="101" class="tiny">NOT COMPLETION</text></g>
    <g transform="translate(512 65)"><rect width="222" height="112" fill="#10171e" stroke="#3f4d56"/><text x="20" y="31" class="micro">PROVENANCE</text><text x="20" y="79" class="value violet">OPEN</text><text x="20" y="101" class="tiny">FLOATING MODEL ALIAS</text></g>
    <text x="28" y="207" class="micro cyan">STRUCTURALLY COHERENT ≠ DOMAIN VALIDATED ≠ REPRODUCED</text>
  </g>
  <text x="70" y="681" class="metric">{stats["hard_checks"]}</text><text x="151" y="660" class="micro">HARD</text><text x="151" y="683" class="micro">INTEGRITY CHECKS</text><text x="387" y="681" class="metric">{stats["disclosure_checks"]}</text><text x="448" y="660" class="micro">DISCLOSURE</text><text x="448" y="683" class="micro">CHECKS</text><text x="710" y="681" class="metric">0</text><text x="765" y="660" class="micro">LOCAL FILES</text><text x="765" y="683" class="micro">UPLOADED</text>
  <g transform="translate(982 130)"><text class="section" y="0">AN HONEST EVIDENCE LADDER</text>
    <g transform="translate(0 55)"><rect width="520" height="86" fill="#10171e" stroke="#43525b"/><rect width="9" height="86" fill="#ff6f91"/><text x="31" y="35" class="label">01 / INTEGRITY GAPS</text><text x="31" y="61" class="aside">Counts or aggregates do not reconcile.</text></g>
    <g transform="translate(0 159)"><rect width="520" height="86" fill="#10171e" stroke="#43525b"/><rect width="9" height="86" fill="#ffdc67"/><text x="31" y="35" class="label">02 / STRUCTURALLY COHERENT</text><text x="31" y="61" class="aside">The local artifact passes hard checks.</text></g>
    <g transform="translate(0 263)"><rect width="520" height="86" fill="#10171e" stroke="#43525b"/><rect width="9" height="86" fill="#75e6ff"/><text x="31" y="35" class="label">03 / SOURCE-BOUND EXAMPLE</text><text x="31" y="61" class="aside">The committed source and hash are known.</text></g>
    <g transform="translate(0 367)"><rect width="520" height="86" fill="#10171e" stroke="#43525b"/><rect width="9" height="86" fill="#b69cff"/><text x="31" y="35" class="label">04 / INDEPENDENTLY REPRODUCED</text><text x="31" y="61" class="aside">Requires a separate run and receipt.</text></g>
    <rect y="489" width="520" height="84" fill="#75e6ff"/><text x="34" y="541" class="cta">INSPECT AN EVAL_*.JSON LOCALLY →</text>
  </g>
  <style>text{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;fill:#f4f2eb}}.micro{{font:800 12px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:1.45px;fill:#9eabb4}}.cyan{{fill:#75e6ff}}.headline{{font-size:68px;font-weight:950;letter-spacing:-4px}}.italic{{font-family:Georgia,serif;font-size:70px;font-style:italic;font-weight:400;fill:#b69cff}}.deck{{font:800 14px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:1.5px;fill:#9eabb4}}.value{{font:950 34px ui-monospace,SFMono-Regular,Menlo,monospace}}.yellow{{fill:#ffdc67}}.violet{{fill:#b69cff}}.tiny{{font:750 9px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.9px;fill:#74828b}}.metric{{font:950 55px ui-monospace,SFMono-Regular,Menlo,monospace}}.section{{font-size:30px;font-weight:920;letter-spacing:-1.4px}}.label{{font:900 15px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.6px}}.aside{{font-size:14px;fill:#9eabb4}}.cta{{font:900 16px ui-monospace,SFMono-Regular,Menlo,monospace;fill:#080b10}}</style>
</svg>\n'''


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    catalog = {item["path"]: item for item in json.loads(CATALOG_PATH.read_text())}
    reliability = json.loads(RELIABILITY_PATH.read_text())
    if manifest["schema_version"] != "aau-receipt-lab-samples/1.0":
        raise SystemExit("unsupported Receipt Lab sample manifest")

    samples = []
    for declared in manifest["samples"]:
        source_path = ROOT / declared["source_path"]
        if not source_path.is_file():
            raise SystemExit(f"{declared['id']}: missing result {declared['source_path']}")
        if declared["lab_path"] not in catalog:
            raise SystemExit(f"{declared['id']}: lab is not cataloged")
        result = json.loads(source_path.read_text())
        if declared["primary_metric"] not in result["metric_means"]:
            raise SystemExit(f"{declared['id']}: primary metric is absent")
        samples.append(
            {
                **declared,
                "lab_title": catalog[declared["lab_path"]]["title"],
                "industry": catalog[declared["lab_path"]]["industry"],
                "source_sha256": digest(source_path),
                "result_url": f"https://github.com/immu4989/awesome-agentic-usecases/blob/main/{declared['source_path']}",
                "lab_url": f"https://github.com/immu4989/awesome-agentic-usecases/tree/main/{declared['lab_path']}",
                "result": compact_result(result),
            }
        )

    result_artifacts = len(list(ROOT.glob("*/*/results/eval_*.json")))
    stats = {
        "result_artifacts": result_artifacts,
        "samples": len(samples),
        "source_trials": sum(len(sample["result"]["results"]) for sample in samples),
        "hard_checks": len(HARD_CHECKS),
        "disclosure_checks": len(DISCLOSURE_CHECKS),
    }
    output = {
        "schema_version": "aau-receipt-lab/1.0",
        "status": "local_evidence_inspector",
        "privacy": "Selected JSON stays in this browser tab. Receipt Lab does not upload, persist, or transmit the file.",
        "stats": stats,
        "hard_checks": [{"id": item[0], "label": item[1]} for item in HARD_CHECKS],
        "disclosure_checks": [{"id": item[0], "label": item[1]} for item in DISCLOSURE_CHECKS],
        "dimensions": reliability["dimensions"],
        "samples": samples,
        "provenance": {
            "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
            "manifest_sha256": digest(MANIFEST_PATH),
            "catalog_sha256": digest(CATALOG_PATH),
            "reliability_sha256": digest(RELIABILITY_PATH),
        },
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2) + "\n")
    ARTWORK_PATH.write_text(make_artwork(stats))
    print(f"updated Receipt Lab with {stats['samples']} source-bound examples across {stats['source_trials']} trials")


if __name__ == "__main__":
    main()
