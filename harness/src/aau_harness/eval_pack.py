"""Portable, offline evaluation policy review with recomputable reviewer HTML."""

import argparse
from html import escape
import json
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered
from .authority_html import STYLE
from .eval_policy import review_evaluations
from .eval_import import import_observations
from .eval_diagnostics import diagnostic_reports, render_diagnostics


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


def render_review(report: dict, *, recordings: bool = False, diagnostics_html: str = "") -> str:
    """Only render reports freshly computed from their source evidence."""
    status = "Constraints met" if report["status"] == "constraints_met" else "Constraints not met"
    failures = _table("Failed constraints", ("Metric or source", "Constraint"), [
        ((f"Cohort {row['cohort_id']} · " if "cohort_id" in row else "") + row.get("metric", row.get("source")),
         CONSTRAINT_LABELS[row["constraint"]]) for row in report["failed_constraints"]])
    sections = []
    views = [(checks, comparison, None) for checks, comparison in zip(report["metric_checks"], report["comparisons"])]
    for cohort in report.get("cohort_reviews", []):
        views.extend((checks, comparison, cohort["cohort_id"])
                     for checks, comparison in zip(cohort["metric_checks"], cohort["comparisons"]))
    for checks, comparison, cohort_id in views:
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
            f'<section><h2>{_text((f"Cohort {cohort_id} · " if cohort_id is not None else "") + checks["metric"])}</h2>'
            + (f'<p class="notice">{_text(report["cohort_boundary"])}</p>' if cohort_id is not None else "")
            + f'<p>Preferred direction: <strong>{_text(comparison["preferred_direction"])}</strong>. '
            f'Mean delta (candidate minus baseline): <strong>{_text(comparison["mean_delta"])}</strong>. '
            f'Descriptive 95% interval: {_text(comparison["delta_ci95"])}.</p>'
            f'<p>{_text(comparison["scenario_count"])} scenarios; baseline repeats: '
            f'{_text(comparison["baseline_repeat_count"])}; candidate repeats: {_text(comparison["candidate_repeat_count"])}.</p>'
            f'<p>Declared evaluation context: <strong>{_text(comparison["context_match"]["status"])}</strong>. '
            'Matching fingerprints are not execution attestations.</p>'
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
    file_count = ("thirteen" if recordings else "eleven") if diagnostics_html else ("eight" if recordings else "six")
    navigation = '<p><a href="#diagnostics">Inspect repeated-run and operating diagnostics ↓</a></p>' if diagnostics_html else ""
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
            'style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
            f'<title>Evaluation policy review — {status}</title><style>{STYLE}'
            'td{overflow-wrap:anywhere}details{margin:1rem 0}summary{cursor:pointer;font-weight:600}'
            '</style></head><body><main><p class="eyebrow">Evaluation evidence · offline review</p>'
            f'<h1>{status}</h1>'
            + ('<p class="notice">Recorded-observation pack: retains both supplied recordings and normalized '
               'evaluations. Verification recomputes imports and policy review, not original execution or scoring. '
               'Use <code>aau evaluation-pack verify PATH --require-recordings</code> to require this evidence chain.</p>'
               if recordings else '')
            + f'<p class="notice">{_text(report["boundary"])}</p>'
            '<p>This page does not verify itself. Run <code>aau evaluation-pack verify PATH</code> '
            'with the matching repository harness to recompute the review, HTML, and manifest.</p>'
            '<p><strong>Sharing notice:</strong> this folder contains the complete supplied evaluations, including '
            'their detail fields. It is not sanitized. Review the source files for sensitive data before sharing.</p>'
            f'<p>Required repeats on each side: <strong>{_text(report["policy"]["minimum_repeats"])}</strong>.</p>'
            f'{failures}{navigation}<h2>Scope not reviewed</h2><p>{_text(", ".join(report["unreviewed_metrics"]) or "No additional metric names found; unmeasured risks remain outside this review.")}</p>'
            f'{"".join(sections)}<h2>Evidence consistency</h2>{summaries}'
            f'<h2>Source-value hashes</h2><dl>{hashes}</dl>'
            + f'<p>Retain all {file_count} files together. Hashes are not signatures; coordinated replacement of sources '
            'and derived outputs can still verify. This is not independent attestation.</p>'
            + diagnostics_html + '</main></body></html>\n')


