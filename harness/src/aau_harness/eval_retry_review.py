"""Bind both retry ledgers and their accounting plans to one complete evaluation review."""

import argparse
import json
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered
from .eval_csv_review import BUDGET_FILES, REVIEW_FILES, ROOT_FILES
from .eval_pack import pack_payloads
from .eval_retries import FILES as RETRY_FILES, retry_payloads


GROUPS = {"baseline": RETRY_FILES, "candidate": RETRY_FILES, "review": REVIEW_FILES}
GUIDE = """AAU retry evaluation handoff

Open review/review.html for policy checks and logical-task operating diagnostics.
The page is self-contained and script-free. It does not verify itself. Using the
same trusted harness, verify the entire folder from its parent:

  aau retry-review verify PATH_TO_THIS_FOLDER

Exit 0: complete source chain verifies and supplied policy constraints are met.
Exit 1: complete source chain verifies but supplied policy constraints are NOT met.
Exit 2: invalid inputs, incomplete evidence, or failed verification.

Retain all 28 files. Baseline and candidate each contain their accounting plan,
complete declared retry ledger, recording, evaluation, accounting report, and
manifest. Review contains both derived recordings, policy, diagnostics, and all
derived review files. The outer report, guide, and manifest bind all three folders.
Verification recomputes from both ledgers, not just hashes or standalone reviews.
An individually valid but unrelated nested review cannot replace this source chain.

Each observation is one logical task, not a transport call. Both plans must use
identical metric reducers and sequential_disjoint scope. Last-only metrics can
hide earlier harm; inspect both accounting reports, not only final task scores.
Attempts are not independently executed repeats. No retry is run or authorized.
Costs include every declared attempt only when coverage is complete. Whole-task
latency must be supplied separately; missing measurements remain unknown.

Inspect and independently approve plans, source census, reducers, scoring context,
policy and diagnostic definitions. CLI review can disclose absent context, while
the GitHub Action requires matching declared context and independent approval pins.
Hashes do not establish execution, authenticity, precommitment, scoring validity,
complete external collection, invoice accuracy, or deployment approval. Coordinated
replacement can verify. Both JSON ledgers retain values, not original file bytes.

NOT SANITIZED: all identifiers and source values may be sensitive. Inspect before
sharing. No uploads, model calls, credential use, or automated retries occur.
Interrupted folders are not complete evidence; verification must succeed first.
"""


def handoff_payloads(policy: dict, baseline_plan: dict, baseline_ledger: dict,
                     candidate_plan: dict, candidate_ledger: dict, diagnostics: dict, *,
                     operating_budget: dict | None = None) -> tuple[dict, dict[str, bytes]]:
    if diagnostics is None:
        raise AgentBomError("retry handoff requires an explicit diagnostics plan")
    payloads, recordings, sources = {}, [], {}
    for side, plan, ledger in (("baseline", baseline_plan, baseline_ledger), ("candidate", candidate_plan, candidate_ledger)):
        accounting, files = retry_payloads(plan, ledger)
        payloads.update({f"{side}/{name}": value for name, value in files.items()})
        recordings.append(json.loads(files["recording.json"]))
        sources[side] = {key: accounting[key] for key in (
            "plan_sha256", "ledger_sha256", "recording_sha256", "evaluation_sha256", "task_count",
            "attempt_count", "retry_count", "tasks_with_retries", "last_only_metrics", "unreported_task_metrics")}
    # Equal context hashes are declarations, not proof that accounting definitions match.
    if any(baseline_plan[key] != candidate_plan[key] for key in ("metric_reducers", "attempt_scope")):
        raise AgentBomError("retry handoff requires identical metric reducers and attempt scope on both plans")
    outcome, files = pack_payloads(policy, *recordings, recordings=True, diagnostics=diagnostics,
                                   operating_budget=operating_budget)
    payloads.update({f"review/{name}": value for name, value in files.items()})
    report = {"report_version": "aau-retry-evaluation-handoff/1.0", "status": outcome["status"],
              "policy_sha256": digest(policy), "diagnostics_sha256": digest(diagnostics),
              "review_sha256": digest(json.loads(files["review.json"])), "sources": sources,
              "unit": "logical_task_per_scenario_repeat",
              "boundary": "Full recomputation from declared sequential retry ledgers with equal explicit metric reducers, not execution, authenticated completeness, policy approval, or safe retry authorization. Last-only metrics may hide earlier failures. Missing context and operating measurements are not fabricated. No sanitization. Hashes are not signatures."}
    guide = GUIDE
    if operating_budget is not None:
        report.update(report_version="aau-retry-evaluation-handoff/1.1", gate_sha256=digest(outcome),
                      operating_budget_sha256=digest(operating_budget), policy_status=outcome["policy_status"],
                      candidate_budget_status=outcome["candidate_budget_status"])
        guide = (GUIDE.replace("28 files", "31 files").replace("supplied policy constraints", "combined policy and candidate budget constraints")
                 .replace("are NOT met.", "are NOT met or not verified.")
                 + "\nThis handoff includes the candidate operating budget and combined gate. Both policy\n"
                 "and budget must be met independently. Missing required budget evidence cannot pass.\n"
                 "Reject a missing budget layer with: aau retry-review verify PATH_TO_THIS_FOLDER --require-budget\n")
    payloads["handoff.json"] = rendered(report)
    payloads["README.txt"] = guide.encode("utf-8")
    payloads["manifest.json"] = rendered({
        "pack_version": "aau-retry-evaluation-handoff-pack/1.1" if operating_budget is not None else "aau-retry-evaluation-handoff-pack/1.0",
        "files": {name: digest(value) for name, value in sorted(payloads.items())}})
    if any(len(value) > MAX_JSON_BYTES for value in payloads.values()):
        raise AgentBomError("retry handoff member exceeds 2 MB")
    return report, payloads


