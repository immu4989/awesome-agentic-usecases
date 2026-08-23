from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest


KIT = Path(__file__).resolve().parents[1]
ROOT = KIT.parent
SPEC = importlib.util.spec_from_file_location(
    "aau_portfolio", KIT / "aau_portfolio.py"
)
portfolio = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(portfolio)


def load(name: str) -> dict:
    return json.loads((KIT / "examples" / name).read_text())


@pytest.fixture
def inventory() -> dict:
    return load("synthetic-agency-inventory.json")


@pytest.fixture
def ledger() -> dict:
    return load("public-value-ledger.json")


@pytest.fixture
def tevv() -> dict:
    return load("three-layer-tev-v-plan.json")


@pytest.fixture
def clauses() -> dict:
    return load("clause-testbench.json")


@pytest.fixture
def sources() -> dict:
    return json.loads((KIT / "sources.json").read_text())


def test_all_public_contracts_validate(
    inventory, ledger, tevv, clauses, sources
):
    portfolio.validate_inventory(inventory)
    portfolio.validate_public_value(ledger, inventory)
    portfolio.validate_tev_v(tevv, inventory)
    portfolio.validate_clauses(clauses)
    portfolio.validate_sources(sources)


def test_analysis_keeps_gaps_and_overlap_visible(inventory):
    result = portfolio.analyze_inventory(
        inventory,
        json.loads((ROOT / "docs/use-cases.json").read_text()),
    )
    assert result["summary"] == {
        "use_cases": 6,
        "documented": 4,
        "needs_evidence": 2,
        "critical_gaps": 5,
        "important_gaps": 2,
        "possible_overlaps": 1,
        "estimated_annual_cost_usd": 1_915_000,
        "unknown_costs": 1,
    }
    assert (
        result["possible_overlaps"][0]["disposition"]
        == "human-review-required"
    )
    assert set(result["decisions"].values()) == {"not-produced"}


def test_possible_overlap_never_claims_duplication(inventory):
    result = portfolio.analyze_inventory(inventory)
    overlap = result["possible_overlaps"][0]
    assert "not proof of duplication" in overlap["boundary"]
    assert "recommendation" in overlap["boundary"]


def test_empty_owner_is_a_gap_not_schema_failure(inventory):
    portfolio.validate_inventory(inventory)
    item = next(
        item
        for item in inventory["use_cases"]
        if item["use_case_id"] == "meeting-summary-assistant"
    )
    codes = {
        issue["code"] for issue in portfolio.quality_issues(item)
    }
    assert {
        "missing-owner",
        "missing-benefit",
        "missing-performance-metric",
    } <= codes


def test_unknown_strategic_goal_is_rejected(inventory):
    inventory["use_cases"][0]["strategic_goal_ids"] = ["goal-not-real"]
    with pytest.raises(
        portfolio.ValidationError, match="unknown strategic goals"
    ):
        portfolio.validate_inventory(inventory)


def test_duplicate_use_case_id_is_rejected(inventory):
    inventory["use_cases"][1]["use_case_id"] = inventory["use_cases"][0][
        "use_case_id"
    ]
    with pytest.raises(
        portfolio.ValidationError, match="use case ids must be unique"
    ):
        portfolio.validate_inventory(inventory)


def test_nonpublic_sharing_is_rejected(inventory):
    inventory["sharing"][
        "contains_controlled_unclassified_information"
    ] = True
    with pytest.raises(portfolio.ValidationError, match="must be false"):
        portfolio.validate_inventory(inventory)


def test_sensitive_scan_omits_matched_value():
    secret = "AKIAABCDEFGHIJKLMNOP"
    result = portfolio.scan_sensitive({"credential": secret})
    assert result["finding_count"] == 1
    assert secret not in json.dumps(result)
    assert result["matched_values_included"] is False


def test_public_value_changes_are_bounded(ledger, inventory):
    result = portfolio.assess_public_value(ledger, inventory)
    measured = result["records"][0]
    assert measured["minutes_per_case_change"] == -4.5
    assert measured["error_rate_change"] == -0.04
    assert measured["verified_savings_claim"] is False
    assert result["summary"]["baseline_only"] == 1


