"""Explain evaluation-context drift without comparing scores across changed benchmarks."""

import argparse
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json
from .eval_audit import audit_evaluation
from .eval_import import import_observations
from .evaluation_context import validate_context


def _fingerprints(before: dict | None, after: dict | None, *, names=()) -> dict:
    """Absence of an entire declaration is not evidence of component removal."""
    available = before is not None and after is not None
    rows = []
    for name in sorted(set(before or {}) | set(after or {}) | set(names)):
        left, right = (before or {}).get(name), (after or {}).get(name)
        state = ("unknown" if not available else "added" if left is None else
                 "removed" if right is None else "unchanged" if left == right else "changed")
        rows.append({"name": name, "state": state, "baseline_sha256": left, "candidate_sha256": right})
    return {"comparison_available": available, "components": rows,
            "counts": {state: sum(row["state"] == state for row in rows)
                       for state in ("added", "removed", "changed", "unchanged", "unknown")}}


def compare_evaluation_contexts(baseline: dict, candidate: dict, *, input_format: str = "evaluations") -> dict:
    if input_format not in ("evaluations", "recordings"):
        raise AgentBomError("input_format must be evaluations or recordings")
    originals = baseline, candidate
    sources = [import_observations(value) if input_format == "recordings" else value for value in originals]
    inventories, contexts, audits = {}, [], {}
    for label, original, source in zip(("baseline", "candidate"), originals, sources):
        audit = audit_evaluation(source)
        ids = sorted({row["scenario_id"] for row in source["results"]})
        context = source.get("evaluation_context")
        if "evaluation_context" in source:
            validate_context(context, ids)  # Malformed present context is not legacy absence.
        contexts.append(context)
        inventories[label] = {"source_sha256": digest(original), "evaluation_sha256": digest(source),
                              "scenario_ids": ids, "repeat_count": source["n_repeats"],
                              "context_declared": context is not None}
        audits[label] = {"status": audit["status"], "mismatch_count": len(audit["mismatches"])}
    before_ids, after_ids = (set(inventories[label]["scenario_ids"]) for label in ("baseline", "candidate"))
    old, new = contexts
    scenarios = _fingerprints(old["scenario_sha256"] if old else None, new["scenario_sha256"] if new else None,
                              names=before_ids | after_ids)
    scoring = _fingerprints(old["scoring_sha256"] if old else None, new["scoring_sha256"] if new else None)
    census = {"added": sorted(after_ids - before_ids), "removed": sorted(before_ids - after_ids),
              "shared": sorted(before_ids & after_ids)}
    config = {"baseline_sha256": old["config_sha256"] if old else None,
              "candidate_sha256": new["config_sha256"] if new else None,
              "state": "unknown" if old is None or new is None else
                       "unchanged" if old["config_sha256"] == new["config_sha256"] else "changed"}
    missing = [label for label in ("baseline", "candidate") if not inventories[label]["context_declared"]]
    reasons = []
    if missing:
        reasons.append("context_unavailable")
    if census["added"] or census["removed"]:
        reasons.append("scenario_census_changed")
    if scenarios["counts"]["changed"]:
        reasons.append("scenario_content_changed")
    if any(scoring["counts"][state] for state in ("added", "removed", "changed")):
        reasons.append("scoring_sources_changed")
    if config["state"] == "changed":
        reasons.append("configuration_changed")
    for label, audit in audits.items():
        if audit["status"] != "consistent":
            reasons.append(f"{label}_metric_summaries_inconsistent")
    guidance = []
    if missing:
        guidance.append("Recover contemporaneous collection context if available; do not attach today's fingerprints to historical observations.")
    if any(reason in reasons for reason in ("scenario_census_changed", "scenario_content_changed", "scoring_sources_changed", "configuration_changed")):
        guidance.append("Review the changed test definition and collect comparable evidence under an independently reviewed common context. Do not drop changed or removed cases, relabel IDs, or replace fingerprints to force a match.")
    if any(audit["status"] != "consistent" for audit in audits.values()):
        guidance.append("Run audit-eval on the normalized evaluations to inspect exact summary mismatches; preserve the original evidence while investigating.")
    different_repeats = inventories["baseline"]["repeat_count"] != inventories["candidate"]["repeat_count"]
    warnings = ["Matching declared fingerprints do not authenticate execution, scoring, or the completeness of captured dependencies."]
    if different_repeats:
        warnings.append("Repeat counts differ. This is disclosed, not a context mismatch; policy minimums and uncertainty still require separate review.")
    return {
        "report_version": "aau-evaluation-context-diff/1.0", "input_format": input_format,
        "sources": inventories, "status": "review_required" if reasons else "declared_context_matched",
        "review_reasons": reasons, "missing_context_sources": missing,
        "scenario_census": census, "scenario_fingerprints": scenarios, "scoring_fingerprints": scoring,
        "configuration": config, "repeat_counts_differ": different_repeats,
        "source_metric_audits": audits, "next_steps": guidance, "warnings": warnings,
        "boundary": "A structural inventory of supplied evaluation context, not a score comparison, migration approval, equivalence proof, compliance certification, or deployment decision. Added and removed scenario IDs are determined from complete supplied observation censuses; missing fingerprints stay unknown. Changed digests do not reveal semantic differences, and renamed items are not inferred to be equivalent. This report does not pair only a favorable intersection, modify a source, repair summaries, fill missing context, or relax any existing comparison gate. Fingerprints bind declared JSON values and named scoring bytes, not execution authenticity, collection timing, environment, dependency closure, or representativeness. Scenario IDs, component names, and digests may be sensitive; inspect before sharing.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau compare-eval-contexts", description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--input-format", choices=("evaluations", "recordings"), default="evaluations")
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--out", type=Path)
    destination.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    try:
        report = compare_evaluation_contexts(load_json(args.baseline), load_json(args.candidate), input_format=args.input_format)
        if len(rendered(report)) > MAX_JSON_BYTES:
            raise AgentBomError("evaluation context comparison exceeds 2 MB")
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise AgentBomError("evaluation context comparison does not recompute")
        else:
            write_json(report, args.out)
        print(f"{report['status']}: {len(report['review_reasons'])} review reasons; no cross-context score comparison performed")
        return int(report["status"] == "review_required")
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
