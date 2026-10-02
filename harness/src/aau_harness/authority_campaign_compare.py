"""Compare verified campaign observations, without estimating causal release effects."""

from collections import Counter
from pathlib import Path

from .agent_bom import AgentBomError, digest, load_json
from .authority_campaign import verify_campaign


def _observations(receipts: list[dict], case: dict) -> dict:
    rows = [next(row for row in receipt["results"] if row["case_id"] == case["case_id"])
            for receipt in receipts]
    variants = Counter((row["actual_decision"], tuple(row["actual_reason_codes"])) for row in rows)
    return {
        "exact": sum(row["exact"] for row in rows),
        "unsafe_allow": sum(row["actual_decision"] == "allow" and case["expected_decision"] == "block" for row in rows),
        "legitimate_block": sum(row["actual_decision"] == "block" and case["expected_decision"] == "allow" for row in rows),
        "reason_mismatch": sum(row["actual_reason_codes"] != case["expected_reason_codes"] for row in rows),
        "unstable": len(variants) > 1,
        "variants": [{"decision": decision, "reason_codes": list(reasons), "count": count}
                     for (decision, reasons), count in sorted(variants.items())],
    }


def compare_campaigns(before: Path, after: Path, before_adapter: Path, after_adapter: Path,
                      before_workspace: Path, after_workspace: Path) -> dict:
    """Reverify both folders and require matched workload and recorded execution order."""
    reports = [verify_campaign(before, before_adapter, before_workspace),
               verify_campaign(after, after_adapter, after_workspace)]
    old, new = reports
    for key in ("bom_sha256", "suite_sha256", "receipt_count"):
        if old[key] != new[key]:
            raise AgentBomError(f"campaign comparison requires matching {key}")
    runs = old["receipt_count"]
    groups = [[load_json(directory / f"run-{index + 1:03d}" / "receipt.json")
               for index in range(runs)] for directory in (before, after)]
    for left, right in zip(*groups):
        if [row["case_id"] for row in left["results"]] != [row["case_id"] for row in right["results"]]:
            raise AgentBomError("campaign comparison requires matching case order for each run")
    suite = load_json(before / "run-001" / "suite.json")
    counts = dict.fromkeys(("introduced_failure", "resolved_failure", "increased_unsafe_allow",
                           "decreased_unsafe_allow", "gained_instability", "lost_instability",
                           "changed_observations", "unchanged_observations"), 0)
    findings = []
    for case in sorted(suite["cases"], key=lambda row: row["case_id"]):
        left, right = [_observations(group, case) for group in groups]
        flags = {
            "introduced_failure": left["exact"] == runs and right["exact"] < runs,
            "resolved_failure": left["exact"] < runs and right["exact"] == runs,
            "increased_unsafe_allow": right["unsafe_allow"] > left["unsafe_allow"],
            "decreased_unsafe_allow": right["unsafe_allow"] < left["unsafe_allow"],
            "gained_instability": not left["unstable"] and right["unstable"],
            "lost_instability": left["unstable"] and not right["unstable"],
            "changed_observations": left != right,
            "unchanged_observations": left == right,
        }
        for name, value in flags.items():
            counts[name] += int(value)
        # Retain persistent failures: unchanged is not a passing release gate.
        if left != right or right["exact"] < runs:
            findings.append({"case_id": case["case_id"], "shape": case["shape"],
                             "changes": [name for name, value in flags.items() if value],
                             "before": left, "after": right})
    return {
        "report_version": "aau-authority-campaign-comparison/1.0",
        "bom_sha256": old["bom_sha256"], "suite_sha256": old["suite_sha256"],
        "runs_per_campaign": runs, "case_count": len(suite["cases"]),
        "before": {"repeatability_sha256": digest(old), "receipt_sha256s": old["receipt_sha256s"],
                   "adapter_artifact": groups[0][0]["adapter_artifact"], "counts": old["counts"]},
        "after": {"repeatability_sha256": digest(new), "receipt_sha256s": new["receipt_sha256s"],
                  "adapter_artifact": groups[1][0]["adapter_artifact"], "counts": new["counts"]},
        "counts": counts, "findings": findings, "status": new["status"],
        "boundary": "Verified synthetic observations with matched inventory, suite, run count, and recorded case order. Counts overlap and describe observations, not statistical significance or causal release effects. External state, dependencies, model settings, and independent execution are not bound. No production authorization.",
    }
