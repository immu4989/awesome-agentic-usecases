#!/usr/bin/env python3
"""Regenerate the three committed Agent Evidence Starter examples."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness" / "src"))

from aau_harness.starter import TEMPLATES, build_files, resolve_config, write_files  # noqa: E402


def main() -> None:
    examples = ROOT / "agent-evidence-starter" / "examples"
    for template_id in TEMPLATES:
        target = examples / template_id
        target.mkdir(parents=True, exist_ok=True)
        write_files(target, build_files(resolve_config(template_id, template_id)))
        print(f"generated {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
