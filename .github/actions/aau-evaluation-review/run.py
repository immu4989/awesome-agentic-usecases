"""Pinned-repository Action; no model calls, installations, credentials, or uploads."""

import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "harness" / "src"))

from aau_harness.agent_bom import AgentBomError, MAX_JSON_BYTES, _parse_json  # noqa: E402
from aau_harness.eval_pack import create_pack, verify_pack  # noqa: E402
from aau_harness.evaluation_context import compare_contexts  # noqa: E402
from aau_harness.eval_audit import audit_evaluation  # noqa: E402
from aau_harness.eval_import import import_observations  # noqa: E402
from aau_harness.eval_csv import csv_payloads  # noqa: E402
from aau_harness.eval_csv_review import create_handoff, verify_handoff  # noqa: E402


def workspace_path(workspace: Path, raw: str) -> Path:
    path = Path(raw)
    if (not raw.strip() or path.is_absolute() or ".." in path.parts
            or any(ord(char) < 32 or ord(char) == 127 for char in raw)):
        raise AgentBomError("Action paths must be nonempty workspace-relative paths without '..' or control characters")
    target = workspace / path
    resolved = target.resolve()
    if resolved == workspace or not resolved.is_relative_to(workspace):
        raise AgentBomError("Action path must remain inside the workspace")
    current = workspace
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise AgentBomError("Action paths cannot contain symbolic links")
    return target


def read_bytes(path: Path, expected_hash: str | None = None) -> bytes:
    if not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise AgentBomError("Action source must be a bounded file")
    with path.open("rb") as stream:
        payload = stream.read(MAX_JSON_BYTES + 1)
    if len(payload) > MAX_JSON_BYTES:
        raise AgentBomError("Action source exceeds 2 MB")
    if expected_hash is not None:
        if len(expected_hash) != 64 or set(expected_hash) - set("0123456789abcdef"):
            raise AgentBomError("approved SHA-256 must contain 64 lowercase hexadecimal characters")
        if hashlib.sha256(payload).hexdigest() != expected_hash:
            raise AgentBomError("approved source file SHA-256 does not match")
    return payload


def read_source(path: Path, expected_hash: str | None = None) -> dict:
    payload = read_bytes(path, expected_hash)
    value = _parse_json(payload)
    if not isinstance(value, dict):
        raise AgentBomError("Action source must contain one JSON object")
    return value


def main() -> int:
    try:
        workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve(strict=True)
        if not workspace.is_dir():
            raise AgentBomError("GitHub workspace must be a directory")
        paths = {name: workspace_path(workspace, os.environ[f"AAU_EVAL_{name.upper()}"])
                 for name in ("policy", "baseline", "candidate", "output")}
        if paths["output"].exists():
            raise AgentBomError("refusing to overwrite an existing pack destination")
        policy = read_source(paths["policy"], os.environ["AAU_EVAL_POLICY_SHA256"])
        diagnostic_path = os.environ.get("AAU_EVAL_DIAGNOSTICS", "")
        diagnostic_hash = os.environ.get("AAU_EVAL_DIAGNOSTICS_SHA256", "")
        if bool(diagnostic_path) != bool(diagnostic_hash):
            raise AgentBomError("diagnostic plan and independently approved byte hash must be supplied together")
        diagnostics = read_source(workspace_path(workspace, diagnostic_path), diagnostic_hash) if diagnostic_path else None
        input_format = os.environ.get("AAU_EVAL_INPUT_FORMAT", "evaluations")
        if input_format not in ("evaluations", "recordings", "csv"):
            raise AgentBomError("input format must be evaluations, recordings, or csv")
        maps = {name: os.environ.get(f"AAU_EVAL_{name}", "") for name in (
            "BASELINE_PLAN", "BASELINE_PLAN_SHA256", "CANDIDATE_PLAN", "CANDIDATE_PLAN_SHA256")}
        if input_format != "csv" and any(maps.values()):
            raise AgentBomError("CSV mapping inputs are allowed only with input-format csv")
        recordings = input_format == "recordings"
        if input_format == "csv":
            if not all(maps.values()) or diagnostics is None:
                raise AgentBomError("CSV mode requires both independently pinned mapping plans and a pinned diagnostics plan")
            baseline_plan = read_source(workspace_path(workspace, maps["BASELINE_PLAN"]), maps["BASELINE_PLAN_SHA256"])
            candidate_plan = read_source(workspace_path(workspace, maps["CANDIDATE_PLAN"]), maps["CANDIDATE_PLAN_SHA256"])
            baseline = read_bytes(paths["baseline"], os.environ["AAU_EVAL_BASELINE_SHA256"])
            candidate = read_bytes(paths["candidate"])
            reviewed_baseline, reviewed_candidate = (
                json.loads(csv_payloads(plan, raw)[1]["evaluation.json"])
                for plan, raw in ((baseline_plan, baseline), (candidate_plan, candidate)))
        else:
            baseline = read_source(paths["baseline"], os.environ["AAU_EVAL_BASELINE_SHA256"])
            candidate = read_source(paths["candidate"])
            reviewed_baseline, reviewed_candidate = (
                (import_observations(baseline), import_observations(candidate)) if recordings else (baseline, candidate))
        # Validate observation shapes before the context checker inspects IDs.
        audit_evaluation(reviewed_baseline)
        audit_evaluation(reviewed_candidate)
        if compare_contexts(reviewed_baseline, reviewed_candidate)["status"] != "matched":
            raise AgentBomError("Action requires matching declared context on both evaluations; legacy evidence needs separate review")
        if input_format == "csv":
            handoff = create_handoff(policy, baseline_plan, baseline, candidate_plan, candidate, diagnostics, paths["output"])
            if verify_handoff(paths["output"]) != handoff:
                raise AgentBomError("saved CSV handoff does not match computed evidence")
            report = read_source(paths["output"] / "review/review.json")
        else:
            report = create_pack(policy, baseline, candidate, paths["output"], recordings=recordings, diagnostics=diagnostics)
            if verify_pack(paths["output"], require_recordings=recordings, require_diagnostics=diagnostics is not None) != report:
                raise AgentBomError("saved review pack does not match computed evidence")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write("## AAU saved evaluation review\n\n"
                             f"Result: **{report['status']}**. Failed constraints: {len(report['failed_constraints'])}.\n\n"
                             "Approved policy/baseline byte hashes matched; declared benchmark context matched. "
                             "The offline pack recomputed. No raw scenario text is included in this summary.\n\n"
                             "The pack includes full source details: inspect before uploading. "
                             "This check is not execution attestation or deployment approval.\n")
                if diagnostics is not None:
                    stream.write("\nDiagnostic dossier: approved plan byte hash matched; repeated-run and operating "
                                 "views recomputed for both sources. Diagnostics do not change the policy verdict. "
                                 "Criteria, cost labels, scores, identifiers, and source details are not echoed here.\n")
                if input_format == "csv":
                    stream.write("\nCSV handoff: both approved mapping-plan byte hashes matched; original CSV exports "
                                 "and all 28 files recomputed together. Column headers and source values are not echoed here. "
                                 "Use aau csv-review verify for the complete handoff.\n")
        return int(report["status"] != "constraints_met")
    except (AgentBomError, OSError, ValueError, KeyError) as exc:
        # Avoid echoing raw source content or GitHub annotation-shaped payloads.
        print(f"AAU evaluation review failed ({type(exc).__name__}); validate inputs, approved hashes, context, and destination.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
