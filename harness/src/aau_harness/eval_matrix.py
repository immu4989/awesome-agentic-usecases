"""Compare recorded candidate trade-offs without compensating for failed policy constraints."""

import argparse
from itertools import combinations
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered
from .authority_html import STYLE
from .eval_operations import COST_BASES, review_operations
from .eval_pack import _table, _text
from .eval_policy import review_evaluations
from .evaluation_context import compare_contexts


BOUNDARY = ("Descriptive comparison of supplied observations, not vendor selection, procurement advice, deployment "
            "approval, statistical dominance, future cost or latency, verified invoices, or realized outcomes. "
            "All candidates share the declared scenario/scorer/configuration fingerprints and repeat count; "
            "fingerprints do not authenticate execution or prove identical operating conditions. Passing counts "
            "use the plan's joint criteria, not necessarily policy/cohort criteria. Failure costs remain included. "
            "Operating trade-offs use only cost per jointly passing attempt and nearest-rank p95 latency; other "
            "quality, safety, environmental, accessibility, and procurement considerations are not ranked. "
            "Comparisons use exact recorded finite numbers, not uncertainty-adjusted estimates. Cost bases are "
            "declarations; infrastructure, human review, and other omitted costs are not inferred. No source is sanitized. "
            "Hashes are not signatures; coordinated replacement can verify. No model calls, uploads, or approvals.")


def validate_plan(plan: dict) -> list[str]:
    if not isinstance(plan, dict) or set(plan) != {"plan_version", "candidate_ids", "criteria", "cost_basis"}:
        raise AgentBomError("matrix plan requires plan_version, candidate_ids, criteria, and cost_basis")
    if plan["plan_version"] != "aau-candidate-matrix/1.0":
        raise AgentBomError("unsupported matrix plan version")
    ids = plan["candidate_ids"]
    if (not isinstance(ids, list) or not 2 <= len(ids) <= 10
            or any(not isinstance(name, str) or not name.strip() or len(name) > 120 or "=" in name for name in ids)
            or len(set(ids)) != len(ids)):
        raise AgentBomError("matrix requires 2 to 10 distinct nonblank candidate IDs of at most 120 characters without '='")
    bases = plan["cost_basis"]
    if (not isinstance(bases, dict) or set(bases) != set(ids)
            or any(not isinstance(value, str) or value not in COST_BASES for value in bases.values())):
        raise AgentBomError("matrix requires an explicit supported cost basis for every candidate")
    return sorted(ids)


def prefix(index: int) -> str:
    return f"candidate-{index:02d}"


