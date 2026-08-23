#!/usr/bin/env python3
"""Generate the browser-local Agent Evidence Starter contract and launch artwork."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness" / "src"))

from aau_harness.starter import browser_contract, evidence_svg, resolve_config  # noqa: E402


def main() -> None:
    data = browser_contract()
    (ROOT / "docs" / "agent-starter-data.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n"
    )
    config = resolve_config(
        "agent-evidence-starter",
        "public-service-routing",
        title="Agent Evidence Starter",
    )
    (ROOT / "docs" / "assets" / "agent-starter.svg").write_text(evidence_svg(config))
    print(
        f"generated {len(data['templates'])} starter templates, "
        f"{data['validation_gate_count']} gates, and {data['bundle_file_count']} files"
    )


if __name__ == "__main__":
    main()
