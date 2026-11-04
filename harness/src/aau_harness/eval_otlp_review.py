"""Retain both original OTLP exports through an independently recomputable policy/budget review."""

import argparse
import json
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered
from .eval_csv_review import BUDGET_FILES, REVIEW_FILES, ROOT_FILES
from .eval_otlp import ROOT_FILES as OTLP_FILES, _read, otlp_payloads
from .eval_retries import FILES as RETRY_FILES
from .eval_retry_review import handoff_payloads as retry_handoff_payloads


GUIDE = """AAU original-trace evaluation handoff

Open review/review.html for policy checks and logical-task operating diagnostics.
Verify the entire folder, not only the nested review or retry packs:

  aau otlp-review verify PATH_TO_THIS_FOLDER

Exit 0: the complete source chain verifies and supplied policy constraints are met.
Exit 1: the complete source chain verifies but supplied policy constraints are NOT met.
Exit 2: invalid inputs, incomplete evidence, or failed verification.

Retain all 36 files. Each baseline/candidate folder holds the original source.otlp
bytes, explicit mapping, projection report, manifest, and six-file retry/ pack.
The review/ folder contains the policy, diagnostics, recordings, and derived review.
The top-level report and manifest bind the full chain. Verification reprojects both
exports, normalizes both ledgers, and recomputes the review and all nested artifacts.
An individually valid but unrelated nested pack cannot replace this source chain.

Both mappings must use identical attribute maps, attempt semantics, metric reducers,
and accounting scope. Export format and span IDs may differ. Matching names do not
prove matching meanings or scoring validity. Independently approve the maps, span
census, exclusions, scores, measurement units, reducers, policy, context, and budget.
CLI review discloses missing context; the GitHub Action requires matching declarations
and independent input pins. Do not manufacture context fingerprints to pass CI.

Only declared sequential single-attempt spans directly under a task in the same
resource entry are supported. A logical-operation span may already include retries.
No status-based scoring, token pricing, telemetry collection, model calls, network,
uploads, or retry execution occurs. Missing operating measurements stay unknown.
Conversion success does not compensate for policy or operating-budget failure.

NOT SANITIZED: original traces can contain prompts, credentials, personal data, and
unmapped sensitive attributes/events. Inspect ALL files before sharing or uploading.
Hashes are not signatures, proof of complete capture, clock accuracy, independent
approval, actual execution, safety, regulatory compliance, or deployment approval.
Coordinated replacement of original evidence and declarations can still verify.
Interrupted folders are incomplete; verification must succeed before consumption.
"""


def handoff_payloads(policy: dict, baseline_mapping: dict, baseline_raw: bytes,
                     candidate_mapping: dict, candidate_raw: bytes, diagnostics: dict, *,
                     operating_budget: dict | None = None) -> tuple[dict, dict[str, bytes]]:
    payloads, sources, projections = {}, {}, []
    for side, mapping, raw in (("baseline", baseline_mapping, baseline_raw), ("candidate", candidate_mapping, candidate_raw)):
        report, files = otlp_payloads(mapping, raw)
        projections.append(files)
        payloads.update({f"{side}/{name}": value for name, value in files.items()})
        sources[side] = {key: report[key] for key in (
            "source_sha256", "mapping_sha256", "ledger_sha256", "evaluation_sha256",
            "exported_span_count", "task_count", "attempt_count", "excluded_span_count")}
    if any(baseline_mapping[key] != candidate_mapping[key] for key in ("attributes", "span_semantics")):
        raise AgentBomError("OTLP review requires identical attribute maps and attempt semantics")
    # Reuse the retry handoff's reducer/context checks and combined policy/budget gate.
    # Do not duplicate its baseline/candidate packs: the original-trace folders contain them.
    baseline, candidate = projections
    outcome, review_files = retry_handoff_payloads(
        policy, json.loads(baseline["retry/plan.json"]), json.loads(baseline["retry/ledger.json"]),
        json.loads(candidate["retry/plan.json"]), json.loads(candidate["retry/ledger.json"]), diagnostics,
        operating_budget=operating_budget)
    payloads.update({name: value for name, value in review_files.items() if name.startswith("review/")})
    report = {"report_version": "aau-otlp-evaluation-handoff/1.0", "status": outcome["status"],
              "sources": sources, "policy_sha256": digest(policy), "diagnostics_sha256": digest(diagnostics),
              "review_sha256": outcome["review_sha256"], "unit": "logical_task_per_scenario_repeat",
              "boundary": "Full original-trace-to-review recomputation with identical declared attribute maps, attempt semantics, "
                          "reducers and accounting scope, not execution authenticity, scoring validity, approved exclusions, "
                          "complete external capture, trustworthy clocks, regulatory compliance, or deployment approval. "
                          "Raw exports are retained without sanitization. Hashes are not signatures."}
    guide = GUIDE
    if operating_budget is not None:
        report.update(report_version="aau-otlp-evaluation-handoff/1.1",
                      **{key: outcome[key] for key in ("gate_sha256", "operating_budget_sha256", "policy_status", "candidate_budget_status")})
        guide = (GUIDE.replace("36 files", "39 files").replace("supplied policy constraints", "combined policy and candidate budget constraints")
                 .replace("are NOT met.", "are NOT met or not verified.")
                 + "\nThis handoff retains the candidate operating budget and its independent verdict.\n"
                 "Both policy and budget must be met. Refuse missing budget layers with:\n"
                 "  aau otlp-review verify PATH_TO_THIS_FOLDER --require-budget\n")
    payloads["handoff.json"] = rendered(report)
    payloads["README.txt"] = guide.encode()
    payloads["manifest.json"] = rendered({
        "pack_version": "aau-otlp-evaluation-handoff-pack/1.1" if operating_budget is not None else "aau-otlp-evaluation-handoff-pack/1.0",
        "files": {name: digest(value) for name, value in sorted(payloads.items())}})
    if any(len(value) > MAX_JSON_BYTES for value in payloads.values()):
        raise AgentBomError("OTLP review handoff member exceeds 2 MB")
    return report, payloads