def matrix_payloads(plan: dict, policy: dict, baseline: dict, candidates: dict) -> tuple[dict, dict[str, bytes]]:
    ids = validate_plan(plan)
    if not isinstance(candidates, dict) or set(candidates) != set(ids):
        raise AgentBomError("supplied candidates must exactly match the matrix plan; no missing or extra candidates")
    rows, files = [], {"plan.json": rendered(plan), "policy.json": rendered(policy), "baseline.json": rendered(baseline)}
    for index, name in enumerate(ids, 1):
        source = candidates[name]
        review = review_evaluations(policy, baseline, source)
        if compare_contexts(baseline, source)["status"] != "matched":
            raise AgentBomError("candidate matrix requires matching declared context on every source")
        if baseline["n_repeats"] != source["n_repeats"]:
            raise AgentBomError("candidate matrix requires equal repeat counts on every source")
        operations = review_operations(source, criteria=plan["criteria"], cost_basis=plan["cost_basis"][name])
        overall = operations["overall"]
        reasons = []
        if review["status"] != "constraints_met":
            reasons.append("policy_constraints_not_met")
        if overall["cost"]["status"] != "complete":
            reasons.append("incomplete_cost_coverage")
        if overall["latency"]["status"] != "complete":
            reasons.append("incomplete_latency_coverage")
        if not overall["passing_attempt_count"]:
            reasons.append("no_jointly_passing_attempts")
        if plan["cost_basis"][name] == "unknown":
            reasons.append("unknown_cost_basis")
        stem = prefix(index)
        files.update({f"{stem}.json": rendered(source), f"{stem}-policy.json": rendered(review),
                      f"{stem}-operations.json": rendered(operations)})
        rows.append({"candidate_id": name, "source_file": f"{stem}.json",
                     "policy_file": f"{stem}-policy.json", "operations_file": f"{stem}-operations.json",
                     "source_sha256": digest(source), "policy_status": review["status"],
                     "failed_constraints": review["failed_constraints"], "cost_basis": plan["cost_basis"][name],
                     "operating_comparison_eligible": not reasons, "exclusion_reasons": reasons,
                     "overall": overall})
    pairs, dominated = [], set()
    for left, right in combinations(rows, 2):
        if not left["operating_comparison_eligible"] or not right["operating_comparison_eligible"]:
            relationship = "not_comparable"
            reason = "candidate_excluded"
        elif left["cost_basis"] != right["cost_basis"]:
            relationship, reason = "not_comparable", "different_declared_cost_bases"
        else:
            a, b = [(row["overall"]["cost"]["total_per_passing_attempt_usd"], row["overall"]["latency"]["p95_s"])
                    for row in (left, right)]
            reason = None
            if a == b:
                relationship = "equal_recorded_axes"
            elif all(x <= y for x, y in zip(a, b)):
                relationship = "left_dominates_recorded_axes"
                dominated.add(right["candidate_id"])
            elif all(x >= y for x, y in zip(a, b)):
                relationship = "right_dominates_recorded_axes"
                dominated.add(left["candidate_id"])
            else:
                relationship = "recorded_tradeoff"
        pairs.append({"left": left["candidate_id"], "right": right["candidate_id"],
                      "relationship": relationship, "reason": reason})
    groups = []
    for basis in sorted(set(plan["cost_basis"].values()) - {"unknown"}):
        eligible = [r["candidate_id"] for r in rows if r["cost_basis"] == basis and r["operating_comparison_eligible"]]
        groups.append({"cost_basis": basis, "eligible_candidates": eligible,
                       "nondominated_recorded_candidates": [name for name in eligible if name not in dominated]})
    report = {"report_version": "aau-candidate-matrix-report/1.0", "plan_sha256": digest(plan),
              "policy_sha256": digest(policy), "baseline_sha256": digest(baseline),
              "scenario_count": baseline["n_scenarios"], "repeats_per_scenario": baseline["n_repeats"],
              "joint_pass_criteria": plan["criteria"],
              "candidates": rows, "pairwise_comparisons": pairs, "operating_groups": groups,
              "boundary": BOUNDARY}
    files["matrix.json"] = rendered(report)
    files["matrix.html"] = render_matrix(report).encode("utf-8")
    if any(len(value) > MAX_JSON_BYTES for value in files.values()):
        raise AgentBomError("candidate matrix member exceeds 2 MB")
    files["manifest.json"] = rendered({"pack_version": "aau-candidate-matrix-pack/1.0",
        "files": {name: digest(value) for name, value in sorted(files.items())}})
    return report, files


