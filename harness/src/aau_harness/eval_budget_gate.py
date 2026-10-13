"""Compose policy and candidate operating checks without changing either source verdict."""

from .agent_bom import AgentBomError, digest
from .eval_budget import review_budget
from .eval_diagnostics import _table, _text
from .eval_repeatability import _criteria


def budget_gate(plan: dict, diagnostics: dict, policy_review: dict, candidate: dict) -> tuple[dict, dict]:
    if diagnostics is None:
        raise AgentBomError("budget-gated packs require a diagnostic plan with declared candidate cost basis")
    budget = review_budget(plan, candidate, cost_basis=diagnostics["cost_basis"]["candidate"])
    if _criteria(plan["criteria"]) != _criteria(diagnostics["criteria"]):
        raise AgentBomError("budget and diagnostics must use the same joint-pass criteria")
    status = ("constraints_not_met" if "constraints_not_met" in (policy_review["status"], budget["status"]) else
              "constraints_not_verified" if budget["status"] == "constraints_not_verified" else "constraints_met")
    gate = {"report_version": "aau-evaluation-budget-gate/1.0", "status": status,
            "policy_status": policy_review["status"], "candidate_budget_status": budget["status"],
            "policy_review_sha256": digest(policy_review), "candidate_budget_sha256": digest(budget),
            "budget_plan_sha256": digest(plan), "diagnostics_sha256": digest(diagnostics),
            "candidate_sha256": digest(candidate),
            "boundary": "Both policy and candidate operating-budget constraints must be met. Unknown budget evidence cannot pass. Baseline budgets are not gated. The source policy verdict remains unchanged; diagnostics alone do not change it. This combined recorded-evidence gate is not deployment approval, production SLO assurance, invoice verification, or authenticated execution. Hashes are not signatures."}
    return gate, budget


def render_budget_gate(gate: dict, budget: dict) -> str:
    labels = {"constraints_met": "Met", "constraints_not_met": "Not met",
              "constraints_not_verified": "Not verified", "met": "Met", "exceeded": "Exceeded", "not_verified": "Not verified"}
    measures = {"total_cost_usd": "Total USD, including failures", "cost_per_passing_attempt_usd": "USD per jointly passing attempt",
                "p95_latency_s": "p95 latency, seconds", "max_latency_s": "Maximum latency, seconds", "total_api_calls": "Total API calls"}
    reasons = {"declared_cost_basis_mismatch": "Declared cost basis differs from budget",
               "incomplete_measurement_coverage": "Incomplete measurement coverage",
               "no_jointly_passing_attempts": "No jointly passing attempts", None: "—"}
    prerequisites = {"minimum_repeats": "Minimum repeats", "metric_summary_consistency": "Stored metric summaries"}
    rows = [("Overall" if scope["scope"] == "overall" else "Group: " + scope["group_id"], measures[check["constraint"]],
             labels[check["status"]], check["limit"], check["observed"], reasons[check["reason"]])
            for scope in budget["scopes"] for check in scope["checks"]]
    return ('<section id="operating-budget"><h2>Combined policy and candidate operating-budget gate</h2>'
            + _table("Independent verdicts — both must meet their constraints", ("Review", "Result"),
                     [("Policy", labels[gate["policy_status"]]), ("Candidate operating budget", labels[gate["candidate_budget_status"]])])
            + '<p class="notice">Missing budget evidence cannot pass. A known failure takes precedence in the '
              'combined status; inspect all unverified checks too. Only the candidate budget is gated. '
              'Group totals may overlap and must not be added. This is not deployment approval.</p>'
            + _table("Candidate operating-budget checks", ("Scope", "Measure", "Result", "Upper limit", "Observed", "Reason"), rows)
            + _table("Budget prerequisites", ("Prerequisite", "Result", "Required", "Observed"),
                     [(prerequisites[c["constraint"]], labels[c["status"]], c.get("limit", "consistent"), c["observed"])
                      for c in budget["prerequisites"]])
            + '<p><a href="operating-budget.json">Budget plan</a> · <a href="candidate-budget.json">Full budget review</a> · '
              '<a href="gate.json">Combined gate</a> · <a href="review.json">Unchanged policy verdict</a></p>'
            + f'<p>{_text(budget["boundary"])}</p><p>Require this layer when verifying: '
              '<code>aau evaluation-pack verify PATH --require-budget</code>.</p></section>')
