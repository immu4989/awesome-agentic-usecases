#!/usr/bin/env python3
"""Verify canonical contracts and the browser-local Portfolio Observatory."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
OBSERVATORY = ROOT / "federal-portfolio-observatory"
DOCS = ROOT / "docs"


def fail(message: str) -> None:
    raise SystemExit(f"Federal Portfolio Observatory check failed: {message}")


def main() -> None:
    spec = importlib.util.spec_from_file_location(
        "aau_portfolio", OBSERVATORY / "aau_portfolio.py"
    )
    if not spec or not spec.loader:
        fail("cannot load the portfolio validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = json.loads((DOCS / "federal-portfolio-data.json").read_text())
    inventory = json.loads((OBSERVATORY / "examples/synthetic-agency-inventory.json").read_text())
    ledger = json.loads((OBSERVATORY / "examples/public-value-ledger.json").read_text())
    tevv = json.loads((OBSERVATORY / "examples/three-layer-tev-v-plan.json").read_text())
    clauses = json.loads((OBSERVATORY / "examples/clause-testbench.json").read_text())
    sources = json.loads((OBSERVATORY / "sources.json").read_text())
    catalog = json.loads((DOCS / "use-cases.json").read_text())
    canonical = {
        "inventory": inventory,
        "analysis": module.analyze_inventory(inventory, catalog),
        "public_value": {"ledger": ledger, "assessment": module.assess_public_value(ledger, inventory)},
        "tev_v": {"plan": tevv, "coverage": module.tevv_coverage(tevv, inventory)},
        "clauses": {"library": clauses, "coverage": module.clause_coverage(clauses)},
        "sources": sources,
    }
    for key, value in canonical.items():
        if data[key] != value:
            fail(f"browser {key} differs from the canonical contract")
    summary = data["analysis"]["summary"]
    expected = {
        "use_cases": 6,
        "documented": 4,
        "needs_evidence": 2,
        "critical_gaps": 5,
        "important_gaps": 2,
        "possible_overlaps": 1,
    }
    for key, value in expected.items():
        if summary[key] != value:
            fail(f"expected {key}={value}, got {summary[key]}")
    if data["privacy_scan"]["finding_count"]:
        fail("public examples contain a narrow scan finding")
    if data["tev_v"]["coverage"]["three_layer_complete"] is not True:
        fail("the reference plan must cover all three TEV&V layers")
    if data["clauses"]["coverage"]["areas"] != 7:
        fail("the testbench must cover seven acquisition areas")
    allowed = {"www.gao.gov", "www.nist.gov", "www.whitehouse.gov", "www.performance.gov"}
    for source in sources["sources"]:
        if urlparse(source["url"]).hostname not in allowed:
            fail(f"source is outside the official-domain allowlist: {source['url']}")

    schema_map = {
        "inventory.schema.json": "federal-ai-portfolio.schema.json",
        "public-value-ledger.schema.json": "public-value-ledger.schema.json",
        "three-layer-tev-v.schema.json": "three-layer-tev-v.schema.json",
        "clause-testbench.schema.json": "clause-testbench.schema.json",
    }
    for source_name, published_name in schema_map.items():
        if (OBSERVATORY / source_name).read_text() != (DOCS / published_name).read_text():
            fail(f"published schema is stale: {published_name}")

    html = (DOCS / "index.html").read_text()
    css = (DOCS / "federal-portfolio.css").read_text()
    js = (DOCS / "federal-portfolio.js").read_text()
    for token in (
        'id="portfolio-observatory"', 'id="portfolio-case-list"',
        'id="portfolio-local-file"', 'id="portfolio-download"',
        'id="portfolio-value-records"', 'id="portfolio-tev-v-layers"',
        'id="portfolio-clause-list"', 'id="portfolio-source-list"',
        "Files stay in this browser tab",
    ):
        if token not in html:
            fail(f"public interface is missing {token}")
    for token in (
        "federal-portfolio-data.json", "analyzeLocalInventory", "URL.createObjectURL",
        "possible_overlap", "investment: \"not-produced\"",
    ):
        if token not in js:
            fail(f"browser implementation is missing {token}")
    if "innerHTML" in js or "insertAdjacentHTML" in js:
        fail("uploaded values must only be rendered as text")
    if "localStorage" in js or "sessionStorage" in js:
        fail("inventory contents must not persist")
    if js.count("fetch(") != 1 or "http://" in js or "https://" in js:
        fail("the Observatory must use exactly one local fetch and no remote endpoint")
    if "@media (prefers-reduced-motion: reduce)" not in css:
        fail("the Observatory needs a reduced-motion mode")
    asset = (DOCS / "assets/federal-portfolio.svg").read_text()
    for value in (6, 4, 5, 1):
        if f">{value}</text>" not in asset:
            fail(f"generated visual is stale: missing {value}")
    print("Federal Portfolio Observatory verified: 6 entries, 5 critical gaps, 3 TEV&V layers, 7 clause areas")


if __name__ == "__main__":
    main()
