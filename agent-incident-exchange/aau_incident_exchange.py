"""Privacy-bounded, machine-readable exchange for public agent incident lessons."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


EXCHANGE_VERSION = "aau-agent-incident-exchange/1.0"
PACK_VERSION = "aau-agent-incident-exchange-pack/1.0"
MAX_BYTES = 2_000_000
MAX_ENTRIES = 500
STATUSES = {"under_investigation", "mitigation_available", "fixed_in_fixture", "withdrawn"}
SEVERITIES = {"critical", "high", "medium", "low", "unknown"}
TLP = {"TLP:CLEAR", "TLP:GREEN"}
HEX = set("0123456789abcdef")
BOUNDARY_KEYS = {
    "public_or_synthetic_only",
    "no_credentials_targets_or_personal_data",
    "no_exploit_instructions",
    "not_attribution_or_original_incident_reproduction",
    "not_vulnerability_database_or_regulator_feed",
    "not_certification_or_field_effectiveness",
}


class ExchangeError(ValueError):
    """Raised when public incident exchange evidence violates the contract."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def rendered(value: Any) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode()


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(payload).hexdigest()


def _text(value: Any, label: str, limit: int = 600) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ExchangeError(f"{label} must be non-empty text of at most {limit} characters")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ExchangeError(f"{label} fields differ from the 1.0 contract")
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in HEX for char in value):
        raise ExchangeError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _date_time(value: Any, label: str) -> str:
    value = _text(value, label, 40)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExchangeError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ExchangeError(f"{label} must include a timezone")
    return value


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ExchangeError(f"invalid, oversized, or symbolic-link file: {path}")
    try:
        value = json.loads(path.read_text())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExchangeError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExchangeError(f"expected one JSON object in {path}")
    return value


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise ExchangeError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(rendered(value))


