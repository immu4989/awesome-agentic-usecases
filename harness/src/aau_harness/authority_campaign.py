"""Bounded sequential staging runs with per-run evidence retained."""

from pathlib import Path

from .agent_bom import AgentBomError, generate_conformance_suite, load_json, ordered_authority_cases, rendered, write_json
from .authority_check import check_authority, verify_check
from .authority_repeatability import assess_repeatability
from .authority_plan import plan_authority


def repeat_authority(bom: dict, command: str, adapter: Path, workspace: Path,
                     out: Path, runs: int = 3, timeout: float = 10.0,
                     order_seeds: list[int] | None = None,
                     max_invocations: int | None = None) -> dict:
    if type(runs) is not int or not 2 <= runs <= 10:
        raise AgentBomError("repeated staging checks require 2 to 10 runs")
    if out.exists() or out.is_symlink():
        raise AgentBomError(f"refusing to overwrite: {out}")
    plan = plan_authority(bom, runs, timeout, max_invocations)
    if plan["status"] == "over_budget":
        raise AgentBomError(f"campaign requires {plan['planned_adapter_invocations']} adapter invocations; budget is {max_invocations}")
    suite = generate_conformance_suite(bom)
    if order_seeds is not None:
        validate_schedule(order_seeds, runs, suite)
    receipts = []
    for index in range(runs):
        destination = out / f"run-{index + 1:03d}"
        # Behavioral failure returns a report, not an exception: collect all runs.
        check_authority(bom, command, adapter, workspace, destination, timeout,
                        None if order_seeds is None else order_seeds[index])
        verify_check(destination, adapter, workspace)
        receipts.append(load_json(destination / "receipt.json"))
    report = assess_repeatability(receipts, bom, suite, adapter, workspace)
    write_json(report, out / "repeatability.json")
    write_json(campaign_completion(report, order_seeds), out / "completion.json")
    return report


def validate_schedule(seeds: list[int], runs: int, suite: dict) -> None:
    if not isinstance(seeds, list) or len(seeds) != runs or any(type(seed) is not int for seed in seeds):
        raise AgentBomError("order seed schedule must contain one integer per run")
    for seed in seeds:
        ordered_authority_cases(suite, seed)


def campaign_completion(report: dict, order_seeds: list[int] | None = None) -> dict:
    marker = {
        "version": "aau-authority-campaign/1.0", "requested_runs": report["receipt_count"],
        "completed_runs": report["receipt_count"], "status": report["status"],
        "receipt_sha256s": report["receipt_sha256s"],
        "boundary": "Sequential local synthetic checks; no independent-execution attestation, statistical reliability estimate, or production authorization.",
    }
    if order_seeds is not None:
        marker.update(version="aau-authority-campaign/1.1", order_seeds=order_seeds)
    return marker


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
    seeds = None
    if marker.get("version") == "aau-authority-campaign/1.1":
        seeds = marker.get("order_seeds")
        validate_schedule(seeds, runs, suite)
        for seed, receipt in zip(seeds, receipts):
            expected_order = [case["case_id"] for case in ordered_authority_cases(suite, seed)]
            if [row["case_id"] for row in receipt["results"]] != expected_order:
                raise AgentBomError("campaign recorded case order does not match seed schedule")
    report = assess_repeatability(receipts, bom, suite, adapter, workspace)
    if rendered(marker) != rendered(campaign_completion(report, seeds)):
        raise AgentBomError("campaign completion marker does not recompute")
    if rendered(load_json(directory / "repeatability.json")) != rendered(report):
        raise AgentBomError("campaign repeatability report does not recompute")
    return report
