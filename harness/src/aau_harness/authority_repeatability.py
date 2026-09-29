"""Assess observed consistency without claiming independent executions or reliability."""

from collections import Counter
from pathlib import Path

from .agent_bom import AgentBomError, digest, rendered, verify_conformance_receipt


def assess_repeatability(receipts: list[dict], bom: dict, suite: dict,
                         adapter: Path | None = None, workspace: Path | None = None) -> dict:
    if not 2 <= len(receipts) <= 20:
        raise AgentBomError("repeatability requires 2 to 20 receipts")
    for receipt in receipts:
        verify_conformance_receipt(receipt, bom, suite, adapter, workspace)
    first = receipts[0]
    identity = (first["adapter_kind"], rendered(first["adapter_artifact"]))
    if any((row["adapter_kind"], rendered(row["adapter_artifact"])) != identity for row in receipts):
        raise AgentBomError("repeatability requires the same adapter kind and artifact binding")
    rows = [{row["case_id"]: row for row in receipt["results"]} for receipt in receipts]
    findings = []
    counts = {"stable_pass": 0, "stable_failure": 0, "unstable": 0}
    for case in sorted(suite["cases"], key=lambda item: item["case_id"]):
        observations = [run[case["case_id"]] for run in rows]
        variants = Counter((row["actual_decision"], tuple(row["actual_reason_codes"]))
                           for row in observations)
        exact_count = sum(row["exact"] for row in observations)
        state = ("unstable" if len(variants) > 1 else
                 "stable_pass" if exact_count == len(receipts) else "stable_failure")
        counts[state] += 1
        if state != "stable_pass":
            findings.append({
                "case_id": case["case_id"], "shape": case["shape"], "state": state,
                "exact_observation_count": exact_count,
                "variants": [{"decision": decision, "reason_codes": list(reasons), "count": count}
                             for (decision, reasons), count in sorted(variants.items())],
            })
    hashes = sorted(digest(receipt) for receipt in receipts)
    return {
        "report_version": "aau-authority-repeatability/1.0",
        "bom_sha256": digest(bom), "suite_sha256": digest(suite),
        "receipt_sha256s": hashes, "receipt_count": len(receipts),
        "distinct_receipt_count": len(set(hashes)),
        "adapter_kind": first["adapter_kind"], "adapter_bytes_checked": adapter is not None,
        "case_count": len(suite["cases"]), "counts": counts, "findings": findings,
        "status": "evidence_passed" if counts["stable_pass"] == len(suite["cases"]) else "evidence_failed",
        "boundary": "Describes supplied synthetic observations only. Identical receipts may be copies or genuine repeats; independent execution, statistical reliability, and production safety are not established.",
    }