def validate_exchange(exchange: dict[str, Any]) -> None:
    _exact(
        exchange,
        {
            "exchange_version",
            "exchange_id",
            "title",
            "publisher",
            "published_at",
            "entries",
            "boundary",
            "exchange_sha256",
        },
        "incident exchange",
    )
    if exchange["exchange_version"] != EXCHANGE_VERSION:
        raise ExchangeError(f"exchange_version must be {EXCHANGE_VERSION}")
    _text(exchange["exchange_id"], "exchange_id", 120)
    _text(exchange["title"], "exchange title", 240)
    publisher = _exact(exchange["publisher"], {"name", "namespace", "contact"}, "publisher")
    _text(publisher["name"], "publisher name", 160)
    _text(publisher["namespace"], "publisher namespace", 300)
    if not publisher["namespace"].startswith("https://"):
        raise ExchangeError("publisher namespace must use HTTPS")
    _text(publisher["contact"], "publisher contact", 300)
    _date_time(exchange["published_at"], "published_at")
    entries = exchange["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENTRIES:
        raise ExchangeError(f"entries must contain 1 to {MAX_ENTRIES} items")
    ids: set[str] = set()
    for index, entry in enumerate(entries):
        entry = _exact(
            entry,
            {
                "incident_id",
                "title",
                "summary",
                "published_at",
                "updated_at",
                "status",
                "severity",
                "affected",
                "failure_shapes",
                "authority_boundary",
                "regression",
                "sources",
                "disclosure",
            },
            f"entries[{index}]",
        )
        incident_id = _text(entry["incident_id"], "incident_id", 120)
        if incident_id in ids:
            raise ExchangeError(f"duplicate incident_id: {incident_id}")
        ids.add(incident_id)
        _text(entry["title"], "entry title", 240)
        _text(entry["summary"], "entry summary")
        _date_time(entry["published_at"], "entry published_at")
        _date_time(entry["updated_at"], "entry updated_at")
        if entry["status"] not in STATUSES or entry["severity"] not in SEVERITIES:
            raise ExchangeError("entry status or severity is unsupported")
        affected = _exact(entry["affected"], {"components", "protocols"}, "affected")
        if not isinstance(affected["components"], list) or not affected["components"]:
            raise ExchangeError("affected components must be non-empty")
        for component in affected["components"]:
            component = _exact(component, {"name", "ecosystem", "versions"}, "affected component")
            _text(component["name"], "component name", 160)
            _text(component["ecosystem"], "component ecosystem", 120)
            if not isinstance(component["versions"], list) or not component["versions"]:
                raise ExchangeError("component versions must be non-empty")
            for version in component["versions"]:
                _text(version, "component version", 120)
        if not isinstance(affected["protocols"], list):
            raise ExchangeError("affected protocols must be a list")
        for protocol in affected["protocols"]:
            _text(protocol, "affected protocol", 120)
        shapes = entry["failure_shapes"]
        if not isinstance(shapes, list) or not shapes or len(shapes) != len(set(shapes)):
            raise ExchangeError("failure_shapes must be a unique non-empty list")
        for shape in shapes:
            _text(shape, "failure shape", 160)
        _text(entry["authority_boundary"], "authority_boundary")
        regression = _exact(
            entry["regression"],
            {"artifact_path", "artifact_sha256", "clean_twin_present", "post_fix_status"},
            "regression",
        )
        path = _text(regression["artifact_path"], "regression artifact_path", 300)
        if Path(path).is_absolute() or ".." in Path(path).parts:
            raise ExchangeError("regression artifact_path must be repository relative")
        _sha(regression["artifact_sha256"], "regression artifact_sha256")
        if regression["clean_twin_present"] is not True:
            raise ExchangeError("every exchange entry must preserve a clean twin")
        if regression["post_fix_status"] not in {"not_tested", "fixture_passed", "independently_reproduced"}:
            raise ExchangeError("regression post_fix_status is unsupported")
        sources = entry["sources"]
        if not isinstance(sources, list) or not sources:
            raise ExchangeError("entry sources must be non-empty")
        for source in sources:
            source = _exact(source, {"title", "publisher", "url", "reviewed_on"}, "source")
            _text(source["title"], "source title", 300)
            _text(source["publisher"], "source publisher", 160)
            if not _text(source["url"], "source URL", 600).startswith("https://"):
                raise ExchangeError("source URLs must use HTTPS")
            _text(source["reviewed_on"], "source reviewed_on", 20)
        disclosure = _exact(
            entry["disclosure"],
            {
                "tlp",
                "public_or_synthetic_only",
                "credentials_excluded",
                "personal_data_excluded",
                "targets_excluded",
                "exploit_instructions_excluded",
                "raw_traces_excluded",
            },
            "disclosure",
        )
        if disclosure["tlp"] not in TLP or any(
            disclosure[key] is not True for key in disclosure if key != "tlp"
        ):
            raise ExchangeError("disclosure must preserve the public defensive boundary")
    boundary = _exact(exchange["boundary"], BOUNDARY_KEYS, "exchange boundary")
    if any(boundary[key] is not True for key in BOUNDARY_KEYS):
        raise ExchangeError("all exchange boundaries must be true")
    _sha(exchange["exchange_sha256"], "exchange_sha256")
    expected = digest({key: value for key, value in exchange.items() if key != "exchange_sha256"})
    if exchange["exchange_sha256"] != expected:
        raise ExchangeError("exchange embedded digest mismatch")


def verify_artifact_bindings(exchange: dict[str, Any], root: Path) -> None:
    validate_exchange(exchange)
    root = root.resolve()
    for entry in exchange["entries"]:
        relative = Path(entry["regression"]["artifact_path"])
        target = root / relative
        current = root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ExchangeError(f"regression path contains a symlink: {relative}")
        resolved = target.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ExchangeError("regression path escapes repository root") from exc
        if not resolved.is_file() or resolved.stat().st_size > MAX_BYTES:
            raise ExchangeError(f"missing or oversized regression artifact: {relative}")
        if digest(resolved.read_bytes()) != entry["regression"]["artifact_sha256"]:
            raise ExchangeError(f"regression artifact digest drift: {relative}")


def sarif_export(exchange: dict[str, Any]) -> dict[str, Any]:
    validate_exchange(exchange)
    rules = {}
    results = []
    level_map = {"critical": "error", "high": "error", "medium": "warning", "low": "note", "unknown": "none"}
    for entry in exchange["entries"]:
        for shape in entry["failure_shapes"]:
            rule_id = "AAU-" + "-".join(part.upper() for part in shape.replace("_", " ").split())
            rules.setdefault(
                rule_id,
                {
                    "id": rule_id,
                    "name": shape.replace("_", " ").title().replace(" ", ""),
                    "shortDescription": {"text": shape.replace("_", " ")},
                    "helpUri": entry["sources"][0]["url"],
                    "properties": {"tags": ["agentic-ai", "defensive", "public-synthetic"]},
                },
            )
            results.append(
                {
                    "ruleId": rule_id,
                    "level": level_map[entry["severity"]],
                    "message": {"text": f"{entry['incident_id']}: {entry['summary']}"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": entry["regression"]["artifact_path"]}
                            }
                        }
                    ],
                    "properties": {
                        "incidentId": entry["incident_id"],
                        "status": entry["status"],
                        "regressionSha256": entry["regression"]["artifact_sha256"],
                    },
                }
            )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "AAU Agent Incident Exchange",
                        "informationUri": exchange["publisher"]["namespace"],
                        "rules": [rules[key] for key in sorted(rules)],
                    }
                },
                "results": results,
                "properties": {
                    "boundary": "Public synthetic defensive findings; not attribution, certification, or production vulnerability status."
                },
            }
        ],
    }


