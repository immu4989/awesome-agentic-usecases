"""One portable handoff from two scored CSV exports to a fully recomputable review."""

import argparse
import json
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered
from .eval_csv import FILES as CSV_FILES, _read_source, csv_payloads
from .eval_pack import pack_payloads


REVIEW_FILES = {"policy.json", "baseline.json", "candidate.json", "review.json", "review.html", "manifest.json",
                "baseline-recording.json", "candidate-recording.json", "diagnostics.json",
                "baseline-repeatability.json", "candidate-repeatability.json",
                "baseline-operations.json", "candidate-operations.json"}
GROUPS = {"baseline": CSV_FILES, "candidate": CSV_FILES, "review": REVIEW_FILES}
ROOT_FILES = {"handoff.json", "README.txt", "manifest.json"}
GUIDE = """AAU CSV evaluation handoff

Open review/review.html for the policy review and repeatability/cost diagnostics.
The page is self-contained and script-free. It does not verify itself.
Using the same harness version, verify the entire folder from its parent:

  aau csv-review verify PATH_TO_THIS_FOLDER

Exit 0: the complete source chain verifies and supplied policy constraints are met.
Exit 1: the complete source chain verifies but supplied policy constraints are NOT met.
Exit 2: invalid inputs, incomplete evidence, or a verification error.
Never treat a nonzero exit as a passing review or delete failure evidence automatically.

Retain all 28 files, including both original source.csv files and their column maps.
Verification reparses both CSV exports and recomputes the recordings, evaluations,
policy review, diagnostics, HTML, handoff report, and manifests. It rejects a valid
but unrelated review folder, not just corrupt individual files. Review the mapping,
scenario scope, policy limits, diagnostic criteria, and declared measurement units.

This is supplied evidence, not original execution, independently verified scores,
signatures, policy precommitment, certification, an ATO, or deployment approval.
Missing context stays missing; missing measurements stay unknown. Hashes are not
signatures: coordinated replacement of sources and outputs can still verify.

NOT SANITIZED: review every file before sharing. Identifiers and original CSV bytes
may contain sensitive data or spreadsheet formulas. Do not open untrusted CSV files
in spreadsheet software. The tool does not run agents, upload data, or call models.
An interrupted folder is not complete evidence; verification must succeed first.
"""


def handoff_payloads(policy: dict, baseline_plan: dict, baseline_csv: bytes,
                     candidate_plan: dict, candidate_csv: bytes, diagnostics: dict) -> tuple[dict, dict[str, bytes]]:
    if diagnostics is None:
        raise AgentBomError("CSV handoff requires an explicit diagnostics plan")
    payloads, recordings, sources = {}, [], {}
    for side, plan, raw in (("baseline", baseline_plan, baseline_csv), ("candidate", candidate_plan, candidate_csv)):
        conversion, files = csv_payloads(plan, raw)
        payloads.update({f"{side}/{name}": value for name, value in files.items()})
        recordings.append(json.loads(files["recording.json"]))
        sources[side] = {key: conversion[key] for key in (
            "source_csv_sha256", "plan_sha256", "recording_sha256", "evaluation_sha256",
            "observation_count", "scenario_count", "unreported_metrics", "metric_coverage", "operating_coverage")}
    review, files = pack_payloads(policy, *recordings, recordings=True, diagnostics=diagnostics)
    payloads.update({f"review/{name}": value for name, value in files.items()})
    report = {"report_version": "aau-csv-evaluation-handoff/1.0", "status": review["status"],
              "policy_sha256": digest(policy), "diagnostics_sha256": digest(diagnostics),
              "review_sha256": digest(review), "sources": sources,
              "boundary": "Full source-to-report recomputation of supplied scored exports, not execution, verified scoring, authenticity, policy timing, certification, or deployment approval. No source sanitization. Missing context and operating measurements are not fabricated."}
    payloads["handoff.json"] = rendered(report)
    payloads["README.txt"] = GUIDE.encode("utf-8")
    payloads["manifest.json"] = rendered({"pack_version": "aau-csv-evaluation-handoff-pack/1.0",
        "files": {name: digest(value) for name, value in sorted(payloads.items())}})
    if any(len(value) > MAX_JSON_BYTES for value in payloads.values()):
        raise AgentBomError("CSV handoff member exceeds 2 MB")
    return report, payloads


def create_handoff(policy: dict, baseline_plan: dict, baseline_csv: bytes, candidate_plan: dict,
                   candidate_csv: bytes, diagnostics: dict, directory: Path) -> dict:
    if directory.exists() or directory.is_symlink():
        raise AgentBomError("refusing to overwrite an existing CSV handoff destination")
    report, payloads = handoff_payloads(policy, baseline_plan, baseline_csv, candidate_plan, candidate_csv, diagnostics)
    directory.mkdir(parents=True, exist_ok=False)
    for group in GROUPS:
        (directory / group).mkdir()
    for name, value in payloads.items():
        with (directory / name).open("xb") as stream:
            stream.write(value)  # Root manifest last: incomplete handoffs cannot verify.
    return report


def verify_handoff(directory: Path) -> dict:
    if (directory.is_symlink() or not directory.is_dir()
            or {path.name for path in directory.iterdir()} != ROOT_FILES | set(GROUPS)):
        raise AgentBomError("CSV handoff requires the exact root file and directory set")
    paths = [directory / name for name in ROOT_FILES]
    for group, names in GROUPS.items():
        folder = directory / group
        if (folder.is_symlink() or not folder.is_dir()
                or {path.name for path in folder.iterdir()} != names):
            raise AgentBomError(f"CSV handoff requires the exact member set: {group}")
        paths.extend(folder / name for name in names)
    for path in paths:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise AgentBomError("CSV handoff members must be regular non-symlink files within 2 MB")
    report, expected = handoff_payloads(
        load_json(directory / "review/policy.json"), load_json(directory / "baseline/plan.json"),
        _read_source(directory / "baseline/source.csv"), load_json(directory / "candidate/plan.json"),
        _read_source(directory / "candidate/source.csv"), load_json(directory / "review/diagnostics.json"))
    for name, value in expected.items():
        if (directory / name).read_bytes() != value:
            raise AgentBomError(f"CSV handoff member does not recompute: {name}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau csv-review", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    for name in ("policy", "baseline_plan", "baseline_csv", "candidate_plan", "candidate_csv"):
        create.add_argument(name, type=Path)
    create.add_argument("--diagnostics", type=Path, required=True)
    create.add_argument("--out", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            create_handoff(load_json(args.policy), load_json(args.baseline_plan), _read_source(args.baseline_csv),
                           load_json(args.candidate_plan), _read_source(args.candidate_csv),
                           load_json(args.diagnostics), args.out)
            report = verify_handoff(args.out)
        else:
            report = verify_handoff(args.directory)
        print(f"CSV handoff verified: {report['status']}; all 28 files recomputed. Not deployment approval.")
        return 0 if report["status"] == "constraints_met" else 1
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
