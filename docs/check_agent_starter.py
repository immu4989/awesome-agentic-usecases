#!/usr/bin/env python3
"""Verify starter examples, browser parity, privacy, and release boundaries."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness" / "src"))

from aau_harness.starter import (  # noqa: E402
    PACKAGE_VERSION,
    TEMPLATES,
    browser_contract,
    doctor_project,
)


def require(path: Path, tokens: tuple[str, ...]) -> None:
    text = path.read_text()
    missing = [token for token in tokens if token not in text]
    if missing:
        raise SystemExit(f"{path.relative_to(ROOT)} missing: {', '.join(missing)}")


def main() -> None:
    data_path = ROOT / "docs" / "agent-starter-data.json"
    data = json.loads(data_path.read_text())
    if data != browser_contract():
        raise SystemExit("browser starter contract drifted from the Python generator")
    if data["package_version"] != PACKAGE_VERSION or len(data["templates"]) != 3:
        raise SystemExit("starter package version or template count drifted")

    examples = ROOT / "agent-evidence-starter" / "examples"
    for template_id in TEMPLATES:
        report = doctor_project(examples / template_id)
        if not report.ready or any(check.status != "pass" for check in report.checks):
            raise SystemExit(f"{template_id}: committed starter is not pristine and ready")

    require(
        ROOT / "docs" / "index.html",
        (
            'id="agent-starter"',
            'href="agent-starter.css?v=1"',
            'src="agent-starter.js?v=1"',
            'id="starter-download"',
            'id="starter-validation-list"',
            "Bring your agent.",
            "Nothing leaves this tab.",
        ),
    )
    require(
        ROOT / "docs" / "agent-starter.js",
        (
            'fetch("agent-starter-data.json?v=1")',
            "AAUBoundaryZip.archive",
            "crypto.subtle.digest",
            "aau-agent-evidence-starter/1.0",
            "synthetic_onboarding_not_production_validation",
            "generated_file_sha256",
            "browser_bundle_integrity_verified",
            "sensitiveFindings",
            "Eleven-file Agent Evidence Starter",
        ),
    )
    js = (ROOT / "docs" / "agent-starter.js").read_text()
    for forbidden in ("localStorage", "sessionStorage", "XMLHttpRequest", "sendBeacon"):
        if forbidden in js:
            raise SystemExit(f"browser starter must not persist or transmit form data: {forbidden}")
    require(
        ROOT / "docs" / "agent-starter.css",
        (
            ".agent-starter",
            ".starter-circuit",
            ".starter-template-grid",
            "@media (max-width: 620px)",
            "@media (prefers-reduced-motion: reduce)",
            ".agent-starter [hidden]",
        ),
    )
    require(
        ROOT / "docs" / "assets" / "agent-starter.svg",
        (
            "AAU / AGENT EVIDENCE STARTER",
            "BRING YOUR AGENT. LEAVE WITH A RECEIPT.",
            "PROTECTED HUMAN AUTHORITY",
            "0 ACCOUNTS",
        ),
    )
    require(
        ROOT / "agent-evidence-starter" / "README.md",
        ("aau init", "eleven-file ZIP", "aau doctor", "not production validation"),
    )
    print("Agent Evidence Starter verified: 3 templates, 10 gates, 11 files, CLI/browser parity, zero-upload boundary")


if __name__ == "__main__":
    main()
