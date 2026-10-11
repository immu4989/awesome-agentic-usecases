"""Reconcile one human-review issue without hiding new findings or closing human work."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from aau_freshness import (
    COMPATIBILITY_REPORT_VERSION, COMPATIBILITY_STATUS_ORDER, REPORT_VERSION, STATUS_ORDER,
    digest, issue_markdown,
)

TITLE = "[Policy freshness] Official source review required"
BEGIN = "<!-- aau-policy-freshness:begin -->"
END = "<!-- aau-policy-freshness:end -->"
MAX_BODY_BYTES = 60_000


def checked_report(value: dict, *, compatibility: bool = False) -> None:
    version = COMPATIBILITY_REPORT_VERSION if compatibility else REPORT_VERSION
    rows_key, count_key = ("bindings", "binding_count") if compatibility else ("sources", "source_count")
    statuses = COMPATIBILITY_STATUS_ORDER if compatibility else STATUS_ORDER
    good = "evidence_ready" if compatibility else "current"
    if not isinstance(value, dict) or value.get("report_version") != version:
        raise ValueError("unsupported freshness report")
    expected = digest({key: item for key, item in value.items() if key != "report_sha256"})
    if value.get("report_sha256") != expected:
        raise ValueError("freshness report hash does not recompute")
    rows, summary = value[rows_key], value["summary"]
    if not isinstance(rows, list) or any(not isinstance(row, dict) or row.get("status") not in statuses for row in rows):
        raise ValueError("invalid report status")
    counts = {f"{status}_count": sum(row["status"] == status for row in rows) for status in statuses}
    counts.update({count_key: len(rows), "human_review_required_count": sum(row["status"] != good for row in rows)})
    if summary != counts or any(type(number) is not int for number in summary.values()):
        raise ValueError("freshness report counts differ from its findings")


def snapshot(report: dict, compatibility: dict | None, body: str) -> tuple[str, str, bool]:
    checked_report(report)
    if compatibility is not None:
        checked_report(compatibility, compatibility=True)
        if any(report[key] != compatibility[key] for key in ("registry_id", "registry_sha256", "as_of")):
            raise ValueError("source and compatibility reports refer to different scans")
    if body != issue_markdown(report, compatibility):
        raise ValueError("issue text does not match the supplied reports")
    source_findings = []
    for row in report["sources"]:
        if row["status"] == "current":
            continue
        source_findings.append({
            **{key: row[key] for key in ("source_id", "title", "authority", "url", "owner_paths", "status", "error_code")},
            "baseline_sha256": row["baseline"]["content_sha256"],
            "observed_sha256": row["observed"]["content_sha256"] if row["observed"] else None,
        })
    bindings = [row for row in compatibility["bindings"] if row["status"] != "evidence_ready"] if compatibility else []
    signal = digest({"registry_sha256": report["registry_sha256"],
                     "compatibility_included": compatibility is not None,
                     "sources": sorted(source_findings, key=lambda row: row["source_id"]),
                     "bindings": sorted(bindings, key=lambda row: (row["profile_id"], row["source_id"]))})
    active = bool(source_findings or bindings)
    note = ("This is the latest changed machine finding, not a human disposition. Review earlier findings and owner notes before closing."
            if active else "The latest scan has no machine-flagged findings. This does not resolve earlier human review, approve a source baseline, or authorize closing this issue.")
    marker = f"<!-- aau-policy-freshness:signal:{signal} -->"
    block = f"{BEGIN}\n{marker}\n## Latest automated findings\n\nAs of: {report['as_of']}.\n\n{note}\n\n{body.rstrip()}\n{END}"
    return marker, block, active


def reconcile_body(existing: str | None, marker: str, block: str, active: bool) -> str | None:
    if existing is None:
        result = block + "\n" if active else None
    elif BEGIN not in existing and END not in existing:
        # Migrate legacy notices without deleting any original text or human notes.
        result = block + "\n\n## Earlier notice and owner notes (retained)\n\n" + existing
    else:
        if existing.count(BEGIN) != 1 or existing.count(END) != 1:
            raise ValueError("ambiguous managed issue markers; human repair required")
        start, stop = existing.index(BEGIN), existing.index(END)
        if stop < start:
            raise ValueError("reversed managed issue markers")
        if marker in existing[start:stop]:
            return None
        result = existing[:start] + block + existing[stop + len(END):]
    if result is not None and len(result.encode("utf-8")) > MAX_BODY_BYTES:
        raise ValueError("issue body too large; refusing to truncate human notes or findings")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("body", type=Path)
    parser.add_argument("compatibility_report", type=Path, nargs="?")
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text())
        compatibility = json.loads(args.compatibility_report.read_text()) if args.compatibility_report else None
        marker, block, active = snapshot(report, compatibility, args.body.read_text())
        repository = os.environ.get("GITHUB_REPOSITORY")
        if not repository:
            raise ValueError("GITHUB_REPOSITORY is required")
        listed = subprocess.run(
            ["gh", "issue", "list", "--repo", repository, "--state", "open", "--limit", "100",
             "--search", f'"{TITLE}" in:title', "--json", "number,title,body"],
            check=True, capture_output=True, text=True,
        )
        matches = [item for item in json.loads(listed.stdout) if item.get("title") == TITLE]
        if len(matches) > 1:
            raise ValueError("multiple review issues exist; human reconciliation required")
        issue = matches[0] if matches else None
        new_body = reconcile_body(issue["body"] if issue else None, marker, block, active)
        if new_body is None:
            print("No changed policy-source findings to publish.")
            return 0
        if issue:
            if type(issue["number"]) is not int or issue["number"] < 1:
                raise ValueError("invalid issue identity")
            current = subprocess.run(
                ["gh", "issue", "view", str(issue["number"]), "--repo", repository, "--json", "body,state,title"],
                check=True, capture_output=True, text=True,
            )
            current = json.loads(current.stdout)
            if current["body"] != issue["body"] or current["state"] != "OPEN" or current["title"] != TITLE:
                raise ValueError("issue changed during reconciliation; retry after review")
            command = ["gh", "issue", "edit", str(issue["number"]), "--repo", repository]
        else:
            command = ["gh", "issue", "create", "--repo", repository, "--title", TITLE]
        subprocess.run(command + ["--body-file", "-"], input=new_body, check=True, text=True, capture_output=True)
        print("Updated policy-source findings; human disposition remains required.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(f"Policy review issue reconciliation failed: {type(exc).__name__}. No automatic closure or baseline update.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
