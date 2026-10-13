"""Explicit CSV-to-observation conversion with a retained, recomputable source chain."""

import argparse
from copy import deepcopy
import csv
from io import StringIO
import json
from pathlib import Path
import re
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered
from .eval_import import import_observations


FILES = {"source.csv", "plan.json", "recording.json", "evaluation.json", "conversion.json", "manifest.json"}
OPERATING = {"cost_usd", "latency_s", "n_api_calls"}
NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")


def _columns(plan):
    required = {"plan_version", "source_label", "scenario_ids", "n_repeats", "columns"}
    if not isinstance(plan, dict) or not required <= set(plan) or set(plan) - required - {"evaluation_context"}:
        raise AgentBomError("CSV plan requires the documented fields only")
    if plan["plan_version"] != "aau-csv-observation-import/1.0":
        raise AgentBomError("unsupported CSV import plan version")
    columns = plan["columns"]
    if not isinstance(columns, dict) or set(columns) != {"scenario_id", "repeat", "metrics", "operating"}:
        raise AgentBomError("columns must contain scenario_id, repeat, metrics, operating")
    metrics, operating = columns["metrics"], columns["operating"]
    if (not isinstance(metrics, dict) or not 1 <= len(metrics) <= 100
            or any(not isinstance(name, str) or not name.strip() or len(name) > 200 for name in metrics)):
        raise AgentBomError("CSV metric map requires 1 to 100 nonblank metric names")
    if not isinstance(operating, dict) or not set(operating) <= OPERATING:
        raise AgentBomError("CSV operating map supports only cost_usd, latency_s, n_api_calls")
    names = [columns["scenario_id"], columns["repeat"], *metrics.values(), *operating.values()]
    if (any(not isinstance(name, str) or not name.strip() or len(name) > 200 for name in names)
            or len(set(names)) != len(names)):
        raise AgentBomError("each mapped CSV column must have a distinct nonblank name of at most 200 characters")
    return columns, names


def _number(cell: str):
    value = cell.strip()
    if not NUMBER.fullmatch(value):
        raise AgentBomError("CSV numeric cells must be JSON numbers; no formulas, booleans, nulls, or text coercion")
    try:
        return json.loads(value)
    except (ValueError, OverflowError) as exc:
        raise AgentBomError("CSV numeric cell exceeds supported numeric representation") from exc


