"""Derive the public incident exchange from reviewed metadata and exact artifacts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MODULE_PATH = HERE / "aau_incident_exchange.py"


def exchange_module():
    spec = importlib.util.spec_from_file_location("aau_incident_exchange", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("incident exchange module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build() -> dict:
    module = exchange_module()
    source = json.loads((HERE / "source-records.json").read_text())
    entries = []
    for item in source["entries"]:
        path = ROOT / item["regression_path"]
        artifact_sha256 = module.digest(path.read_bytes())
        entries.append(
            {
                "incident_id": item["incident_id"],
                "title": item["title"],
                "summary": item["summary"],
                "published_at": item["published_at"],
                "updated_at": item["updated_at"],
                "status": item["status"],
                "severity": item["severity"],
                "affected": item["affected"],
                "failure_shapes": sorted(item["failure_shapes"]),
                "authority_boundary": item["authority_boundary"],
                "regression": {
                    "artifact_path": item["regression_path"],
                    "artifact_sha256": artifact_sha256,
                    "clean_twin_present": item["clean_twin_present"],
                    "post_fix_status": item["post_fix_status"],
                },
                "sources": item["sources"],
                "disclosure": {
                    "tlp": "TLP:CLEAR",
                    "public_or_synthetic_only": True,
                    "credentials_excluded": True,
                    "personal_data_excluded": True,
                    "targets_excluded": True,
                    "exploit_instructions_excluded": True,
                    "raw_traces_excluded": True,
                },
            }
        )
    exchange = {
        "exchange_version": module.EXCHANGE_VERSION,
        "exchange_id": source["exchange_id"],
        "title": source["title"],
        "publisher": {
            "name": "Awesome Agentic Use Cases",
            "namespace": "https://github.com/immu4989/awesome-agentic-usecases",
            "contact": "https://github.com/immu4989/awesome-agentic-usecases/security",
        },
        "published_at": source["published_at"],
        "entries": entries,
        "boundary": {
            "public_or_synthetic_only": True,
            "no_credentials_targets_or_personal_data": True,
            "no_exploit_instructions": True,
            "not_attribution_or_original_incident_reproduction": True,
            "not_vulnerability_database_or_regulator_feed": True,
            "not_certification_or_field_effectiveness": True,
        },
        "exchange_sha256": "",
    }
    exchange["exchange_sha256"] = module.digest(
        {key: value for key, value in exchange.items() if key != "exchange_sha256"}
    )
    module.verify_artifact_bindings(exchange, ROOT)
    return exchange


def main() -> None:
    out = HERE / "examples" / "reference-exchange.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(), indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