def create_handoff(policy: dict, baseline_plan: dict, baseline_ledger: dict, candidate_plan: dict,
                   candidate_ledger: dict, diagnostics: dict, directory: Path, *, operating_budget: dict | None = None) -> dict:
    if directory.exists() or directory.is_symlink():
        raise AgentBomError("refusing to overwrite retry handoff destination")
    report, payloads = handoff_payloads(policy, baseline_plan, baseline_ledger, candidate_plan, candidate_ledger,
                                       diagnostics, operating_budget=operating_budget)
    directory.mkdir(parents=True, exist_ok=False)
    for group in GROUPS:
        (directory / group).mkdir()
    for name, value in payloads.items():
        with (directory / name).open("xb") as stream:
            stream.write(value)  # Root manifest last: incomplete handoffs cannot verify.
    return report


def verify_handoff(directory: Path, *, require_budget: bool = False) -> dict:
    if (directory.is_symlink() or not directory.is_dir()
            or {path.name for path in directory.iterdir()} != ROOT_FILES | set(GROUPS)):
        raise AgentBomError("retry handoff requires the exact root file and directory set")
    version = load_json(directory / "manifest.json").get("pack_version")
    if version not in ("aau-retry-evaluation-handoff-pack/1.0", "aau-retry-evaluation-handoff-pack/1.1"):
        raise AgentBomError("unsupported retry handoff version")
    budget = version == "aau-retry-evaluation-handoff-pack/1.1"
    if require_budget and not budget:
        raise AgentBomError("operating budget gate required; ungated retry handoff refused")
    paths = [directory / name for name in ROOT_FILES]
    for group, names in GROUPS.items():
        if budget and group == "review":
            names = names | BUDGET_FILES
        folder = directory / group
        if folder.is_symlink() or not folder.is_dir() or {p.name for p in folder.iterdir()} != names:
            raise AgentBomError(f"retry handoff requires exact member set: {group}")
        paths.extend(folder / name for name in names)
    for path in paths:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise AgentBomError("retry handoff members must be regular non-symlink files within 2 MB")
    report, expected = handoff_payloads(
        load_json(directory / "review/policy.json"), load_json(directory / "baseline/plan.json"),
        load_json(directory / "baseline/ledger.json"), load_json(directory / "candidate/plan.json"),
        load_json(directory / "candidate/ledger.json"), load_json(directory / "review/diagnostics.json"),
        operating_budget=load_json(directory / "review/operating-budget.json") if budget else None)
    for name, value in expected.items():
        if (directory / name).read_bytes() != value:
            raise AgentBomError(f"retry handoff member does not recompute: {name}")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aau retry-review", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    for name in ("policy", "baseline_plan", "baseline_ledger", "candidate_plan", "candidate_ledger"):
        create.add_argument(name, type=Path)
    create.add_argument("--diagnostics", type=Path, required=True)
    create.add_argument("--operating-budget", type=Path)
    create.add_argument("--out", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    verify.add_argument("--require-budget", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            create_handoff(load_json(args.policy), load_json(args.baseline_plan), load_json(args.baseline_ledger),
                           load_json(args.candidate_plan), load_json(args.candidate_ledger), load_json(args.diagnostics), args.out,
                           operating_budget=load_json(args.operating_budget) if args.operating_budget else None)
            report = verify_handoff(args.out, require_budget=bool(args.operating_budget))
        else:
            report = verify_handoff(args.directory, require_budget=args.require_budget)
        count = 31 if "operating_budget_sha256" in report else 28
        print(f"Retry handoff verified: {report['status']}; all {count} files recomputed. Not deployment approval.")
        return int(report["status"] != "constraints_met")
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