def csv_payloads(plan: dict, raw: bytes) -> tuple[dict, dict[str, bytes]]:
    columns, names = _columns(plan)
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_JSON_BYTES:
        raise AgentBomError("CSV source must contain 1 to 2000000 bytes")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise AgentBomError("CSV source must be UTF-8, optionally with a UTF-8 BOM") from exc
    if "\x00" in text:
        raise AgentBomError("CSV source contains a NUL character")
    rows, expanded_size = [], 0
    try:
        reader = csv.reader(StringIO(text, newline=""), dialect="excel", strict=True)
        header = next(reader, [])
        if len(header) != len(names) or len(set(header)) != len(header) or set(header) != set(names):
            raise AgentBomError("CSV headers must match the column map exactly; no duplicate, missing, or unmapped columns")
        for cells in reader:
            if len(cells) != len(header) or len(rows) >= 10000:
                raise AgentBomError("CSV rows must match header width and fit the 10000-observation limit; blank rows are not skipped")
            values = dict(zip(header, cells))
            row = {"scenario_id": values[columns["scenario_id"]], "repeat": _number(values[columns["repeat"]]), "metrics": {}}
            for metric, column in columns["metrics"].items():
                if values[column].strip():
                    row["metrics"][metric] = _number(values[column])
            for field, column in columns["operating"].items():
                if values[column].strip():
                    row[field] = _number(values[column])
            # Short CSV headers may map to long metric names repeated thousands of times.
            # Bound expansion incrementally, before materializing a large recording export.
            expanded_size += len(rendered(row))
            if expanded_size > MAX_JSON_BYTES:
                raise AgentBomError("CSV expanded observations exceed 2 MB")
            rows.append(row)
    except csv.Error as exc:
        raise AgentBomError("CSV quoting or field size is invalid") from exc
    recording = {"format_version": "aau-recorded-observations/1.1",
                 **{field: deepcopy(plan[field]) for field in ("source_label", "scenario_ids", "n_repeats")},
                 "observations": rows,
                 **({"evaluation_context": deepcopy(plan["evaluation_context"])} if "evaluation_context" in plan else {})}
    evaluation = import_observations(recording)
    report = {
        "report_version": "aau-csv-observation-conversion/1.0", "source_csv_sha256": digest(raw),
        "plan_sha256": digest(plan), "recording_sha256": digest(recording), "evaluation_sha256": digest(evaluation),
        "observation_count": len(rows), "scenario_count": evaluation["n_scenarios"],
        "declared_metrics": sorted(columns["metrics"]),
        "unreported_metrics": sorted(set(columns["metrics"]) - set(evaluation["metric_coverage"])),
        "metric_coverage": evaluation["metric_coverage"],
        "operating_coverage": {field: {"reporting_observations": sum(field in row for row in rows),
                                      "declared_observations": len(rows)} for field in sorted(OPERATING)},
        "boundary": "Offline conversion of supplied scored CSV rows, not agent execution, verified scoring, or deployment approval. The source CSV is retained byte-for-byte, including its BOM and line endings. Blank metric or operating cells stay absent, not zero; blank identity/repeat cells are invalid. Column meanings, zero-based repeats, USD costs, elapsed seconds, and API-call counts must be mapped explicitly by the user. No delimiter sniffing, unit conversion, currency conversion, filtering, missing-row repair, or context fabrication is performed. Hashes bind source bytes and declared JSON values, not authenticity or reviewer approval. This folder is not sanitized: source values and identifiers can be sensitive or contain spreadsheet formulas; do not open untrusted CSV in a spreadsheet application. Review before sharing.",
    }
    payloads = {"source.csv": raw, **{name: rendered(value) for name, value in (
        ("plan.json", plan), ("recording.json", recording), ("evaluation.json", evaluation), ("conversion.json", report))}}
    manifest = {"pack_version": "aau-csv-observation-pack/1.0",
                "files": {name: digest(value) for name, value in sorted(payloads.items())}}
    payloads["manifest.json"] = rendered(manifest)
    if any(len(value) > MAX_JSON_BYTES for value in payloads.values()):
        raise AgentBomError("CSV conversion pack member exceeds 2 MB")
    return report, payloads


def create_csv_pack(plan: dict, raw: bytes, directory: Path) -> dict:
    if directory.exists() or directory.is_symlink():
        raise AgentBomError("refusing to overwrite an existing CSV conversion destination")
    report, payloads = csv_payloads(plan, raw)
    directory.mkdir(parents=True, exist_ok=False)
    for name, value in payloads.items():
        with (directory / name).open("xb") as stream:
            stream.write(value)  # Manifest is last; interrupted packs cannot verify.
    return report


def _read_source(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise AgentBomError("CSV input must be a regular, non-symlink file within 2 MB")
    with path.open("rb") as stream:
        return stream.read(MAX_JSON_BYTES + 1)


def verify_csv_pack(directory: Path, *, evaluation_path: Path | None = None) -> dict:
    if directory.is_symlink() or not directory.is_dir() or {path.name for path in directory.iterdir()} != FILES:
        raise AgentBomError("CSV conversion pack requires the exact six-file set in a real directory")
    for path in directory.iterdir():
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise AgentBomError("CSV conversion pack member must be a regular non-symlink file within 2 MB")
    report, expected = csv_payloads(load_json(directory / "plan.json"), _read_source(directory / "source.csv"))
    for name, value in expected.items():
        if (directory / name).read_bytes() != value:
            raise AgentBomError(f"CSV conversion member does not recompute: {name}")
    if evaluation_path is not None and rendered(load_json(evaluation_path)) != expected["evaluation.json"]:
        raise AgentBomError("downstream evaluation does not match the verified CSV conversion")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau csv-eval", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("plan", type=Path)
    create.add_argument("csv", type=Path)
    create.add_argument("--out", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    verify.add_argument("--evaluation", type=Path, help="also bind the normalized evaluation in a downstream review dossier")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            create_csv_pack(load_json(args.plan), _read_source(args.csv), args.out)
            report = verify_csv_pack(args.out)
        else:
            report = verify_csv_pack(args.directory, evaluation_path=args.evaluation)
        print(f"CSV conversion verified: {report['observation_count']} supplied observations; no evaluator executed, not deployment approval.")
        return 0
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