def create_handoff(policy: dict, baseline_mapping: dict, baseline_raw: bytes, candidate_mapping: dict,
                   candidate_raw: bytes, diagnostics: dict, directory: Path, *, operating_budget: dict | None = None) -> dict:
    if directory.exists() or directory.is_symlink():
        raise AgentBomError("refusing to overwrite OTLP review destination")
    report, payloads = handoff_payloads(policy, baseline_mapping, baseline_raw, candidate_mapping, candidate_raw,
                                       diagnostics, operating_budget=operating_budget)
    directory.mkdir(parents=True, exist_ok=False)
    for name in ("baseline", "baseline/retry", "candidate", "candidate/retry", "review"):
        (directory / name).mkdir()
    for name, value in payloads.items():
        with (directory / name).open("xb") as stream:
            stream.write(value)  # The root completion manifest is last.
    return report


def verify_handoff(directory: Path, *, require_budget: bool = False) -> dict:
    if (directory.is_symlink() or not directory.is_dir()
            or {p.name for p in directory.iterdir()} != ROOT_FILES | {"baseline", "candidate", "review"}):
        raise AgentBomError("OTLP handoff requires exact root members")
    version = load_json(directory / "manifest.json").get("pack_version")
    if version not in ("aau-otlp-evaluation-handoff-pack/1.0", "aau-otlp-evaluation-handoff-pack/1.1"):
        raise AgentBomError("unsupported OTLP handoff version")
    budget = version == "aau-otlp-evaluation-handoff-pack/1.1"
    if require_budget and not budget:
        raise AgentBomError("required operating-budget layer is absent")
    names = set(ROOT_FILES)
    groups = {"baseline": OTLP_FILES | {"retry"}, "candidate": OTLP_FILES | {"retry"},
              "baseline/retry": RETRY_FILES, "candidate/retry": RETRY_FILES,
              "review": REVIEW_FILES | (BUDGET_FILES if budget else set())}
    for group, members in groups.items():
        folder = directory / group
        if folder.is_symlink() or not folder.is_dir() or {p.name for p in folder.iterdir()} != members:
            raise AgentBomError("OTLP handoff requires exact nested member sets")
        names.update(f"{group}/{name}" for name in members if name != "retry")
    actual = {name: _read(directory / name) for name in names}
    report, expected = handoff_payloads(
        load_json(directory / "review/policy.json"), load_json(directory / "baseline/mapping.json"), actual["baseline/source.otlp"],
        load_json(directory / "candidate/mapping.json"), actual["candidate/source.otlp"], load_json(directory / "review/diagnostics.json"),
        operating_budget=load_json(directory / "review/operating-budget.json") if budget else None)
    if actual != expected:
        raise AgentBomError("OTLP original-trace handoff does not recompute")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aau otlp-review", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    for name in ("policy", "baseline_mapping", "baseline_source", "candidate_mapping", "candidate_source"):
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
            create_handoff(load_json(args.policy), load_json(args.baseline_mapping), _read(args.baseline_source),
                           load_json(args.candidate_mapping), _read(args.candidate_source), load_json(args.diagnostics), args.out,
                           operating_budget=load_json(args.operating_budget) if args.operating_budget else None)
            report = verify_handoff(args.out, require_budget=args.operating_budget is not None)
        else:
            report = verify_handoff(args.directory, require_budget=args.require_budget)
        count = 39 if "operating_budget_sha256" in report else 36
        print(f"OTLP review verified: {report['status']}; all {count} files recomputed. Not deployment approval.")
        return int(report["status"] != "constraints_met")
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
