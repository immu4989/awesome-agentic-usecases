"""Explain recorded authority mismatches without retaining request payloads."""

from pathlib import Path

from .agent_bom import digest, verify_conformance_receipt


def explain_conformance(receipt: dict, bom: dict, suite: dict,
                        adapter_artifact: Path | None = None,
                        workspace: Path | None = None) -> dict:
    verify_conformance_receipt(receipt, bom, suite, adapter_artifact, workspace)
    expected = {row["case_id"]: row for row in suite["cases"]}
    mismatches = []
    counts = {"unsafe_allow": 0, "legitimate_block": 0, "reason_mismatch": 0}
    for row in receipt["results"]:
        if row["exact"]:
            continue
        case = expected[row["case_id"]]
        if row["actual_decision"] != case["expected_decision"]:
            category = "unsafe_allow" if row["actual_decision"] == "allow" else "legitimate_block"
        else:
            category = "reason_mismatch"
        counts[category] += 1
        mismatches.append({
            "case_id": row["case_id"], "shape": case["shape"], "category": category,
            "expected_decision": case["expected_decision"],
            "actual_decision": row["actual_decision"],
            "missing_reason_codes": sorted(set(case["expected_reason_codes"]) - set(row["actual_reason_codes"])),
            "unexpected_reason_codes": sorted(set(row["actual_reason_codes"]) - set(case["expected_reason_codes"])),
        })
    return {
        "report_version": "aau-authority-failure-report/1.0",
        "receipt_sha256": digest(receipt), "bom_sha256": digest(bom),
        "suite_sha256": digest(suite), "status": receipt["status"],
        "adapter_kind": receipt["adapter_kind"],
        "adapter_bytes_checked": adapter_artifact is not None,
        "case_count": receipt["metrics"]["case_count"],
        "exact_count": receipt["metrics"]["exact_count"],
        "mismatch_count": len(mismatches), "categories": counts,
        "mismatches": sorted(mismatches, key=lambda item: item["case_id"]),
        "boundary": "Explains recorded synthetic evidence; does not rerun the adapter or authorize deployment.",
    }


def compare_conformance(before: dict, after: dict, bom: dict, suite: dict,
                        before_artifact: Path | None = None,
                        after_artifact: Path | None = None,
                        workspace: Path | None = None) -> dict:
    """Compare verified receipts against one identical inventory and test suite."""
    baseline = explain_conformance(before, bom, suite, before_artifact, workspace)
    candidate = explain_conformance(after, bom, suite, after_artifact, workspace)
    old = {row["case_id"]: row for row in baseline["mismatches"]}
    new = {row["case_id"]: row for row in candidate["mismatches"]}
    transitions = []
    counts = {"introduced": 0, "resolved": 0, "changed_failure": 0, "persistent": 0}
    for case_id in sorted(old.keys() | new.keys()):
        prior, current = old.get(case_id), new.get(case_id)
        if prior is None:
            change = "introduced"
        elif current is None:
            change = "resolved"
        elif prior != current:
            change = "changed_failure"
        else:
            change = "persistent"
        counts[change] += 1
        transitions.append({"case_id": case_id, "change": change,
                            "before": prior, "after": current})
    return {
        "report_version": "aau-authority-comparison/1.0",
        "bom_sha256": digest(bom), "suite_sha256": digest(suite),
        "before": {key: baseline[key] for key in (
            "receipt_sha256", "status", "adapter_kind", "adapter_bytes_checked",
            "case_count", "exact_count", "categories")},
        "after": {key: candidate[key] for key in (
            "receipt_sha256", "status", "adapter_kind", "adapter_bytes_checked",
            "case_count", "exact_count", "categories")},
        "transitions": transitions, "counts": counts,
        "status": candidate["status"],
        "boundary": "Compares recorded synthetic evidence on identical inputs; no rerun, causal attribution, or deployment approval.",
    }
