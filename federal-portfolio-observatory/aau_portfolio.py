#!/usr/bin/env python3
"""Dependency-free Federal AI Portfolio Observatory validator and packager.

The Observatory finds documentation gaps, possible overlap, missing measurements,
and untested obligations. It never recommends an investment, award, cancellation,
deployment, compliance conclusion, or protected decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


PORTFOLIO_VERSION = "aau-federal-ai-portfolio/0.5"
PUBLIC_VALUE_VERSION = "aau-public-value-ledger/0.5"
TEVV_VERSION = "aau-three-layer-tev-v/0.5"
CLAUSE_VERSION = "aau-ai-clause-testbench/0.5"
SOURCE_VERSION = "aau-federal-portfolio-sources/0.5"
PACK_VERSION = "aau-federal-portfolio-pack/0.5"
ANALYSIS_VERSION = "aau-federal-portfolio-analysis/0.5"
SAFE_CLASSIFICATIONS = {"public", "synthetic", "public_synthetic"}
LIFECYCLES = {"proposed", "piloting", "operational", "paused", "retired"}
IMPACT_STATUSES = {"yes", "no", "uncertain_requires_review"}
LAYERS = {"model_testing", "red_teaming", "field_simulation"}
CLAUSE_AREAS = {
    "government_data_and_ip",
    "privacy_and_training_use",
    "portability_and_exit",
    "pricing_and_total_cost",
    "continuous_evaluation",
    "accessibility_and_service_delivery",
    "incident_and_change_notification",
}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SENSITIVE_PATTERNS = (
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("telephone", re.compile(r"(?<!\d)(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}(?!\d)")),
    ("private-key", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("aws-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("bearer-token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.I)),
)
PACK_NAMES = (
    "README.md",
    "portfolio-analysis.json",
    "public-value-assessment.json",
    "tev-v-coverage.json",
    "clause-test-coverage.json",
    "privacy-scan.json",
    "source-snapshot.json",
    "manifest.json",
)


class ValidationError(ValueError):
    """Raised when a public contract violates a structural or safety invariant."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read valid JSON from {path}: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def require_object(value: Any, label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def require_list(value: Any, label: str, minimum: int = 1) -> list[Any]:
    require(
        isinstance(value, list) and len(value) >= minimum,
        f"{label} must contain at least {minimum} item(s)",
    )
    return value


def require_text(value: Any, label: str) -> str:
    require(isinstance(value, str) and value.strip(), f"{label} must be non-empty text")
    return value.strip()


def require_slug(value: Any, label: str) -> str:
    text = require_text(value, label)
    require(bool(SLUG.fullmatch(text)), f"{label} must be a lowercase hyphenated id")
    return text


def require_unique(values: Iterable[str], label: str) -> None:
    items = list(values)
    require(len(items) == len(set(items)), f"{label} must be unique")


def validate_sharing(value: Any, label: str = "sharing") -> None:
    sharing = require_object(value, label)
    require(
        sharing.get("classification") in SAFE_CLASSIFICATIONS,
        f"{label}.classification must be public or synthetic",
    )
    require(
        sharing.get("human_review_complete") is True,
        f"{label}.human_review_complete must be true",
    )
    for field in (
        "contains_personally_identifiable_information",
        "contains_procurement_sensitive_information",
        "contains_controlled_unclassified_information",
        "contains_classified_information",
        "contains_secrets_or_credentials",
    ):
        require(
            sharing.get(field) is False,
            f"{label}.{field} must be false for this public tool",
        )