def render_matrix(report: dict) -> str:
    def display(value):
        return "Unknown" if value is None else value
    reason_labels = {"policy_constraints_not_met": "Policy constraints not met",
                     "incomplete_cost_coverage": "Incomplete cost coverage",
                     "incomplete_latency_coverage": "Incomplete latency coverage",
                     "no_jointly_passing_attempts": "No jointly passing attempts",
                     "unknown_cost_basis": "Unknown cost basis"}
    table = _table("All supplied candidates — alphabetical, not ranked",
                   ("Candidate", "Policy", "Declared cost basis", "Jointly passing / attempts",
                    "USD / jointly passing attempt", "p95 seconds", "Excluded from operating comparison"), [
        (r["candidate_id"], "Met" if r["policy_status"] == "constraints_met" else "Not met", r["cost_basis"],
         f"{r['overall']['passing_attempt_count']} / {r['overall']['attempt_count']}",
         display(r["overall"]["cost"]["total_per_passing_attempt_usd"]), display(r["overall"]["latency"]["p95_s"]),
         "; ".join(reason_labels[reason] for reason in r["exclusion_reasons"]) or "No") for r in report["candidates"]])
    groups = _table("Observed cost/latency trade-offs within each declared basis",
                    ("Basis", "Eligible candidates", "Not dominated on the two recorded axes"),
                    [(g["cost_basis"], ", ".join(g["eligible_candidates"]) or "None",
                      ", ".join(g["nondominated_recorded_candidates"]) or "None") for g in report["operating_groups"]])
    criteria = _table("Common joint-pass criteria — every condition on the same attempt",
                      ("Metric", "Direction", "Inclusive limit"),
                      [(r["metric"], r["direction"], r["limit"]) for r in report["joint_pass_criteria"]])
    links = "".join(f'<li>{_text(r["candidate_id"])}: <a href="{r["policy_file"]}">full policy checks</a> · '
                    f'<a href="{r["operations_file"]}">operating coverage and per-scenario detail</a></li>'
                    for r in report["candidates"])
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
            'style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
            f'<title>Recorded candidate review matrix</title><style>{STYLE}td{{overflow-wrap:anywhere}}table{{min-width:700px}}</style></head>'
            '<body><main><p class="eyebrow">Offline evidence · no vendor selection</p><h1>Recorded candidate review matrix</h1>'
            '<p class="notice">A cheap or fast result never compensates for a failed policy constraint. '
            'Unknown measurements are not zero. There is no overall winner or weighted score.</p>'
            f'<p>Declared scenarios: {_text(report["scenario_count"])}; '
            f'{_text(report["repeats_per_scenario"])} repeats per scenario on every source. '
            'Declared context matches; actual execution conditions remain unverified.</p>'
            f'{table}{criteria}{groups}<p>Not dominated means no other eligible candidate in the same declared cost basis '
            'is no worse on both recorded axes and strictly better on at least one. Equal points remain tied. '
            'A group may contain only one eligible candidate. This is not statistical or future superiority.</p>'
            f'<h2>Inspect the evidence</h2><ul>{links}</ul><p>{_text(report["boundary"])}</p>'
            '<p>This page does not verify itself. Retain every file and run <code>aau candidate-matrix verify PATH</code> '
            'with the matching trusted harness. Exit 0 verifies the matrix, not candidate policy success. '
            'Complete supplied evaluations are included and are not sanitized; inspect before sharing.</p></main></body></html>\n')


def create_matrix(plan: dict, policy: dict, baseline: dict, candidates: dict, directory: Path) -> dict:
    if directory.exists() or directory.is_symlink():
        raise AgentBomError("refusing to overwrite a candidate matrix destination")
    report, files = matrix_payloads(plan, policy, baseline, candidates)
    directory.mkdir(parents=True, exist_ok=False)
    for name, value in files.items():
        with (directory / name).open("xb") as stream:
            stream.write(value)
    return report


def verify_matrix(directory: Path) -> dict:
    if directory.is_symlink() or not directory.is_dir():
        raise AgentBomError("candidate matrix must be a real directory")
    plan = load_json(directory / "plan.json")
    ids = validate_plan(plan)
    names = {"plan.json", "policy.json", "baseline.json", "matrix.json", "matrix.html", "manifest.json"}
    names.update(f"{prefix(i)}{suffix}.json" for i in range(1, len(ids) + 1) for suffix in ("", "-policy", "-operations"))
    if {path.name for path in directory.iterdir()} != names:
        raise AgentBomError("candidate matrix requires its exact file set")
    for path in directory.iterdir():
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise AgentBomError("candidate matrix member must be a regular non-symlink file within 2 MB")
    candidates = {name: load_json(directory / f"{prefix(index)}.json") for index, name in enumerate(ids, 1)}
    report, expected = matrix_payloads(plan, load_json(directory / "policy.json"), load_json(directory / "baseline.json"), candidates)
    for name, value in expected.items():
        if (directory / name).read_bytes() != value:
            raise AgentBomError(f"candidate matrix member does not recompute: {name}")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="aau candidate-matrix", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    for name in ("plan", "policy", "baseline"):
        create.add_argument(name, type=Path)
    create.add_argument("--candidate", action="append", required=True, metavar="ID=PATH")
    create.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            if not 2 <= len(args.candidate) <= 10:
                raise AgentBomError("supply 2 to 10 candidate files")
            candidates = {}
            for entry in args.candidate:
                name, separator, path = entry.partition("=")
                if not separator or not path or name in candidates:
                    raise AgentBomError("candidate arguments require distinct ID=PATH entries")
                candidates[name] = load_json(Path(path))
            create_matrix(load_json(args.plan), load_json(args.policy), load_json(args.baseline), candidates, args.out)
            report = verify_matrix(args.out)
        else:
            report = verify_matrix(args.directory)
        print(f"Verified descriptive matrix of {len(report['candidates'])} candidates; not a policy-pass gate or selection decision.")
        return 0
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
