#!/usr/bin/env python3
"""Fail when a harness release tag and pyproject version disagree."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("harness-v"):
        print("usage: check_release_version.py harness-vX.Y.Z", file=sys.stderr)
        return 2
    tag_version = sys.argv[1].removeprefix("harness-v")
    package_version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    if tag_version != package_version:
        print(f"tag {tag_version} does not match package {package_version}", file=sys.stderr)
        return 1
    print(f"release version verified: {package_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
