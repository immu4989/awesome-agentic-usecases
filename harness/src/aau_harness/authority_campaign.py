"""Bounded sequential staging runs with per-run evidence retained."""

from pathlib import Path

from .agent_bom import AgentBomError, generate_conformance_suite, load_json, write_json
from .authority_check import check_authority, verify_check
from .authority_repeatability import assess_repeatability


def repeat_authority(bom: dict, command: str, adapter: Path, workspace: Path,
                     out: Path, runs: int = 3, timeout: float = 10.0) -> dict:
    if type(runs) is not int or not 2 <= runs <= 10:
        raise AgentBomError("repeated staging checks require 2 to 10 runs")
    if out.exists() or out.is_symlink():
        raise AgentBomError(f"refusing to overwrite: {out}")
    suite = generate_conformance_suite(bom)
    receipts = []
    for index in range(runs):
        destination = out / f"run-{index + 1:03d}"
        # Behavioral failure returns a report, not an exception: collect all runs.
        check_authority(bom, command, adapter, workspace, destination, timeout)
        verify_check(destination, adapter, workspace)
        receipts.append(load_json(destination / "receipt.json"))
    report = assess_repeatability(receipts, bom, suite, adapter, workspace)
    write_json(report, out / "repeatability.json")
    write_json({
        "version": "aau-authority-campaign/1.0", "requested_runs": runs,
        "completed_runs": len(receipts), "status": report["status"],
        "receipt_sha256s": report["receipt_sha256s"],
        "boundary": "Sequential local synthetic checks; no independent-execution attestation, statistical reliability estimate, or production authorization.",
    }, out / "completion.json")
    return report