def pack_payloads(policy: dict, baseline: dict, candidate: dict, *, recordings: bool = False,
                  diagnostics: dict | None = None) -> tuple[dict, dict[str, bytes]]:
    originals = (baseline, candidate)
    if recordings:
        baseline, candidate = (import_observations(source) for source in originals)
    report = review_evaluations(policy, baseline, candidate)
    payloads = {name: rendered(value) for name, value in (
        ("policy.json", policy), ("baseline.json", baseline), ("candidate.json", candidate), ("review.json", report))}
    diagnostics_html = ""
    if diagnostics is not None:
        reports = diagnostic_reports(diagnostics, baseline, candidate)
        payloads.update({name: rendered(value) for name, value in reports.items()})
        payloads["diagnostics.json"] = rendered(diagnostics)
        diagnostics_html = render_diagnostics(diagnostics, reports)
    payloads["review.html"] = render_review(report, recordings=recordings, diagnostics_html=diagnostics_html).encode("utf-8")
    if recordings:
        payloads.update({name: rendered(source) for name, source in zip(
            ("baseline-recording.json", "candidate-recording.json"), originals)})
    # Every file has a bound, including expanded HTML. Never silently truncate evidence.
    if any(len(value) > MAX_JSON_BYTES for value in payloads.values()):
        raise AgentBomError("review pack member exceeds 2 MB limit")
    manifest = {"pack_version": "aau-evaluation-review-pack/1.1" if recordings else "aau-evaluation-review-pack/1.0",
                "files": {name: digest(value) for name, value in sorted(payloads.items())},
                "boundary": "Unsigned local evidence bundle. Verification recomputes current-harness outputs, not authenticity, policy timing, or execution."}
    if diagnostics is not None:
        manifest.update(pack_version="aau-evaluation-review-pack/2.0",
                        input_format="recordings" if recordings else "evaluations")
    payloads["manifest.json"] = rendered(manifest)
    return report, payloads


def create_pack(policy: dict, baseline: dict, candidate: dict, directory: Path, *, recordings: bool = False,
                diagnostics: dict | None = None) -> dict:
    if directory.exists() or directory.is_symlink():
        raise AgentBomError("refusing to overwrite an existing pack destination")
    report, payloads = pack_payloads(policy, baseline, candidate, recordings=recordings, diagnostics=diagnostics)
    directory.mkdir(parents=True, exist_ok=False)
    # Manifest is last. Interrupted writes leave an incomplete pack that cannot verify.
    for name, payload in payloads.items():
        with (directory / name).open("xb") as stream:
            stream.write(payload)
    return report


def verify_pack(directory: Path, *, require_recordings: bool = False, require_diagnostics: bool = False) -> dict:
    names = {"policy.json", "baseline.json", "candidate.json", "review.json", "review.html", "manifest.json"}
    if directory.is_symlink() or not directory.is_dir():
        raise AgentBomError("review pack must be a real directory")
    manifest = load_json(directory / "manifest.json")
    version = manifest.get("pack_version")
    if version not in ("aau-evaluation-review-pack/1.0", "aau-evaluation-review-pack/1.1", "aau-evaluation-review-pack/2.0"):
        raise AgentBomError("unsupported review pack version")
    recordings = version == "aau-evaluation-review-pack/1.1"
    diagnostics = version == "aau-evaluation-review-pack/2.0"
    if diagnostics:
        if manifest.get("input_format") not in ("evaluations", "recordings"):
            raise AgentBomError("diagnostic dossier requires an explicit supported input_format")
        recordings = manifest["input_format"] == "recordings"
        names.update({"diagnostics.json", "baseline-repeatability.json", "candidate-repeatability.json",
                      "baseline-operations.json", "candidate-operations.json"})
    if require_diagnostics and not diagnostics:
        raise AgentBomError("diagnostic dossier required; policy-only pack refused")
    if require_recordings and not recordings:
        raise AgentBomError("original recordings are required; normalized-only pack refused")
    if recordings:
        names.update({"baseline-recording.json", "candidate-recording.json"})
    if {path.name for path in directory.iterdir()} != names:
        raise AgentBomError("review pack file set is incomplete or unexpected")
    for name in names:
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise AgentBomError(f"invalid review pack member: {name}")
    inputs = ("policy.json", "baseline-recording.json", "candidate-recording.json") if recordings else (
        "policy.json", "baseline.json", "candidate.json")
    report, expected = pack_payloads(*(load_json(directory / name) for name in inputs), recordings=recordings,
                                     diagnostics=load_json(directory / "diagnostics.json") if diagnostics else None)
    for name, payload in expected.items():
        if (directory / name).read_bytes() != payload:
            raise AgentBomError(f"review pack member does not recompute: {name}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau evaluation-pack", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("create", "from-recordings"):
        create = commands.add_parser(command)
        for name in ("policy", "baseline", "candidate"):
            create.add_argument(name, type=Path)
        create.add_argument("--out", type=Path, required=True)
        create.add_argument("--diagnostics", type=Path, help="include repeated-run and operating views from an explicit diagnostic plan")
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    verify.add_argument("--require-recordings", action="store_true", help="refuse normalized-only packs")
    verify.add_argument("--require-diagnostics", action="store_true", help="refuse policy-only packs")
    args = parser.parse_args(argv)
    try:
        if args.command in ("create", "from-recordings"):
            report = create_pack(load_json(args.policy), load_json(args.baseline), load_json(args.candidate), args.out,
                                 recordings=args.command == "from-recordings",
                                 diagnostics=load_json(args.diagnostics) if args.diagnostics else None)
        else:
            report = verify_pack(args.directory, require_recordings=args.require_recordings,
                                 require_diagnostics=args.require_diagnostics)
        print(f"{report['status']}; complete offline review pack; not deployment approval")
        return int(report["status"] != "constraints_met")
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
