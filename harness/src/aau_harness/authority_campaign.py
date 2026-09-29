"""Bounded sequential staging runs with per-run evidence retained."""

from pathlib import Path

from .agent_bom import AgentBomError, generate_conformance_suite, load_json, rendered, write_json
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
    write_json(campaign_completion(report), out / "completion.json")
    return report


def campaign_completion(report: dict) -> dict:
    return {
        "version": "aau-authority-campaign/1.0", "requested_runs": report["receipt_count"],
        "completed_runs": report["receipt_count"], "status": report["status"],
        "receipt_sha256s": report["receipt_sha256s"],
        "boundary": "Sequential local synthetic checks; no independent-execution attestation, statistical reliability estimate, or production authorization.",
    }


def verify_campaign(directory: Path, adapter: Path, workspace: Path) -> dict:
    if directory.is_symlink() or not directory.is_dir():
        raise AgentBomError("campaign must be a real directory")
    for name in ("completion.json", "repeatability.json"):
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
            raise AgentBomError(f"invalid campaign file: {name}")
    marker = load_json(directory / "completion.json")
    runs = marker.get("requested_runs")
    if type(runs) is not int or not 2 <= runs <= 10:
        raise AgentBomError("campaign run count must be 2 to 10")
    names = [f"run-{index + 1:03d}" for index in range(runs)]
    if {path.name for path in directory.iterdir()} != set(names) | {"completion.json", "repeatability.json"}:
        raise AgentBomError("campaign directory file set is incomplete or unexpected")
    receipts = []
    for name in names:
        verify_check(directory / name, adapter, workspace)
        receipts.append(load_json(directory / name / "receipt.json"))
    bom = load_json(directory / names[0] / "inventory.json")
    suite = load_json(directory / names[0] / "suite.json")
    report = assess_repeatability(receipts, bom, suite, adapter, workspace)
    if rendered(marker) != rendered(campaign_completion(report)):
        raise AgentBomError("campaign completion marker does not recompute")
    if rendered(load_json(directory / "repeatability.json")) != rendered(report):
        raise AgentBomError("campaign repeatability report does not recompute")
    return report