def openvex_export(exchange: dict[str, Any]) -> dict[str, Any]:
    validate_exchange(exchange)
    status_map = {
        "under_investigation": "under_investigation",
        "mitigation_available": "affected",
        "fixed_in_fixture": "fixed",
        "withdrawn": "not_affected",
    }
    statements = []
    for entry in exchange["entries"]:
        statements.append(
            {
                "vulnerability": {"@id": f"urn:aau:agent-incident:{entry['incident_id']}"},
                "products": [
                    {"@id": f"pkg:generic/{component['name']}@{version}"}
                    for component in entry["affected"]["components"]
                    for version in component["versions"]
                ],
                "status": status_map[entry["status"]],
                "status_notes": (
                    f"{entry['summary']} Post-fix status: {entry['regression']['post_fix_status']}. "
                    "AAU public-synthetic abstraction; not a production vulnerability determination."
                ),
                "action_statement": entry["authority_boundary"],
                "timestamp": entry["updated_at"],
            }
        )
    return {
        "@context": "https://openvex.dev/ns/v0.2.0",
        "@id": f"{exchange['publisher']['namespace'].rstrip('/')}/incident-exchange/{exchange['exchange_id']}",
        "author": exchange["publisher"]["name"],
        "timestamp": exchange["published_at"],
        "version": 1,
        "tooling": "AAU Agent Incident Exchange 1.0",
        "statements": statements,
    }