def validate_inventory(value: Any) -> dict[str, Any]:
    inventory = require_object(value, "inventory")
    require(
        inventory.get("profile_version") == PORTFOLIO_VERSION,
        f"profile_version must be {PORTFOLIO_VERSION}",
    )
    require_slug(inventory.get("portfolio_id"), "portfolio_id")
    require_text(inventory.get("agency_context"), "agency_context")
    date.fromisoformat(require_text(inventory.get("as_of"), "as_of"))
    validate_sharing(inventory.get("sharing"))
    goals = require_list(inventory.get("strategic_goals"), "strategic_goals")
    goal_ids = []
    for index, goal_value in enumerate(goals):
        goal = require_object(goal_value, f"strategic_goals[{index}]")
        goal_ids.append(
            require_slug(goal.get("goal_id"), f"strategic_goals[{index}].goal_id")
        )
        require_text(goal.get("title"), f"strategic_goals[{index}].title")
        require_text(
            goal.get("outcome_metric"),
            f"strategic_goals[{index}].outcome_metric",
        )
    require_unique(goal_ids, "strategic goal ids")
    use_cases = require_list(inventory.get("use_cases"), "use_cases")
    use_case_ids = []
    for index, item_value in enumerate(use_cases):
        item = require_object(item_value, f"use_cases[{index}]")
        use_case_ids.append(
            require_slug(item.get("use_case_id"), f"use_cases[{index}].use_case_id")
        )
        require_text(item.get("title"), f"use_cases[{index}].title")
        require_text(item.get("mission"), f"use_cases[{index}].mission")
        require(
            item.get("lifecycle") in LIFECYCLES,
            f"use_cases[{index}].lifecycle is invalid",
        )
        require(
            item.get("high_impact_status") in IMPACT_STATUSES,
            f"use_cases[{index}].high_impact_status is invalid",
        )
        require_list(item.get("capabilities"), f"use_cases[{index}].capabilities")
        require_list(item.get("data_classes"), f"use_cases[{index}].data_classes")
        require(
            isinstance(item.get("performance_metrics", []), list),
            f"use_cases[{index}].performance_metrics must be a list",
        )
        require(
            isinstance(item.get("strategic_goal_ids", []), list),
            f"use_cases[{index}].strategic_goal_ids must be a list",
        )
        unknown_goals = set(item.get("strategic_goal_ids", [])) - set(goal_ids)
        require(
            not unknown_goals,
            f"use_cases[{index}] references unknown strategic goals: {sorted(unknown_goals)}",
        )
        cost = item.get("estimated_annual_cost_usd")
        require(
            cost is None or isinstance(cost, (int, float)) and cost >= 0,
            f"use_cases[{index}].estimated_annual_cost_usd must be nonnegative or null",
        )
    require_unique(use_case_ids, "use case ids")
    return inventory


