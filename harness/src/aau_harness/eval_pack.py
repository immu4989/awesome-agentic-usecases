"""Portable, offline evaluation policy review with recomputable reviewer HTML."""

import argparse
from html import escape
import json
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered
from .authority_html import STYLE
from .eval_policy import review_evaluations


CONSTRAINT_LABELS = {
    "candidate_observation_limit": "Every candidate observation meets its limit",
    "max_mean_regression": "Average deterioration stays within budget",
    "max_regressed_scenarios": "Regressed scenario count stays within budget",
    "minimum_repeats": "Minimum repeat count on each side",
    "summary_consistency": "Stored summaries match recorded observations",
}


def _text(value) -> str:
    return escape(str(value), quote=True)


def _table(caption, headers, rows) -> str:
    heading = "".join(f'<th scope="col">{_text(value)}</th>' for value in headers)
    body = "".join("<tr>" + "".join(f"<td>{_text(value)}</td>" for value in row) + "</tr>" for row in rows)
    if not rows:
        body = f'<tr><td colspan="{len(headers)}">None recorded.</td></tr>'
    return (f'<div class="scroll"><table><caption>{_text(caption)}</caption><thead><tr>{heading}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def render_review(report: dict) -> str:
    """Only render reports freshly computed from their source evidence."""
    status = "Constraints met" if report["status"] == "constraints_met" else "Constraints not met"
    failures = _table("Failed constraints", ("Metric or source", "Constraint"), [
        (row.get("metric", row.get("source")), CONSTRAINT_LABELS[row["constraint"]]) for row in report["failed_constraints"]])
    sections = []
    for checks, comparison in zip(report["metric_checks"], report["comparisons"]):
        rows = [(CONSTRAINT_LABELS[row["constraint"]], "Met" if row["passed"] else "Not met", row["limit"],
                 row.get("observed", f"{len(row.get('violations', []))} violating observations"))
                for row in checks["checks"]]
        violations = checks["checks"][0]["violations"]
        scenarios = comparison["scenarios"]
        details = _table("Every matched scenario", ("Scenario", "Baseline mean", "Candidate mean", "Delta", "Change"),
                         [(row["scenario_id"], row["baseline_mean"], row["candidate_mean"], row["delta"], row["change"])
                          for row in scenarios])
        warnings = "".join(f'<li>{_text(value)}</li>' for value in comparison["warnings"])
        sections.append(
            f'<section><h2>{_text(checks["metric"])}</h2>'
            f'<p>Preferred direction: <strong>{_text(comparison["preferred_direction"])}</strong>. '
            f'Mean delta (candidate minus baseline): <strong>{_text(comparison["mean_delta"])}</strong>. '
            f'Descriptive 95% interval: {_text(comparison["delta_ci95"])}.</p>'
            f'<p>{_text(comparison["scenario_count"])} scenarios; baseline repeats: '
            f'{_text(comparison["baseline_repeat_count"])}; candidate repeats: {_text(comparison["candidate_repeat_count"])}.</p>'
            + _table("Policy checks", ("Constraint", "Result", "Limit", "Observed"), rows)
            + _table("Observations outside the candidate limit", ("Scenario", "Repeat", "Value"),
                     [(row["scenario_id"], row["repeat"], row["value"]) for row in violations])
            + f'<ul>{warnings}</ul><details><summary>Inspect all scenario changes</summary>{details}</details>'
            + f'<p class="muted">{_text(comparison["boundary"])}</p></section>')
    audit = report["comparisons"][0]["source_audits"]
    summaries = _table("Source summary consistency", ("Source", "Status", "Stored-summary differences"),
                       [(label, value["status"], json.dumps(value["mismatches"], ensure_ascii=False, sort_keys=True))
                        for label, value in audit.items()])
    hashes = "".join(f'<dt>{_text(label)}</dt><dd><code>{_text(report[field])}</code></dd>'
                     for label, field in (("Policy", "policy_sha256"), ("Baseline", "baseline_sha256"), ("Candidate", "candidate_sha256")))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
            'style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
            f'<title>Evaluation policy review — {status}</title><style>{STYLE}'
            'td{overflow-wrap:anywhere}details{margin:1rem 0}summary{cursor:pointer;font-weight:600}'
            '</style></head><body><main><p class="eyebrow">Evaluation evidence · offline review</p>'
            f'<h1>{status}</h1><p class="notice">{_text(report["boundary"])}</p>'
            '<p>This page does not verify itself. Run <code>aau evaluation-pack verify PATH</code> '
            'with the matching repository harness to recompute the review, HTML, and manifest.</p>'
            '<p><strong>Sharing notice:</strong> this folder contains the complete supplied evaluations, including '
            'their detail fields. It is not sanitized. Review the source files for sensitive data before sharing.</p>'
            f'<p>Required repeats on each side: <strong>{_text(report["policy"]["minimum_repeats"])}</strong>.</p>'
            f'{failures}<h2>Scope not reviewed</h2><p>{_text(", ".join(report["unreviewed_metrics"]) or "No additional metric names found; unmeasured risks remain outside this review.")}</p>'
            f'{"".join(sections)}<h2>Evidence consistency</h2>{summaries}'
            f'<h2>Source-value hashes</h2><dl>{hashes}</dl>'
            '<p>Retain all six files together. Hashes are not signatures; coordinated replacement of sources '
            'and derived outputs can still verify. This is not independent attestation.</p></main></body></html>\n')