def csaf_bridge(exchange: dict[str, Any]) -> dict[str, Any]:
    validate_exchange(exchange)
    products = []
    vulnerabilities = []
    for entry in exchange["entries"]:
        product_ids = []
        for component in entry["affected"]["components"]:
            for version in component["versions"]:
                product_id = f"{component['ecosystem']}:{component['name']}:{version}"
                product_ids.append(product_id)
                products.append(
                    {
                        "category": "product_name",
                        "name": f"{component['name']} {version}",
                        "product": {"name": component["name"], "product_id": product_id},
                    }
                )
        vulnerabilities.append(
            {
                "title": entry["incident_id"],
                "notes": [
                    {"category": "summary", "text": entry["summary"], "title": entry["title"]},
                    {"category": "general", "text": entry["authority_boundary"], "title": "Authority boundary"},
                ],
                "product_status": {
                    (
                        "fixed"
                        if entry["status"] == "fixed_in_fixture"
                        else "under_investigation"
                        if entry["status"] == "under_investigation"
                        else "known_affected"
                    ): product_ids
                },
                "references": [
                    {"category": "external", "summary": source["title"], "url": source["url"]}
                    for source in entry["sources"]
                ],
            }
        )
    unique_products = {item["product"]["product_id"]: item for item in products}
    return {
        "document": {
            "category": "csaf_security_advisory",
            "csaf_version": "2.0",
            "publisher": {
                "category": "other",
                "name": exchange["publisher"]["name"],
                "namespace": exchange["publisher"]["namespace"],
            },
            "title": exchange["title"],
            "tracking": {
                "current_release_date": exchange["published_at"],
                "id": exchange["exchange_id"],
                "initial_release_date": exchange["published_at"],
                "revision_history": [
                    {"date": exchange["published_at"], "number": "1", "summary": "Initial public synthetic exchange"}
                ],
                "status": "draft",
                "version": "1",
            },
            "notes": [
                {
                    "category": "legal_disclaimer",
                    "title": "Experimental bridge boundary",
                    "text": "Not validated as a CSAF advisory, vulnerability database record, attribution, production impact statement, certification, or regulator feed.",
                }
            ],
        },
        "product_tree": {"branches": [unique_products[key] for key in sorted(unique_products)]},
        "vulnerabilities": vulnerabilities,
        "x_aau_bridge": {"experimental": True, "validated_against_csaf_schema": False},
    }


