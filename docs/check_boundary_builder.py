#!/usr/bin/env python3
"""Fail when Boundary Builder drifts from its sources or safe export contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "boundary-builder-data.json"
MANIFEST_PATH = ROOT / "boundary-builder" / "contracts.json"
BOUNDARY_PATH = ROOT / "docs" / "boundary-data.json"
CATALOG_PATH = ROOT / "docs" / "use-cases.json"
VALID_MODES = {"contract-aware", "generic-fallback"}
FORBIDDEN = ("sk-live", "int-db-creds", "secret_value", "github_pat_")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def require_text(path: Path, needles: tuple[str, ...]) -> None:
    text = path.read_text()
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path.relative_to(ROOT)} missing: {', '.join(missing)}")


def main() -> None:
    data = json.loads(DATA_PATH.read_text())
    manifest = json.loads(MANIFEST_PATH.read_text())
    boundary_data = json.loads(BOUNDARY_PATH.read_text())
    catalog = {item["path"]: item for item in json.loads(CATALOG_PATH.read_text())}

    if data["schema_version"] != "aau-boundary-builder/1.0":
        raise SystemExit("Boundary Builder public schema changed without a version update")
    if manifest["schema_version"] != "aau-boundary-builder-contracts/1.0":
        raise SystemExit("Boundary Builder manifest schema changed without a version update")
    if data["status"] != "draft_infrastructure_only":
        raise SystemExit("Boundary Builder must not imply that its exports are verified")
    if (data["contract_count"], data["validation_gate_count"], data["bundle_file_count"]) != (6, 12, 8):
        raise SystemExit("Boundary Builder v1 must retain six templates, twelve gates, and eight files")

    contracts = data["contracts"]
    if len(contracts) != len(manifest["contracts"]) or len({item["id"] for item in contracts}) != 6:
        raise SystemExit("Boundary Builder must expose six unique contract templates")
    mode_counts = {mode: sum(item["forge_mode"] == mode for item in contracts) for mode in VALID_MODES}
    if mode_counts != {"contract-aware": 3, "generic-fallback": 3}:
        raise SystemExit(f"unexpected Forge support split: {mode_counts}")

    for public, declared in zip(contracts, manifest["contracts"], strict=True):
        if public["id"] != declared["id"] or public["forge_mode"] not in VALID_MODES:
            raise SystemExit("Boundary Builder contract order or mode drifted")
        source = ROOT / public["source_document"]
        if not source.is_file() or public["source_sha256"] != digest(source):
            raise SystemExit(f"{public['id']}: source document or hash drifted")
        expected_url = (
            "https://github.com/immu4989/awesome-agentic-usecases/blob/main/"
            f"{public['source_document']}"
        )
        if public["source_url"] != expected_url:
            raise SystemExit(f"{public['id']}: source URL drifted")
        case = public["recommended_case"]
        if case["path"] not in catalog:
            raise SystemExit(f"{public['id']}: recommended case is not cataloged")
        if any(case[field] != catalog[case["path"]][field] for field in ("title", "cli")):
            raise SystemExit(f"{public['id']}: recommended case metadata drifted")

    if data["provenance"] != {
        "manifest": "boundary-builder/contracts.json",
        "manifest_sha256": digest(MANIFEST_PATH),
        "boundary_data_sha256": digest(BOUNDARY_PATH),
        "catalog_sha256": digest(CATALOG_PATH),
    }:
        raise SystemExit("Boundary Builder provenance hashes drifted")

    example = data["worked_example"]
    source_pair = next(item for item in boundary_data["pairs"] if item["id"] == "one-tag-stops-restoration")
    if example["origin"] != "source-derived-worked-example":
        raise SystemExit("worked example must declare its source-derived status")
    for field in ("boundary_label", "before", "after", "why", "stake"):
        source_field = "label" if field == "boundary_label" else field
        source_value = source_pair["boundary"][source_field] if field in {"boundary_label", "before", "after"} else source_pair[field]
        if example[field] != source_value:
            raise SystemExit(f"worked example {field} drifted from its source pair")
    if (example["baseline_review"], example["changed_review"]) != (
        source_pair["expected_reviews"]["baseline"],
        source_pair["expected_reviews"]["changed"],
    ):
        raise SystemExit("worked example reviewer actions drifted")
    if (example["source_one"], example["source_two"]) != tuple(source["url"] for source in source_pair["sources"][:2]):
        raise SystemExit("worked example source declarations drifted")

    serialized = DATA_PATH.read_text().lower()
    for token in FORBIDDEN:
        if token in serialized:
            raise SystemExit(f"Boundary Builder public data contains forbidden material: {token}")

    require_text(
        ROOT / "docs" / "index.html",
        (
            'id="boundary-builder"',
            'href="boundary-builder.css?v=1"',
            'src="boundary-builder-zip.js?v=1"',
            'src="boundary-builder.js?v=1"',
            'id="builder-load-example"',
            'id="builder-download-bundle"',
            'id="builder-privacy-scan"',
            'id="builder-validation-list"',
            "Bring a workflow.",
            "No form data leaves this page.",
        ),
    )
    require_text(
        ROOT / "docs" / "boundary-builder.js",
        (
            'fetch("boundary-builder-data.json?v=1")',
            "localStorage",
            "sensitiveFindings",
            'schema_version: "aau-boundary-draft/1.0"',
            'contract_version: "aau-studio/1.0"',
            'status: "adaptation_required"',
            "AAUBoundaryZip.archive",
            "Eight-file contribution ZIP generated locally",
            "issue intentionally omits scenario text, evidence, and source URLs",
            "window.confirm",
        ),
    )
    require_text(
        ROOT / "docs" / "boundary-builder-zip.js",
        ("crc32", "0x04034b50", "0x02014b50", "0x06054b50", "Uint8Array"),
    )
    require_text(
        ROOT / "docs" / "boundary-builder.css",
        (
            ".builder-workbench",
            ".builder-twin-inputs",
            "@media (max-width: 600px)",
            "@media (prefers-reduced-motion: reduce)",
            ".boundary-builder [hidden]",
        ),
    )
    require_text(
        ROOT / "docs" / "assets" / "boundary-builder.svg",
        ("AAU Boundary Builder", "BRING A WORKFLOW.", "VALIDATION GATES", "CONTRIBUTION ZIP", "Taint and Egress Gate"),
    )
    require_text(
        ROOT / "boundary-builder" / "README.md",
        ("Twelve local gates", "eight-file contribution ZIP", "python docs/make_boundary_builder_data.py", "adaptation_required"),
    )
    print("Boundary Builder integrity: 6 templates, 12 local gates, 8-file export, provenance, and privacy verified")


if __name__ == "__main__":
    main()