def pack_payloads(policy: dict, baseline: dict, candidate: dict) -> tuple[dict, dict[str, bytes]]:
    report = review_evaluations(policy, baseline, candidate)
    payloads = {name: rendered(value) for name, value in (
        ("policy.json", policy), ("baseline.json", baseline), ("candidate.json", candidate), ("review.json", report))}
    payloads["review.html"] = render_review(report).encode("utf-8")
    # Every file has a bound, including expanded HTML. Never silently truncate evidence.
    if any(len(value) > MAX_JSON_BYTES for value in payloads.values()):
        raise AgentBomError("review pack member exceeds 2 MB limit")
    manifest = {"pack_version": "aau-evaluation-review-pack/1.0",
                "files": {name: digest(value) for name, value in sorted(payloads.items())},
                "boundary": "Unsigned local evidence bundle. Verification recomputes current-harness outputs, not authenticity, policy timing, or execution."}
    payloads["manifest.json"] = rendered(manifest)
    return report, payloads


def create_pack(policy: dict, baseline: dict, candidate: dict, directory: Path) -> dict:
    if directory.exists() or directory.is_symlink():
        raise AgentBomError("refusing to overwrite an existing pack destination")
    report, payloads = pack_payloads(policy, baseline, candidate)
    directory.mkdir(parents=True, exist_ok=False)
    # Manifest is last. Interrupted writes leave an incomplete pack that cannot verify.
    for name, payload in payloads.items():
        with (directory / name).open("xb") as stream:
            stream.write(payload)
    return report


def verify_pack(directory: Path) -> dict:
    names = {"policy.json", "baseline.json", "candidate.json", "review.json", "review.html", "manifest.json"}
    if directory.is_symlink() or not directory.is_dir():
        raise AgentBomError("review pack must be a real directory")
    if {path.name for path in directory.iterdir()} != names:
        raise AgentBomError("review pack file set is incomplete or unexpected")
    for name in names:
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise AgentBomError(f"invalid review pack member: {name}")
    report, expected = pack_payloads(*(load_json(directory / name) for name in ("policy.json", "baseline.json", "candidate.json")))
    for name, payload in expected.items():
        if (directory / name).read_bytes() != payload:
            raise AgentBomError(f"review pack member does not recompute: {name}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau evaluation-pack", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    for name in ("policy", "baseline", "candidate"):
        create.add_argument(name, type=Path)
    create.add_argument("--out", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            report = create_pack(load_json(args.policy), load_json(args.baseline), load_json(args.candidate), args.out)
        else:
            report = verify_pack(args.directory)
        print(f"{report['status']}; complete offline review pack; not deployment approval")
        return int(report["status"] != "constraints_met")
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
