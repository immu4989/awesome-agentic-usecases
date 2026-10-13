"""Recomputable diagnostic views accompanying, never overriding, policy decisions."""

from html import escape

from .agent_bom import AgentBomError
from .eval_operations import COST_BASES, review_operations
from .eval_repeatability import review_repeatability


def diagnostic_reports(plan: dict, baseline: dict, candidate: dict) -> dict:
    if not isinstance(plan, dict) or set(plan) != {"plan_version", "criteria", "draw_sizes", "cost_basis"}:
        raise AgentBomError("diagnostic plan requires exactly plan_version, criteria, draw_sizes, cost_basis")
    if plan["plan_version"] != "aau-evaluation-diagnostics/1.0":
        raise AgentBomError("unsupported diagnostic plan version")
    bases = plan["cost_basis"]
    if (not isinstance(bases, dict) or set(bases) != {"baseline", "candidate"}
            or any(value not in COST_BASES for value in bases.values())):
        raise AgentBomError("diagnostic cost_basis requires baseline and candidate declarations")
    reports = {}
    for label, source in (("baseline", baseline), ("candidate", candidate)):
        reports[f"{label}-repeatability.json"] = review_repeatability(
            source, criteria=plan["criteria"], draw_sizes=plan["draw_sizes"])
        reports[f"{label}-operations.json"] = review_operations(
            source, criteria=plan["criteria"], cost_basis=bases[label])
    return reports


def _text(value) -> str:
    return escape("Not available" if value is None else str(value), quote=True)


def _table(caption, headers, rows, *, compact_numbers=False):
    return ('<div class="scroll"><table><caption>' + _text(caption) + '</caption><thead><tr>'
            + ''.join(f'<th scope="col">{_text(value)}</th>' for value in headers)
            + '</tr></thead><tbody>'
            + ''.join('<tr>' + ''.join(f'<td>{_text(format(value, ".6g") if compact_numbers and type(value) is float else value)}</td>'
                                      for value in row) + '</tr>' for row in rows)
            + '</tbody></table></div>')


def render_diagnostics(plan: dict, reports: dict) -> str:
    """Render only freshly recomputed reports; all source-derived strings are escaped."""
    repeats = [reports[f"{label}-repeatability.json"] for label in ("baseline", "candidate")]
    operations = [reports[f"{label}-operations.json"] for label in ("baseline", "candidate")]
    overall = [report["overall"] for report in operations]
    rows = [
        ("Declared cost basis", *(report["declared_cost_basis"] for report in operations)),
        ("Recorded attempts", *(report["attempt_count"] for report in overall)),
        ("Jointly passing attempts", *(report["passing_attempt_count"] for report in overall)),
        ("Cost coverage", *(report["cost"]["status"] for report in overall)),
        ("Recorded total USD (all attempts)", *(report["cost"]["total_usd"] for report in overall)),
        ("Mean USD per attempt", *(report["cost"]["mean_per_attempt_usd"] for report in overall)),
        ("Total USD / passing attempts", *(report["cost"]["total_per_passing_attempt_usd"] for report in overall)),
        ("USD spent on non-passing attempts", *(report["cost"]["spent_on_failed_attempts_usd"] for report in overall)),
        ("Latency coverage", *(report["latency"]["status"] for report in overall)),
        ("Median latency, seconds", *(report["latency"]["p50_s"] for report in overall)),
        ("Nearest-rank p95 latency, seconds", *(report["latency"]["p95_s"] for report in overall)),
        ("Maximum latency, seconds", *(report["latency"]["max_s"] for report in overall)),
        ("API-call coverage", *(report["api_calls"]["status"] for report in overall)),
        ("Recorded total API calls", *(report["api_calls"]["total"] for report in overall)),
    ]
    curve_rows = [(left["draw_size"], left["all_pass_fraction"], right["all_pass_fraction"],
                   left["any_pass_fraction"], right["any_pass_fraction"])
                  for left, right in zip(repeats[0]["curve"], repeats[1]["curve"])]
    details = []
    for label, repeated, operating in zip(("baseline", "candidate"), repeats, operations):
        links = (f'<a href="{label}-repeatability.json">Repeated-run JSON</a> · '
                 f'<a href="{label}-operations.json">Operating JSON</a>')
        warnings = ''.join(f'<li>{_text(warning)}</li>' for report in (repeated, operating) for warning in report["warnings"])
        failed = [(row["scenario_id"], failure["repeat"], criterion["metric"], criterion["value"])
                  for row in repeated["scenarios"] for failure in row["failures"] for criterion in failure["failed_criteria"]]
        if not failed:
            failed = [("No failing observations under the diagnostic criteria", "—", "—", "—")]
        details.append(f'<h3>{label.capitalize()} diagnostic evidence</h3><p>{links}</p>'
                       + f'<ul>{warnings}</ul><details><summary>Inspect every diagnostic failure</summary>'
                       + _table("Failed diagnostic observations", ("Scenario", "Repeat", "Metric", "Value"), failed)
                       + '</details><details><summary>Methods and interpretation limits</summary>'
                       + f'<p>{_text(repeated["boundary"])}</p><p>{_text(operating["boundary"])}</p></details>')
    return ('<section id="diagnostics"><p class="eyebrow">Diagnostic dossier · descriptive only</p>'
            '<h2>What the policy verdict alone does not tell you</h2>'
            '<p class="notice">These diagnostics never change the policy verdict. Their joint observation criteria '
            'are separately supplied, not inferred from the policy or its cohort limits. A passing diagnostic '
            'is not deployment approval, and a favorable cost ratio cannot excuse a failed policy obligation.</p>'
            '<p><a href="diagnostics.json">Inspect the complete diagnostic plan</a>. '
            'Both sources use the same diagnostic criteria. Cost bases are declarations; different bases, '
            'repeat counts, workloads, or measurement conditions can make side-by-side values misleading. No winner is declared.</p>'
            '<p>Require these views during handoff with <code>aau evaluation-pack verify PATH --require-diagnostics</code>. '
            'This recomputes all included reports and the page; it does not authenticate their source observations.</p>'
            + _table("Diagnostic criteria: all must pass on the same attempt", ("Metric", "Preferred direction", "Inclusive limit"),
                     [(rule["metric"], rule["direction"], rule["limit"]) for rule in repeats[0]["criteria"]])
            + _table("Recorded operating evidence (not a forecast)", ("Measure", "Baseline", "Candidate"), rows, compact_numbers=True)
            + '<p>Not available means insufficient recorded data or no passing attempts, not zero. '
            'Cost per passing attempt includes the cost of all attempts. JSON reports retain coverage counts and null reasons.</p>'
            + _table("Recorded-subset fractions, equal-weighted across scenarios", ("Subset size", "Baseline all pass", "Candidate all pass", "Baseline any pass", "Candidate any pass"), curve_rows, compact_numbers=True)
            + '<p>Fractions range from 0 to 1. Any-pass asks whether at least one recorded attempt passes; '
            'all-pass requires every attempt in the subset to pass. Neither is a future-run probability '
            'or permission to retry consequential actions. Operating values and fractions are displayed to six significant digits; '
            'full computed values and per-scenario counts remain in the JSON files. Criterion limits and failed values are not display-rounded.</p>'
            + ''.join(details) + '</section>')
