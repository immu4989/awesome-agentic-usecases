#!/usr/bin/env python3
"""Verify the Receipt Lab's source bindings, privacy boundary, and public interface."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "receipt-lab-data.json"
MANIFEST_PATH = ROOT / "receipt-lab" / "samples.json"
HTML_PATH = ROOT / "docs" / "index.html"
JS_PATH = ROOT / "docs" / "receipt-lab.js"
CSS_PATH = ROOT / "docs" / "receipt-lab.css"
ART_PATH = ROOT / "docs" / "assets" / "receipt-lab.svg"
README_PATH = ROOT / "receipt-lab" / "README.md"

EXPECTED_HARD_CHECKS = {
    "parse",
    "envelope",
    "coverage",
    "trial-count",
    "scenario-grid",
    "repeat-grid",
    "row-shape",
    "finite-values",
    "metric-aggregation",
    "cost-aggregation",
}
EXPECTED_DISCLOSURES = {
    "metric-coverage",
    "interval-keys",
    "interval-bounds",
    "mean-cost",
    "median-latency",
    "provider-errors",
    "provenance",
}
REQUIRED_HTML_IDS = {
    "receipt-lab",
    "receipt-title",
    "receipt-file-input",
    "receipt-file-button",
    "receipt-drop",
    "receipt-paste",
    "receipt-inspect-paste",
    "receipt-samples",
    "receipt-dashboard",
    "receipt-status-title",
    "receipt-hard-list",
    "receipt-disclosure-list",
    "receipt-metrics",
    "receipt-worst",
    "receipt-provenance",
    "receipt-privacy",
    "receipt-download-json",
    "receipt-download-card",
    "receipt-copy-summary",
}


def fail(message: str) -> None:
    raise SystemExit(f"Receipt Lab check failed: {message}")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    for path in (DATA_PATH, MANIFEST_PATH, HTML_PATH, JS_PATH, CSS_PATH, ART_PATH, README_PATH):
        if not path.is_file():
            fail(f"missing {path.relative_to(ROOT)}")

    data = json.loads(DATA_PATH.read_text())
    manifest = json.loads(MANIFEST_PATH.read_text())
    if data.get("schema_version") != "aau-receipt-lab/1.0":
        fail("unexpected public-data schema")
    if manifest.get("schema_version") != "aau-receipt-lab-samples/1.0":
        fail("unexpected sample-manifest schema")

    hard_ids = {item["id"] for item in data.get("hard_checks", [])}
    disclosure_ids = {item["id"] for item in data.get("disclosure_checks", [])}
    if hard_ids != EXPECTED_HARD_CHECKS:
        fail(f"hard-check contract drifted: {sorted(hard_ids)}")
    if disclosure_ids != EXPECTED_DISCLOSURES:
        fail(f"disclosure contract drifted: {sorted(disclosure_ids)}")

    artifact_count = len(list(ROOT.glob("*/*/results/eval_*.json")))
    stats = data.get("stats", {})
    expected_stats = {
        "result_artifacts": artifact_count,
        "samples": len(manifest["samples"]),
        "source_trials": sum(len(sample["result"]["results"]) for sample in data["samples"]),
        "hard_checks": len(EXPECTED_HARD_CHECKS),
        "disclosure_checks": len(EXPECTED_DISCLOSURES),
    }
    if stats != expected_stats:
        fail(f"dynamic stats drifted: {stats!r} != {expected_stats!r}")

    declared = {item["id"]: item for item in manifest["samples"]}
    generated = {item["id"]: item for item in data["samples"]}
    if declared.keys() != generated.keys() or len(generated) != 3:
        fail("source-bound sample set drifted")

    for sample_id, sample in generated.items():
        source_path = ROOT / sample["source_path"]
        source = json.loads(source_path.read_text())
        compact = sample["result"]
        declaration = declared[sample_id]
        if sample["source_sha256"] != digest(source_path):
            fail(f"{sample_id}: source hash drifted")
        if sample["primary_metric"] not in compact["metric_means"]:
            fail(f"{sample_id}: primary metric is absent")
        if len(compact["results"]) != source["n_scenarios"] * source["n_repeats"]:
            fail(f"{sample_id}: compact trial grid is incomplete")
        if compact["metric_means"] != source["metric_means"] or compact["metric_ci95"] != source["metric_ci95"]:
            fail(f"{sample_id}: aggregate evidence differs from its source")
        if sample["lab_path"] != declaration["lab_path"]:
            fail(f"{sample_id}: lab binding drifted")
        for row in compact["results"]:
            if set(row) != {"scenario_id", "repeat", "metrics", "cost_usd", "latency_s", "n_api_calls", "error", "archetype"}:
                fail(f"{sample_id}: compact trial exposes an unexpected field")

    coherent = generated["coherent-current-receipt"]["result"]
    if not coherent.get("provenance") or coherent["provenance"].get("model_pinned") is not False:
        fail("current teaching receipt must disclose a floating model alias")
    older = generated["provenance-gap-receipt"]["result"]
    if older.get("provenance") is not None or not any(row["error"] for row in older["results"]):
        fail("older teaching receipt must retain its provenance gap and provider errors")
    interval = generated["interval-drift-receipt"]["result"]
    means = set(interval["metric_means"])
    intervals = set(interval["metric_ci95"])
    if means == intervals and all(
        interval["metric_ci95"][metric][0] <= interval["metric_means"][metric] <= interval["metric_ci95"][metric][1]
        for metric in means
    ):
        fail("interval-drift teaching receipt no longer contains its declared finding")

    if data["provenance"].get("manifest_sha256") != digest(MANIFEST_PATH):
        fail("manifest provenance hash drifted")
    if "does not upload, persist, or transmit" not in data.get("privacy", ""):
        fail("public data does not state the local privacy boundary")

    html = HTML_PATH.read_text()
    for element_id in REQUIRED_HTML_IDS:
        if f'id="{element_id}"' not in html:
            fail(f"landing page is missing #{element_id}")
    for asset in ("receipt-lab.css?v=1", "receipt-lab.js?v=1", "receipt-lab-data.json"):
        if asset == "receipt-lab-data.json":
            continue
        if asset not in html:
            fail(f"landing page is missing {asset}")
    if "Nothing leaves this tab" not in html and "NOTHING LEAVES THIS TAB" not in html:
        fail("landing page is missing the local-first promise")

    js = JS_PATH.read_text()
    for token in (
        'const MAX_FILE_BYTES = 12 * 1024 * 1024',
        'crypto.subtle.digest("SHA-256"',
        'aau-reproduction-receipt/1.0',
        "raw_values_included: false",
        "Aggregate exports are locked until the source is redacted",
        "publicProvenance",
        "Structural coherence is not domain validation",
        "No universal score is calculated",
        "metric_ci95",
        "providerErrors",
        "normalizedError",
        "scanPrivacy",
    ):
        if token not in js:
            fail(f"browser inspector is missing contract token {token!r}")
    for forbidden in ("localStorage", "sessionStorage", "XMLHttpRequest", "sendBeacon", "fetch(file", "result.detail", "row.detail?."):
        if forbidden in js:
            fail(f"browser inspector contains forbidden persistence or raw-detail token {forbidden!r}")

    css = CSS_PATH.read_text()
    for token in ("@media (max-width: 560px)", "@media (prefers-reduced-motion: reduce)", ".receipt-lab [hidden]", "overflow-x: auto"):
        if token not in css:
            fail(f"responsive visual system is missing {token!r}")

    artwork = ART_PATH.read_text()
    for token in ("BRING THE RECEIPT.", "SEE WHAT IT PROVES.", "AN HONEST EVIDENCE LADDER", "NO FILE UPLOAD"):
        if token not in artwork:
            fail(f"launch artwork is missing {token!r}")

    readme = README_PATH.read_text()
    for token in ("Structurally coherent", "independently reproduced", "aggregate-only", "make_receipt_lab_data.py"):
        if token not in readme:
            fail(f"Receipt Lab documentation is missing {token!r}")

    print(
        "Receipt Lab verified: "
        f"{artifact_count} artifacts, {len(generated)} source-bound examples, "
        f"{len(EXPECTED_HARD_CHECKS)} hard checks, {len(EXPECTED_DISCLOSURES)} disclosures"
    )


if __name__ == "__main__":
    main()