def ocsf_bridge(exchange: dict[str, Any]) -> dict[str, Any]:
    validate_exchange(exchange)
    events = []
    severity_map = {"unknown": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    for entry in exchange["entries"]:
        events.append(
            {
                "activity_name": "Agent incident lesson published",
                "category_name": "Findings",
                "class_name": "Detection Finding",
                "message": entry["summary"],
                "severity_id": severity_map[entry["severity"]],
                "status": entry["status"],
                "time": int(datetime.fromisoformat(entry["updated_at"].replace("Z", "+00:00")).timestamp() * 1000),
                "finding_info": {"uid": entry["incident_id"], "title": entry["title"], "types": entry["failure_shapes"]},
                "resources": [
                    {"name": component["name"], "type": component["ecosystem"]}
                    for component in entry["affected"]["components"]
                ],
                "unmapped": {
                    "aau_regression_sha256": entry["regression"]["artifact_sha256"],
                    "aau_authority_boundary": entry["authority_boundary"],
                    "aau_experimental_bridge": True,
                },
            }
        )
    return {
        "bridge_version": "aau-ocsf-agent-incident-bridge/0.1",
        "ocsf_target_version": "1.4.0",
        "validated_against_ocsf_schema": False,
        "events": events,
        "boundary": "Experimental field mapping; not an official OCSF extension or conformance claim.",
    }


def pack_payloads(exchange: dict[str, Any], root: Path) -> dict[str, bytes]:
    verify_artifact_bindings(exchange, root)
    payloads = {
        "README.md": (
            "# AAU Agent Incident Exchange pack\n\n"
            "Public or synthetic defensive lessons with artifact-bound regressions and experimental "
            "SARIF, OpenVEX, CSAF, and OCSF views. The CSAF and OCSF files are bridges, not schema-"
            "validated conformance. No file is attribution, an original-incident reproduction, a "
            "production vulnerability determination, certification, or regulator feed.\n"
        ).encode(),
        "exchange.json": rendered(exchange),
        "findings.sarif.json": rendered(sarif_export(exchange)),
        "statements.openvex.json": rendered(openvex_export(exchange)),
        "advisories.csaf-bridge.json": rendered(csaf_bridge(exchange)),
        "events.ocsf-bridge.json": rendered(ocsf_bridge(exchange)),
    }
    files = [
        {"path": name, "bytes": len(data), "sha256": digest(data)}
        for name, data in sorted(payloads.items())
    ]
    payloads["manifest.json"] = rendered({"manifest_version": PACK_VERSION, "files": files})
    return payloads


def build_pack(exchange: dict[str, Any], root: Path, out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise ExchangeError(f"refusing to overwrite exchange pack: {out}")
    payloads = pack_payloads(exchange, root)
    out.mkdir(parents=True)
    for name, data in payloads.items():
        (out / name).write_bytes(data)


def verify_pack(pack: Path, root: Path) -> dict[str, Any]:
    if pack.is_symlink() or not pack.is_dir():
        raise ExchangeError(f"invalid exchange pack: {pack}")
    manifest = load_json(pack / "manifest.json")
    if manifest.get("manifest_version") != PACK_VERSION or not isinstance(manifest.get("files"), list):
        raise ExchangeError("exchange pack manifest is invalid")
    expected = {
        "README.md",
        "exchange.json",
        "findings.sarif.json",
        "statements.openvex.json",
        "advisories.csaf-bridge.json",
        "events.ocsf-bridge.json",
    }
    if {item.get("path") for item in manifest["files"]} != expected:
        raise ExchangeError("exchange pack manifest file set is invalid")
    actual = {path.name for path in pack.iterdir()}
    if actual != expected | {"manifest.json"}:
        raise ExchangeError("exchange pack contains unmanifested or missing files")
    for item in manifest["files"]:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
            raise ExchangeError("exchange manifest entry is invalid")
        target = pack / item["path"]
        if target.is_symlink() or not target.is_file():
            raise ExchangeError("exchange pack file is missing or symbolic")
        data = target.read_bytes()
        if len(data) != item["bytes"] or digest(data) != item["sha256"]:
            raise ExchangeError(f"exchange pack integrity mismatch: {item['path']}")
    exchange = load_json(pack / "exchange.json")
    expected_payloads = pack_payloads(exchange, root)
    for name in expected:
        if (pack / name).read_bytes() != expected_payloads[name]:
            raise ExchangeError(f"derived exchange artifact does not recompute: {name}")
    return exchange


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Build privacy-bounded agent incident exchange evidence")
    sub = root.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("exchange", type=Path)
    validate.add_argument("--root", type=Path, default=Path.cwd())
    pack = sub.add_parser("pack")
    pack.add_argument("exchange", type=Path)
    pack.add_argument("--root", type=Path, default=Path.cwd())
    pack.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify-pack")
    verify.add_argument("pack", type=Path)
    verify.add_argument("--root", type=Path, default=Path.cwd())
    export = sub.add_parser("export")
    export.add_argument("exchange", type=Path)
    export.add_argument("format", choices=("sarif", "openvex", "csaf-bridge", "ocsf-bridge"))
    export.add_argument("--out", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "verify-pack":
            exchange = verify_pack(args.pack, args.root)
            print(f"OK: exchange pack verified with {len(exchange['entries'])} entries.")
            return 0
        exchange = load_json(args.exchange)
        if args.command == "validate":
            verify_artifact_bindings(exchange, args.root)
            print(f"OK: {len(exchange['entries'])} incident entries and regression bindings verified.")
        elif args.command == "pack":
            build_pack(exchange, args.root, args.out)
            print(f"OK: incident exchange pack written to {args.out}.")
        else:
            exporters = {
                "sarif": sarif_export,
                "openvex": openvex_export,
                "csaf-bridge": csaf_bridge,
                "ocsf-bridge": ocsf_bridge,
            }
            write_json(exporters[args.format](exchange), args.out)
            print(f"OK: {args.format} export written to {args.out}.")
        return 0
    except ExchangeError as exc:
        print(f"aau incident exchange: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