def validate_public_value(
    value: Any,
    inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ledger = require_object(value, "public value ledger")
    require(
        ledger.get("profile_version") == PUBLIC_VALUE_VERSION,
        f"profile_version must be {PUBLIC_VALUE_VERSION}",
    )
    require_slug(ledger.get("ledger_id"), "ledger_id")
    validate_sharing(ledger.get("sharing"))
    records = require_list(ledger.get("records"), "records")
    inventory_ids = (
        {item["use_case_id"] for item in inventory["use_cases"]}
        if inventory
        else None
    )
    record_ids = []
    for index, item_value in enumerate(records):
        item = require_object(item_value, f"records[{index}]")
        record_ids.append(
            require_slug(item.get("record_id"), f"records[{index}].record_id")
        )
        use_case_id = require_slug(
            item.get("use_case_id"), f"records[{index}].use_case_id"
        )
        require(
            inventory_ids is None or use_case_id in inventory_ids,
            f"records[{index}] references an unknown use case",
        )
        require(
            item.get("status") in {"baseline_only", "measured", "revalidation_due"},
            f"records[{index}].status is invalid",
        )
        for side in ("baseline", "observed"):
            metrics = require_object(item.get(side), f"records[{index}].{side}")
            for field in (
                "cases",
                "minutes_per_case",
                "error_rate",
                "human_review_minutes_per_case",
            ):
                number = metrics.get(field)
                require(
                    number is None
                    or isinstance(number, (int, float))
                    and number >= 0,
                    f"records[{index}].{side}.{field} must be nonnegative or null",
                )
            rate = metrics.get("error_rate")
            require(
                rate is None or rate <= 1,
                f"records[{index}].{side}.error_rate must be between 0 and 1",
            )
        costs = require_object(item.get("costs"), f"records[{index}].costs")
        for field in ("pilot_cost_usd", "annual_operating_cost_usd"):
            require(
                isinstance(costs.get(field), (int, float)) and costs[field] >= 0,
                f"records[{index}].costs.{field} must be nonnegative",
            )
        measurement = require_object(
            item.get("measurement"), f"records[{index}].measurement"
        )
        require_text(
            measurement.get("method"), f"records[{index}].measurement.method"
        )
        require_text(
            measurement.get("limitations"),
            f"records[{index}].measurement.limitations",
        )
        require(
            item.get("claims_verified_savings") is False,
            f"records[{index}].claims_verified_savings must remain false",
        )
    require_unique(record_ids, "public value record ids")
    return ledger


def validate_tev_v(
    value: Any,
    inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan = require_object(value, "TEV&V plan")
    require(
        plan.get("profile_version") == TEVV_VERSION,
        f"profile_version must be {TEVV_VERSION}",
    )
    require_slug(plan.get("plan_id"), "plan_id")
    validate_sharing(plan.get("sharing"))
    inventory_ids = (
        {item["use_case_id"] for item in inventory["use_cases"]}
        if inventory
        else None
    )
    use_case_id = require_slug(plan.get("use_case_id"), "use_case_id")
    require(
        inventory_ids is None or use_case_id in inventory_ids,
        "TEV&V plan references an unknown use case",
    )
    layers = require_list(plan.get("layers"), "layers", minimum=3)
    layer_ids = []
    for index, item_value in enumerate(layers):
        item = require_object(item_value, f"layers[{index}]")
        layer = item.get("layer")
        require(layer in LAYERS, f"layers[{index}].layer is invalid")
        layer_ids.append(layer)
        require_text(item.get("objective"), f"layers[{index}].objective")
        require_list(item.get("methods"), f"layers[{index}].methods")
        require_list(
            item.get("success_measures"), f"layers[{index}].success_measures"
        )
        require_list(
            item.get("stop_conditions"), f"layers[{index}].stop_conditions"
        )
        require_list(
            item.get("evidence_outputs"), f"layers[{index}].evidence_outputs"
        )
        if layer == "field_simulation":
            require_list(
                item.get("participant_roles"),
                f"layers[{index}].participant_roles",
            )
            require_text(
                item.get("consent_and_privacy"),
                f"layers[{index}].consent_and_privacy",
            )
    require(
        set(layer_ids) == LAYERS and len(layer_ids) == 3,
        "TEV&V plan must contain each testing layer exactly once",
    )
    require_text(
        plan.get("accountable_decision_role"), "accountable_decision_role"
    )
    require_list(plan.get("protected_decisions"), "protected_decisions")
    return plan


def validate_clauses(value: Any) -> dict[str, Any]:
    library = require_object(value, "clause testbench")
    require(
        library.get("profile_version") == CLAUSE_VERSION,
        f"profile_version must be {CLAUSE_VERSION}",
    )
    require_slug(library.get("library_id"), "library_id")
    validate_sharing(library.get("sharing"))
    clauses = require_list(library.get("clauses"), "clauses")
    clause_ids = []
    areas = set()
    for index, item_value in enumerate(clauses):
        item = require_object(item_value, f"clauses[{index}]")
        clause_ids.append(
            require_slug(item.get("clause_id"), f"clauses[{index}].clause_id")
        )
        area = item.get("area")
        require(area in CLAUSE_AREAS, f"clauses[{index}].area is invalid")
        areas.add(area)
        require_text(item.get("obligation"), f"clauses[{index}].obligation")
        require_text(
            item.get("human_owner_role"),
            f"clauses[{index}].human_owner_role",
        )
        require_list(item.get("tests"), f"clauses[{index}].tests")
        require_list(
            item.get("required_evidence"),
            f"clauses[{index}].required_evidence",
        )
        require_list(
            item.get("failure_actions"),
            f"clauses[{index}].failure_actions",
        )
        require(
            item.get("legal_conclusion") is False,
            f"clauses[{index}].legal_conclusion must be false",
        )
    require_unique(clause_ids, "clause ids")
    require(
        areas == CLAUSE_AREAS,
        f"clause library must cover all areas; missing {sorted(CLAUSE_AREAS - areas)}",
    )
    return library


def validate_sources(value: Any) -> dict[str, Any]:
    ledger = require_object(value, "source ledger")
    require(
        ledger.get("profile_version") == SOURCE_VERSION,
        f"profile_version must be {SOURCE_VERSION}",
    )
    sources = require_list(ledger.get("sources"), "sources")
    source_ids = []
    for index, source_value in enumerate(sources):
        source = require_object(source_value, f"sources[{index}]")
        source_ids.append(
            require_slug(source.get("source_id"), f"sources[{index}].source_id")
        )
        require_text(source.get("title"), f"sources[{index}].title")
        url = require_text(source.get("url"), f"sources[{index}].url")
        require(url.startswith("https://"), f"sources[{index}].url must use HTTPS")
        date.fromisoformat(
            require_text(
                source.get("last_verified"),
                f"sources[{index}].last_verified",
            )
        )
        date.fromisoformat(
            require_text(source.get("review_due"), f"sources[{index}].review_due")
        )
    require_unique(source_ids, "source ids")
    return ledger


def scan_sensitive(*values: Any) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for value_index, value in enumerate(values):
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False)
        for code, pattern in SENSITIVE_PATTERNS:
            for match in pattern.finditer(raw):
                fingerprint = hashlib.sha256(match.group(0).encode()).hexdigest()[:12]
                findings.append(
                    {
                        "code": code,
                        "document_index": value_index,
                        "fingerprint": fingerprint,
                    }
                )
    return {
        "scan_version": "aau-public-portfolio-scan/0.5",
        "finding_count": len(findings),
        "findings": findings,
        "matched_values_included": False,
        "boundary": (
            "A zero-finding scan is not disclosure authorization, DLP, "
            "classification review, privacy approval, or legal advice."
        ),
    }


def tokens(value: Any) -> set[str]:
    raw = (
        " ".join(value if isinstance(value, list) else [str(value)])
        .lower()
        .replace("_", " ")
    )
    return {
        token
        for token in re.findall(r"[a-z0-9]+", raw)
        if len(token) > 2
    }


def quality_issues(item: dict[str, Any]) -> list[dict[str, Any]]:
    checks = (
        (
            "owner_role",
            "missing-owner",
            "critical",
            "Name the accountable use-case owner role.",
        ),
        (
            "expected_benefit",
            "missing-benefit",
            "critical",
            "State a measurable benefit for a lay audience.",
        ),
        (
            "system_boundary",
            "missing-boundary",
            "critical",
            "State what the system may and may not do.",
        ),
        (
            "human_authority",
            "missing-human-authority",
            "critical",
            "Name the protected human decision.",
        ),
    )
    issues = []
    for field, code, severity, remedy in checks:
        if not str(item.get(field) or "").strip():
            issues.append(
                {
                    "code": code,
                    "severity": severity,
                    "field": field,
                    "remedy": remedy,
                }
            )
    if not item.get("performance_metrics"):
        issues.append(
            {
                "code": "missing-performance-metric",
                "severity": "critical",
                "field": "performance_metrics",
                "remedy": "Define an outcome metric, baseline, and measurement owner.",
            }
        )
    if not item.get("strategic_goal_ids"):
        issues.append(
            {
                "code": "unmapped-strategic-goal",
                "severity": "important",
                "field": "strategic_goal_ids",
                "remedy": "Map the investment to a declared agency outcome.",
            }
        )
    if item.get("high_impact_status") == "uncertain_requires_review":
        issues.append(
            {
                "code": "impact-review-open",
                "severity": "critical",
                "field": "high_impact_status",
                "remedy": (
                    "Complete the accountable high-impact determination "
                    "before deployment."
                ),
            }
        )
    if item.get("estimated_annual_cost_usd") is None:
        issues.append(
            {
                "code": "cost-unknown",
                "severity": "important",
                "field": "estimated_annual_cost_usd",
                "remedy": (
                    "Record total expected operating cost or preserve the "
                    "value as explicitly unknown."
                ),
            }
        )
    return issues


def possible_overlap(
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any] | None:
    left_tokens = tokens(
        [left.get("title", ""), left.get("mission", ""), *left.get("capabilities", [])]
    )
    right_tokens = tokens(
        [
            right.get("title", ""),
            right.get("mission", ""),
            *right.get("capabilities", []),
        ]
    )
    union = left_tokens | right_tokens
    score = len(left_tokens & right_tokens) / len(union) if union else 0
    shared_capabilities = sorted(
        set(left.get("capabilities", []))
        & set(right.get("capabilities", []))
    )
    if score < 0.28 or len(shared_capabilities) < 2:
        return None
    return {
        "left_use_case_id": left["use_case_id"],
        "right_use_case_id": right["use_case_id"],
        "similarity": round(score, 3),
        "shared_capabilities": shared_capabilities,
        "disposition": "human-review-required",
        "boundary": (
            "Possible overlap is not proof of duplication and is not a "
            "cancellation or consolidation recommendation."
        ),
    }


def catalog_matches(
    item: dict[str, Any],
    catalog: list[dict[str, Any]],
    limit: int = 3,
) -> list[dict[str, Any]]:
    item_tokens = tokens(
        [item.get("title", ""), item.get("mission", ""), *item.get("capabilities", [])]
    )
    ranked = []
    for case in catalog:
        case_tokens = tokens(
            [
                case.get("title", ""),
                case.get("question", ""),
                case.get("industry", ""),
                *case.get("capabilities", []),
            ]
        )
        union = item_tokens | case_tokens
        score = len(item_tokens & case_tokens) / len(union) if union else 0
        ranked.append((score, case))
    ranked.sort(key=lambda row: (-row[0], row[1]["path"]))
    return [
        {
            "path": case["path"],
            "title": case["title"],
            "fit_score": round(score, 3),
            "fit_claim": "candidate-evaluation-contract-only",
        }
        for score, case in ranked[:limit]
        if score > 0
    ]


def analyze_inventory(
    inventory: dict[str, Any],
    catalog: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    validate_inventory(inventory)
    cases = inventory["use_cases"]
    entries = []
    for item in cases:
        issues = quality_issues(item)
        entries.append(
            {
                "use_case_id": item["use_case_id"],
                "title": item["title"],
                "lifecycle": item["lifecycle"],
                "quality_state": "needs-evidence" if issues else "documented",
                "issues": issues,
                "candidate_aau_labs": catalog_matches(item, catalog or []),
                "human_decision_required": True,
            }
        )
    overlaps = []
    for index, left in enumerate(cases):
        for right in cases[index + 1 :]:
            overlap = possible_overlap(left, right)
            if overlap:
                overlaps.append(overlap)
    critical = sum(
        issue["severity"] == "critical"
        for entry in entries
        for issue in entry["issues"]
    )
    important = sum(
        issue["severity"] == "important"
        for entry in entries
        for issue in entry["issues"]
    )
    documented = sum(not entry["issues"] for entry in entries)
    return {
        "analysis_version": ANALYSIS_VERSION,
        "portfolio_id": inventory["portfolio_id"],
        "as_of": inventory["as_of"],
        "summary": {
            "use_cases": len(cases),
            "documented": documented,
            "needs_evidence": len(cases) - documented,
            "critical_gaps": critical,
            "important_gaps": important,
            "possible_overlaps": len(overlaps),
            "estimated_annual_cost_usd": round(
                sum(
                    item.get("estimated_annual_cost_usd") or 0
                    for item in cases
                ),
                2,
            ),
            "unknown_costs": sum(
                item.get("estimated_annual_cost_usd") is None for item in cases
            ),
        },
        "entries": entries,
        "possible_overlaps": overlaps,
        "decisions": {
            "investment": "not-produced",
            "award": "not-produced",
            "deployment": "not-produced",
            "cancellation": "not-produced",
        },
        "boundary": (
            "This analysis surfaces documentation and evaluation questions. "
            "Accountable officials retain portfolio, budget, acquisition, "
            "deployment, and retirement decisions."
        ),
    }


def assess_public_value(
    ledger: dict[str, Any],
    inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_public_value(ledger, inventory)
    records = []
    for item in ledger["records"]:
        before = item["baseline"]
        after = item["observed"]
        measured = (
            item["status"] == "measured"
            and bool(before.get("cases"))
            and bool(after.get("cases"))
        )
        time_change = None
        error_change = None
        if (
            measured
            and before.get("minutes_per_case") is not None
            and after.get("minutes_per_case") is not None
        ):
            time_change = round(
                after["minutes_per_case"] - before["minutes_per_case"], 3
            )
        if (
            measured
            and before.get("error_rate") is not None
            and after.get("error_rate") is not None
        ):
            error_change = round(
                after["error_rate"] - before["error_rate"], 6
            )
        records.append(
            {
                "record_id": item["record_id"],
                "use_case_id": item["use_case_id"],
                "measurement_state": (
                    "measured-with-limitations" if measured else "baseline-only"
                ),
                "minutes_per_case_change": time_change,
                "error_rate_change": error_change,
                "pilot_cost_usd": item["costs"]["pilot_cost_usd"],
                "annual_operating_cost_usd": item["costs"][
                    "annual_operating_cost_usd"
                ],
                "limitations": item["measurement"]["limitations"],
                "verified_savings_claim": False,
            }
        )
    return {
        "assessment_version": "aau-public-value-assessment/0.5",
        "ledger_id": ledger["ledger_id"],
        "records": records,
        "summary": {
            "records": len(records),
            "measured": sum(
                item["measurement_state"] == "measured-with-limitations"
                for item in records
            ),
            "baseline_only": sum(
                item["measurement_state"] == "baseline-only"
                for item in records
            ),
            "pilot_cost_usd": round(
                sum(item["pilot_cost_usd"] for item in records), 2
            ),
            "annual_operating_cost_usd": round(
                sum(item["annual_operating_cost_usd"] for item in records), 2
            ),
        },
        "boundary": (
            "Observed changes remain bounded to the declared measurement design. "
            "This assessment does not claim audited savings, causal impact, "
            "budget authority, or production approval."
        ),
    }


def tevv_coverage(
    plan: dict[str, Any],
    inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_tev_v(plan, inventory)
    layers = []
    for item in plan["layers"]:
        layers.append(
            {
                "layer": item["layer"],
                "methods": len(item["methods"]),
                "success_measures": len(item["success_measures"]),
                "stop_conditions": len(item["stop_conditions"]),
                "evidence_outputs": len(item["evidence_outputs"]),
                "participant_roles": len(item.get("participant_roles", [])),
                "structurally_ready": True,
            }
        )
    return {
        "coverage_version": "aau-three-layer-tev-v-coverage/0.5",
        "plan_id": plan["plan_id"],
        "use_case_id": plan["use_case_id"],
        "layers": layers,
        "three_layer_complete": {item["layer"] for item in layers} == LAYERS,
        "field_simulation_is_production_evidence": False,
        "boundary": (
            "Structural coverage is not evidence that testing occurred or that "
            "the system is valid, safe, compliant, or approved."
        ),
    }


def clause_coverage(library: dict[str, Any]) -> dict[str, Any]:
    validate_clauses(library)
    clauses = [
        {
            "clause_id": item["clause_id"],
            "area": item["area"],
            "tests": len(item["tests"]),
            "required_evidence": len(item["required_evidence"]),
            "failure_actions": len(item["failure_actions"]),
            "human_owner_role": item["human_owner_role"],
            "structurally_testable": True,
        }
        for item in library["clauses"]
    ]
    return {
        "coverage_version": "aau-ai-clause-test-coverage/0.5",
        "library_id": library["library_id"],
        "areas": len({item["area"] for item in clauses}),
        "clauses": clauses,
        "legal_conclusion": False,
        "boundary": (
            "A testable obligation is not approved contract language, legal "
            "advice, a compliance determination, or proof of performance."
        ),
    }


def policy_drift(sources: dict[str, Any], as_of: date) -> dict[str, Any]:
    validate_sources(sources)
    rows = []
    for source in sources["sources"]:
        due = date.fromisoformat(source["review_due"])
        rows.append(
            {
                "source_id": source["source_id"],
                "review_due": source["review_due"],
                "status": "review-due" if due < as_of else "current",
            }
        )
    return {
        "drift_version": "aau-federal-portfolio-policy-drift/0.5",
        "as_of": as_of.isoformat(),
        "current": sum(row["status"] == "current" for row in rows),
        "review_due": sum(row["status"] == "review-due" for row in rows),
        "sources": rows,
        "boundary": (
            "Review dates are maintenance signals, not automatic legal or "
            "policy conclusions."
        ),
    }


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()


def safe_pack_path(name: str) -> None:
    path = PurePosixPath(name)
    require(
        not path.is_absolute()
        and ".." not in path.parts
        and len(path.parts) == 1,
        f"unsafe pack path: {name}",
    )


def build_pack(
    inventory: dict[str, Any],
    ledger: dict[str, Any],
    tevv: dict[str, Any],
    clauses: dict[str, Any],
    sources: dict[str, Any],
    catalog: list[dict[str, Any]],
) -> dict[str, bytes]:
    analysis = analyze_inventory(inventory, catalog)
    public_value = assess_public_value(ledger, inventory)
    tevv_result = tevv_coverage(tevv, inventory)
    clause_result = clause_coverage(clauses)
    drift = policy_drift(sources, date.fromisoformat(inventory["as_of"]))
    privacy = scan_sensitive(inventory, ledger, tevv, clauses)
    require(
        privacy["finding_count"] == 0,
        "public pack blocked by sensitive-data scan findings",
    )
    readme = (
        f"# Federal AI Portfolio evidence pack — {inventory['portfolio_id']}\n\n"
        f"Generated from public or synthetic records as of {inventory['as_of']}.\n\n"
        "This pack surfaces inventory gaps, possible overlap, measurement coverage, "
        "TEV&V structure, and testable acquisition obligations. It does not rank "
        "vendors, select investments, recommend awards, approve deployment, claim "
        "audited savings, certify compliance, or replace accountable officials.\n"
    ).encode()
    files: dict[str, bytes] = {
        "README.md": readme,
        "portfolio-analysis.json": canonical_bytes(analysis),
        "public-value-assessment.json": canonical_bytes(public_value),
        "tev-v-coverage.json": canonical_bytes(tevv_result),
        "clause-test-coverage.json": canonical_bytes(clause_result),
        "privacy-scan.json": canonical_bytes(privacy),
        "source-snapshot.json": canonical_bytes(
            {"source_ledger": sources, "drift": drift}
        ),
    }
    manifest = {
        "manifest_version": PACK_VERSION,
        "portfolio_id": inventory["portfolio_id"],
        "created": f"{inventory['as_of']}T00:00:00Z",
        "hash_algorithm": "sha256",
        "files": [
            {
                "path": name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
            for name, data in sorted(files.items())
        ],
        "claims": {
            "investment_recommendation": False,
            "award_recommendation": False,
            "deployment_approval": False,
            "audited_savings": False,
            "compliance_certification": False,
        },
    }
    files["manifest.json"] = canonical_bytes(manifest)
    require(set(files) == set(PACK_NAMES), "internal pack contract drifted")
    return files


def write_pack(files: dict[str, bytes], output: Path) -> None:
    require(
        not output.exists()
        or output.is_dir()
        and not any(output.iterdir()),
        f"refusing to overwrite non-empty output path: {output}",
    )
    output.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        safe_pack_path(name)
        (output / name).write_bytes(data)


def verify_pack(output: Path) -> dict[str, Any]:
    require(output.is_dir(), "pack path must be a directory")
    actual = {path.name for path in output.iterdir() if path.is_file()}
    require(
        actual == set(PACK_NAMES),
        (
            f"pack files differ: missing={sorted(set(PACK_NAMES) - actual)}, "
            f"extra={sorted(actual - set(PACK_NAMES))}"
        ),
    )
    manifest = load_json(output / "manifest.json")
    require(
        manifest.get("manifest_version") == PACK_VERSION,
        "pack manifest version is invalid",
    )
    listed = {item["path"]: item for item in manifest.get("files", [])}
    require(
        set(listed) == set(PACK_NAMES) - {"manifest.json"},
        "pack manifest file list is incomplete",
    )
    for name, item in listed.items():
        safe_pack_path(name)
        data = (output / name).read_bytes()
        require(len(data) == item["bytes"], f"byte count differs for {name}")
        require(
            hashlib.sha256(data).hexdigest() == item["sha256"],
            f"digest differs for {name}",
        )
    return manifest


def default_paths() -> tuple[Path, Path]:
    kit = Path(__file__).resolve().parent
    root = kit.parent
    return kit / "sources.json", root / "docs" / "use-cases.json"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    sub = value.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate one portfolio contract")
    validate.add_argument(
        "kind",
        choices=("inventory", "public-value", "tev-v", "clauses", "sources"),
    )
    validate.add_argument("path", type=Path)
    analyze = sub.add_parser(
        "analyze",
        help="find portfolio quality gaps and possible overlap",
    )
    analyze.add_argument("inventory", type=Path)
    analyze.add_argument("--catalog", type=Path)
    analyze.add_argument("--out", type=Path)
    analyze.add_argument("--json", action="store_true")
    assess = sub.add_parser(
        "assess-public-value",
        help="recompute bounded public-value changes",
    )
    assess.add_argument("ledger", type=Path)
    assess.add_argument("--inventory", type=Path)
    assess.add_argument("--out", type=Path)
    coverage = sub.add_parser(
        "tev-v-coverage",
        help="verify three-layer evaluation coverage",
    )
    coverage.add_argument("plan", type=Path)
    coverage.add_argument("--inventory", type=Path)
    coverage.add_argument("--out", type=Path)
    clause = sub.add_parser(
        "clause-coverage",
        help="verify clause-to-test coverage",
    )
    clause.add_argument("library", type=Path)
    clause.add_argument("--out", type=Path)
    scan = sub.add_parser("scan", help="run narrow public-data scan")
    scan.add_argument("paths", type=Path, nargs="+")
    scan.add_argument("--json", action="store_true")
    drift = sub.add_parser(
        "policy-drift",
        help="check dated official-source maintenance",
    )
    drift.add_argument("--sources", type=Path)
    drift.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=date.today(),
    )
    drift.add_argument("--json", action="store_true")
    pack = sub.add_parser(
        "pack",
        help="build an eight-file deterministic evidence pack",
    )
    pack.add_argument("inventory", type=Path)
    pack.add_argument("ledger", type=Path)
    pack.add_argument("tev_v", type=Path)
    pack.add_argument("clauses", type=Path)
    pack.add_argument("--sources", type=Path)
    pack.add_argument("--catalog", type=Path)
    pack.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser(
        "verify-pack",
        help="verify exact files and SHA-256 manifest",
    )
    verify.add_argument("path", type=Path)
    return value


def emit(value: Any, output: Path | None = None) -> None:
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if output:
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    source_default, catalog_default = default_paths()
    try:
        if args.command == "validate":
            validators = {
                "inventory": validate_inventory,
                "public-value": validate_public_value,
                "tev-v": validate_tev_v,
                "clauses": validate_clauses,
                "sources": validate_sources,
            }
            value = validators[args.kind](load_json(args.path))
            identity = (
                value.get("portfolio_id")
                or value.get("ledger_id")
                or value.get("plan_id")
                or value.get("library_id")
                or len(value["sources"])
            )
            print(f"VALID — {args.kind} · {identity}")
            return 0
        if args.command == "analyze":
            result = analyze_inventory(
                validate_inventory(load_json(args.inventory)),
                load_json(args.catalog or catalog_default),
            )
            if args.json or args.out:
                emit(result, args.out)
            else:
                summary = result["summary"]
                print(
                    "PORTFOLIO ANALYZED — "
                    f"{summary['use_cases']} use cases · "
                    f"{summary['critical_gaps']} critical gaps · "
                    f"{summary['possible_overlaps']} possible overlaps"
                )
            return 0
        if args.command == "assess-public-value":
            inventory = (
                validate_inventory(load_json(args.inventory))
                if args.inventory
                else None
            )
            result = assess_public_value(load_json(args.ledger), inventory)
            emit(result, args.out)
            return 0
        if args.command == "tev-v-coverage":
            inventory = (
                validate_inventory(load_json(args.inventory))
                if args.inventory
                else None
            )
            emit(tevv_coverage(load_json(args.plan), inventory), args.out)
            return 0
        if args.command == "clause-coverage":
            emit(clause_coverage(load_json(args.library)), args.out)
            return 0
        if args.command == "scan":
            result = scan_sensitive(*(load_json(path) for path in args.paths))
            if args.json:
                emit(result)
            else:
                print(
                    "PUBLIC PORTFOLIO SCAN — "
                    f"{result['finding_count']} finding(s); matched values omitted"
                )
            return 0 if result["finding_count"] == 0 else 1
        if args.command == "policy-drift":
            result = policy_drift(
                load_json(args.sources or source_default),
                args.as_of,
            )
            if args.json:
                emit(result)
            else:
                print(
                    "POLICY DEPENDENCIES — "
                    f"{result['current']} current · "
                    f"{result['review_due']} review due"
                )
            return 0 if result["review_due"] == 0 else 1
        if args.command == "pack":
            files = build_pack(
                validate_inventory(load_json(args.inventory)),
                load_json(args.ledger),
                load_json(args.tev_v),
                load_json(args.clauses),
                load_json(args.sources or source_default),
                load_json(args.catalog or catalog_default),
            )
            write_pack(files, args.out)
            print(
                f"PORTFOLIO PACK BUILT — {args.out} · {len(files)} files"
            )
            return 0
        manifest = verify_pack(args.path)
        print(
            "PORTFOLIO PACK VERIFIED — "
            f"{manifest['portfolio_id']} · "
            f"{len(manifest['files'])} hashed files"
        )
        return 0
    except (ValidationError, ValueError) as exc:
        print(f"portfolio contract error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
