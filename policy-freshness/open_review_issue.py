"""Open one consolidated GitHub issue when a freshness report needs review."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

TITLE = "[Policy freshness] Official source review required"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("body", type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    if report["summary"]["human_review_required_count"] == 0:
        print("No policy-source review issue required.")
        return 0
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not repository:
        print("GITHUB_REPOSITORY is required", file=sys.stderr)
        return 2
    listed = subprocess.run(
        ["gh", "issue", "list", "--repo", repository, "--state", "open", "--search", f'"{TITLE}" in:title', "--json", "title"],
        check=True,
        capture_output=True,
        text=True,
    )
    if any(item.get("title") == TITLE for item in json.loads(listed.stdout)):
        print("An open policy-source review issue already exists.")
        return 0
    subprocess.run(
        ["gh", "issue", "create", "--repo", repository, "--title", TITLE, "--body-file", str(args.body)],
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
