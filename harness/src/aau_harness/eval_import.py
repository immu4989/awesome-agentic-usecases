"""Import recorded scores and optional operating measurements without executing an evaluator."""

import argparse
from copy import deepcopy
import json
import sys
from pathlib import Path

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json
from .eval_audit import audit_evaluation
from .eval_operations import validate_operating_measurements
from .evaluation_context import validate_context


def import_observations(source: dict) -> dict:
    required = {"format_version", "source_label", "scenario_ids", "n_repeats", "observations"}
    if not isinstance(source, dict) or not required <= set(source) or set(source) - required - {"evaluation_context"}:
        raise AgentBomError("recorded observations require the documented fields only")
    version = source["format_version"]
    if version not in ("aau-recorded-observations/1.0", "aau-recorded-observations/1.1"):
        raise AgentBomError("unsupported recorded observation version")
    label = source["source_label"]
    if not isinstance(label, str) or not label.strip() or len(label) > 200:
        raise AgentBomError("source_label must be a nonblank string of at most 200 characters")
    ids = source["scenario_ids"]
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 500
            or any(not isinstance(value, str) or not value.strip() or len(value) > 200 for value in ids)
            or len(set(ids)) != len(ids)):
        raise AgentBomError("scenario_ids must declare 1 to 500 unique nonblank IDs")
    rows = source["observations"]
    row_required = {"scenario_id", "repeat", "metrics"}
    optional = {"cost_usd", "latency_s", "n_api_calls"} if version == "aau-recorded-observations/1.1" else set()
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) or not row_required <= set(row) or set(row) - row_required - optional for row in rows
    ):
        raise AgentBomError("each observation requires scenario_id, repeat, metrics and only the version's documented optional fields")
    validate_operating_measurements(rows)
    if any(not isinstance(row["scenario_id"], str) or row["scenario_id"] not in ids for row in rows):
        raise AgentBomError("observation scenario ID is outside the declared census")
    if "evaluation_context" in source:
        validate_context(source["evaluation_context"], ids)
    try:
        json.dumps(source, allow_nan=False)
        if len(rendered(source)) > MAX_JSON_BYTES:
            raise AgentBomError("recorded observations exceed 2 MB")
        fingerprint = digest(source)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise AgentBomError("recorded observations must contain finite JSON values") from exc
    # The audit checks the full observation matrix and computes metric summaries using
    # the shared runner. Its operational placeholders never enter this imported export.
    candidate = {"n_scenarios": len(ids), "n_repeats": source["n_repeats"], "results": rows,
                 "metric_means": {}, "metric_ci95": {}}
    audit = audit_evaluation(candidate)
    if not audit["recomputed"]["metric_means"]:
        raise AgentBomError("recorded observations must contain at least one measured metric")
    result = {
        "provenance": {
            "evidence_kind": "imported_unverified_observations", "source_label": label,
            "source_sha256": fingerprint, "import_format": source["format_version"],
            "boundary": "Offline normalization of supplied scores, not an executed or authenticated evaluation. No scoring, model calls, transport checks, cost, latency, or API-call measurements were performed or inferred. Source labels and context fingerprints are declarations, not attestations. Missing metrics remain absent; scenario coverage does not prove population coverage.",
        },
        "n_scenarios": len(ids), "n_repeats": source["n_repeats"],
        **audit["recomputed"], "metric_coverage": audit["metric_coverage"],
        "results": deepcopy(sorted(rows, key=lambda row: (row["scenario_id"], row["repeat"]))),
        **({"evaluation_context": deepcopy(source["evaluation_context"])} if "evaluation_context" in source else {}),
    }
    if version == "aau-recorded-observations/1.1":
        result["provenance"]["boundary"] += (
            " Optional per-attempt USD costs, elapsed seconds, and API-call counts are copied as supplied,"
            " not measured, rounded, unit-converted, price-checked, or authenticated by this importer."
            " Omitted fields remain unknown. Zero is a supplied value, not an assertion of free or instantaneous execution."
            " Cost basis and measurement scope require separate review; no operating totals are inferred here.")
    try:
        json.dumps(result, allow_nan=False)
        if len(rendered(result)) > MAX_JSON_BYTES:
            raise AgentBomError("imported evaluation exceeds 2 MB")
    except (ValueError, OverflowError) as exc:
        raise AgentBomError("imported summary exceeds finite numeric range") from exc
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau import-eval", description=__doc__)
    parser.add_argument("observations", type=Path)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--out", type=Path)
    destination.add_argument("--verify", type=Path, help="recompute an imported evaluation from its recorded source")
    args = parser.parse_args(argv)
    try:
        report = import_observations(load_json(args.observations))
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise AgentBomError("imported evaluation does not recompute from this source")
        else:
            write_json(report, args.out)
        print(f"Imported {len(report['results'])} supplied observations; no evaluator or model was executed.")
        return 0
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
