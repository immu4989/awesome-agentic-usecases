#!/usr/bin/env python3
"""Build the public Boundary Builder contract library from repository evidence."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "boundary-builder" / "contracts.json"
BOUNDARIES = ROOT / "docs" / "boundary-data.json"
CATALOG = ROOT / "docs" / "use-cases.json"
OUTPUT = ROOT / "docs" / "boundary-builder-data.json"
ARTWORK = ROOT / "docs" / "assets" / "boundary-builder.svg"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def build_example(boundary_data: dict[str, Any]) -> dict[str, Any]:
    pair = next(pair for pair in boundary_data["pairs"] if pair["id"] == "one-tag-stops-restoration")
    return {
        "origin": "source-derived-worked-example",
        "source_boundary_id": pair["id"],
        "industry": pair["industry"],
        "title": "Distribution restoration protective-tag boundary",
        "description": (
            "Prepare a restoration evidence packet while keeping the protected "
            "re-energization decision with the accountable system operator."
        ),
        "contract_id": "decision-gate",
        "authority_owner": "Accountable system operator",
        "protected_action": "Final authorization to re-energize distribution equipment",
        "domain_reviewer": "Qualified utility operations and electrical-safety reviewer",
        "boundary_label": pair["boundary"]["label"],
        "before": pair["boundary"]["before"],
        "after": pair["boundary"]["after"],
        "baseline_review": pair["expected_reviews"]["baseline"],
        "changed_review": pair["expected_reviews"]["changed"],
        "why": pair["why"],
        "stake": pair["stake"],
        "baseline_evidence": pair["baseline"]["evidence"]["held"],
        "changed_evidence": pair["changed"]["evidence"]["held"],
        "changed_missing": pair["changed"]["evidence"]["missing"],
        "source_one": pair["sources"][0]["url"],
        "source_two": pair["sources"][1]["url"],
    }


def make_artwork(data: dict[str, Any]) -> str:
    contracts = data["contracts"]
    cards = []
    for index, contract in enumerate(contracts):
        column = index % 3
        row = index // 3
        x = 710 + column * 274
        y = 304 + row * 122
        accent = ("#ffde59", "#6df5d2", "#ff7ac8")[column]
        cards.append(
            f'<g transform="translate({x} {y})">'
            f'<rect width="250" height="96" rx="5" fill="#111519" stroke="#37434a"/>'
            f'<rect width="7" height="96" fill="{accent}"/>'
            f'<text x="25" y="28" class="micro">TEMPLATE {index + 1:02}</text>'
            f'<text x="25" y="59" class="contract">{html.escape(contract["name"])}</text>'
            f'<text x="25" y="80" class="mode">{html.escape(contract["forge_mode"])}</text>'
            '</g>'
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="800" viewBox="0 0 1600 800" role="img" aria-labelledby="title desc">
  <title id="title">AAU Boundary Builder — bring a workflow, leave with a fork</title>
  <desc id="desc">A local-first builder with {len(contracts)} contract templates, twelve validation gates, live counterfactual preview, and an eight-file contribution bundle.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#090b11"/><stop offset=".55" stop-color="#111821"/><stop offset="1" stop-color="#0a0c12"/></linearGradient>
    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="#6df5d2" stroke-opacity=".055"/></pattern>
    <radialGradient id="glow"><stop stop-color="#ff7ac8" stop-opacity=".2"/><stop offset="1" stop-color="#ff7ac8" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="1600" height="800" fill="url(#bg)"/><rect width="1600" height="800" fill="url(#grid)"/><circle cx="1500" cy="30" r="430" fill="url(#glow)"/>
  <rect x="27" y="27" width="1546" height="746" fill="none" stroke="#44525b"/><path d="M27 80H1573" stroke="#44525b"/>
  <text x="66" y="62" class="micro mint">AWESOME AGENTIC USE CASES / FIELD TOOL 03 / LOCAL-FIRST</text>
  <text x="1524" y="62" class="micro" text-anchor="end">NO ACCOUNT · NO KEY · NO UPLOAD</text>
  <text x="68" y="187" class="headline">BRING A WORKFLOW.</text>
  <text x="68" y="267" class="headline italic">LEAVE WITH A FORK.</text>
  <text x="70" y="316" class="deck">DEFINE Δ · PROTECT AUTHORITY · VALIDATE · EXPORT</text>
  <g transform="translate(70 385)">
    <rect width="520" height="190" fill="#0c1117" stroke="#4b5962"/>
    <text x="27" y="38" class="micro">YOUR DECLARED SEMANTIC BOUNDARY</text>
    <text x="27" y="86" class="card">BEFORE</text><text x="264" y="86" class="delta">Δ</text><text x="366" y="86" class="card">AFTER</text>
    <path d="M27 108H493" stroke="#37434a"/>
    <text x="27" y="153" class="result yellow">TRUST</text><text x="215" y="153" class="arrow">→</text><text x="366" y="153" class="result pink">BLOCK</text>
  </g>
  <text x="70" y="646" class="metric">12</text><text x="155" y="625" class="micro">LOCAL</text><text x="155" y="648" class="micro">VALIDATION GATES</text>
  <text x="372" y="646" class="metric">8</text><text x="430" y="625" class="micro">FILES IN THE</text><text x="430" y="648" class="micro">CONTRIBUTION ZIP</text>
  <path d="M660 112V716" stroke="#44525b"/>
  <text x="710" y="166" class="section">CHOOSE THE EVALUATION SHAPE</text>
  <text x="710" y="205" class="aside">The builder inherits structure—not domain truth.</text>
  {''.join(cards)}
  <rect x="710" y="584" width="798" height="72" fill="#ffde59"/><text x="746" y="629" class="cta">DOWNLOAD THE 8-FILE DRAFT BUNDLE →</text>
  <text x="710" y="701" class="micro mint">DRAFT → FORGE → DOMAIN REVIEW → REPEATED EVIDENCE → VERIFIED</text>
  <style>
    text{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;fill:#f5f3ea}}
    .micro{{font:800 13px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:1.6px;fill:#9facb5}}.mint{{fill:#6df5d2}}
    .headline{{font-size:56px;font-weight:900;letter-spacing:-3px}}.italic{{font-family:Georgia,serif;font-size:58px;font-style:italic;font-weight:400;fill:#6df5d2}}
    .deck{{font:800 15px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:1.8px;fill:#9facb5}}
    .card{{font:900 22px ui-monospace,SFMono-Regular,Menlo,monospace;fill:#f5f3ea}}.delta{{font:900 40px ui-monospace,SFMono-Regular,Menlo,monospace;fill:#6df5d2}}
    .result{{font:900 36px ui-monospace,SFMono-Regular,Menlo,monospace}}.yellow{{fill:#ffde59}}.pink{{fill:#ff7ac8}}.arrow{{font-size:35px;fill:#9facb5}}
    .metric{{font:900 61px ui-monospace,SFMono-Regular,Menlo,monospace}}.section{{font-size:34px;font-weight:900;letter-spacing:-1.5px}}.aside{{font-size:17px;fill:#9facb5}}
    .contract{{font-size:17px;font-weight:850}}.mode{{font:750 10px ui-monospace,SFMono-Regular,Menlo,monospace;fill:#9facb5;text-transform:uppercase}}
    .cta{{font:900 19px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:1px;fill:#090b11}}
  </style>
</svg>\n'''


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    boundary_data = json.loads(BOUNDARIES.read_text())
    catalog = {item["path"]: item for item in json.loads(CATALOG.read_text())}
    contracts = manifest["contracts"]
    if manifest["schema_version"] != "aau-boundary-builder-contracts/1.0":
        raise ValueError("unsupported Boundary Builder contract manifest")
    for contract in contracts:
        source = ROOT / contract["source_document"]
        if not source.is_file():
            raise ValueError(f"{contract['id']}: missing source document {contract['source_document']}")
        case = contract["recommended_case"]
        if case["path"] not in catalog:
            raise ValueError(f"{contract['id']}: recommended case is not cataloged")
        catalog_case = catalog[case["path"]]
        for field in ("title", "cli"):
            if case[field] != catalog_case[field]:
                raise ValueError(f"{contract['id']}: recommended case {field} drifted")
        contract["source_sha256"] = digest(source)
        contract["source_url"] = (
            "https://github.com/immu4989/awesome-agentic-usecases/blob/main/"
            f"{contract['source_document']}"
        )
    output = {
        "schema_version": "aau-boundary-builder/1.0",
        "status": "draft_infrastructure_only",
        "privacy": "Drafts stay in this browser. No form value, source, or answer is uploaded.",
        "contract_count": len(contracts),
        "validation_gate_count": 12,
        "bundle_file_count": 8,
        "contracts": contracts,
        "worked_example": build_example(boundary_data),
        "provenance": {
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "manifest_sha256": digest(MANIFEST),
            "boundary_data_sha256": digest(BOUNDARIES),
            "catalog_sha256": digest(CATALOG),
        },
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n")
    ARTWORK.write_text(make_artwork(output))
    print(f"updated Boundary Builder with {len(contracts)} contract templates and a source-derived example")


if __name__ == "__main__":
    main()