def test_verified_savings_claim_is_rejected(ledger):
    ledger["records"][0]["claims_verified_savings"] = True
    with pytest.raises(
        portfolio.ValidationError, match="must remain false"
    ):
        portfolio.validate_public_value(ledger)


def test_three_layers_are_required(tevv):
    tevv["layers"] = tevv["layers"][:2]
    with pytest.raises(portfolio.ValidationError, match="at least 3"):
        portfolio.validate_tev_v(tevv)


def test_field_layer_requires_participants(tevv):
    field = next(
        item
        for item in tevv["layers"]
        if item["layer"] == "field_simulation"
    )
    field["participant_roles"] = []
    with pytest.raises(
        portfolio.ValidationError, match="participant_roles"
    ):
        portfolio.validate_tev_v(tevv)


def test_clause_library_covers_every_area(clauses):
    result = portfolio.clause_coverage(clauses)
    assert result["areas"] == 7
    assert all(
        item["structurally_testable"] for item in result["clauses"]
    )
    assert result["legal_conclusion"] is False


def test_clause_missing_area_is_rejected(clauses):
    clauses["clauses"] = clauses["clauses"][:-1]
    with pytest.raises(
        portfolio.ValidationError, match="must cover all areas"
    ):
        portfolio.validate_clauses(clauses)


def test_policy_drift_is_date_explicit(sources):
    current = portfolio.policy_drift(sources, date(2026, 8, 23))
    due = portfolio.policy_drift(sources, date(2026, 11, 24))
    assert current["current"] == 8
    assert current["review_due"] == 0
    assert due["review_due"] == 8


def test_pack_is_deterministic_and_verifiable(
    tmp_path, inventory, ledger, tevv, clauses, sources
):
    catalog = json.loads((ROOT / "docs/use-cases.json").read_text())
    first = portfolio.build_pack(
        inventory, ledger, tevv, clauses, sources, catalog
    )
    second = portfolio.build_pack(
        inventory, ledger, tevv, clauses, sources, catalog
    )
    assert first == second
    out = tmp_path / "pack"
    portfolio.write_pack(first, out)
    manifest = portfolio.verify_pack(out)
    assert manifest["manifest_version"] == portfolio.PACK_VERSION
    assert len(manifest["files"]) == 7
    assert manifest["claims"]["investment_recommendation"] is False


def test_pack_tamper_is_detected(
    tmp_path, inventory, ledger, tevv, clauses, sources
):
    catalog = json.loads((ROOT / "docs/use-cases.json").read_text())
    out = tmp_path / "pack"
    portfolio.write_pack(
        portfolio.build_pack(
            inventory, ledger, tevv, clauses, sources, catalog
        ),
        out,
    )
    (out / "portfolio-analysis.json").write_text("{}\n")
    with pytest.raises(
        portfolio.ValidationError,
        match="byte count differs|digest differs",
    ):
        portfolio.verify_pack(out)


def test_pack_blocks_sensitive_material(
    inventory, ledger, tevv, clauses, sources
):
    inventory["use_cases"][0]["mission"] = "Contact reviewer@example.gov"
    with pytest.raises(
        portfolio.ValidationError, match="sensitive-data"
    ):
        portfolio.build_pack(
            inventory, ledger, tevv, clauses, sources, []
        )


def test_unsafe_pack_path_is_rejected():
    with pytest.raises(
        portfolio.ValidationError, match="unsafe pack path"
    ):
        portfolio.safe_pack_path("../manifest.json")


def test_cli_analyze_and_verify_pack(
    tmp_path, inventory, ledger, tevv, clauses
):
    inventory_path = tmp_path / "inventory.json"
    ledger_path = tmp_path / "ledger.json"
    tevv_path = tmp_path / "tevv.json"
    clauses_path = tmp_path / "clauses.json"
    for path, value in (
        (inventory_path, inventory),
        (ledger_path, ledger),
        (tevv_path, tevv),
        (clauses_path, clauses),
    ):
        path.write_text(json.dumps(value))
    assert portfolio.main(["analyze", str(inventory_path)]) == 0
    out = tmp_path / "pack"
    assert (
        portfolio.main(
            [
                "pack",
                str(inventory_path),
                str(ledger_path),
                str(tevv_path),
                str(clauses_path),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    assert portfolio.main(["verify-pack", str(out)]) == 0
