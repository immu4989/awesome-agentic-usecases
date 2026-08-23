#!/usr/bin/env python3
"""Build a deterministic, self-verifying Portfolio Observatory release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path


KIT = Path(__file__).resolve().parents[1]
ROOT = KIT.parent
RELEASE_VERSION = "aau-federal-portfolio-release/0.5"
SOURCE_FILES = (
    "README.md",
    "aau_portfolio.py",
    "inventory.schema.json",
    "public-value-ledger.schema.json",
    "three-layer-tev-v.schema.json",
    "clause-testbench.schema.json",
    "sources.json",
    "examples/synthetic-agency-inventory.json",
    "examples/public-value-ledger.json",
    "examples/three-layer-tev-v-plan.json",
    "examples/clause-testbench.json",
    "tests/test_aau_portfolio.py",
    "verify_release.py",
    "RELEASE_VERIFICATION.md",
)


def canonical(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_bytes() -> dict[str, bytes]:
    files = {name: (KIT / name).read_bytes() for name in SOURCE_FILES}
    files["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    return files


def spdx_document(
    version: str, revision: str, created: str, files: dict[str, bytes]
) -> dict:
    file_rows = []
    relationships = []
    for index, (name, data) in enumerate(sorted(files.items()), start=1):
        spdx_id = f"SPDXRef-File-{index}"
        file_rows.append(
            {
                "SPDXID": spdx_id,
                "fileName": f"./{name}",
                "checksums": [{"algorithm": "SHA256", "checksumValue": digest(data)}],
                "licenseConcluded": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-Package",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": spdx_id,
            }
        )
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"AAU Federal AI Portfolio Observatory {version}",
        "documentNamespace": f"https://github.com/immu4989/awesome-agentic-usecases/releases/federal-portfolio-v{version}/{revision}",
        "creationInfo": {
            "created": created,
            "creators": ["Tool: federal-portfolio-observatory/tools/build_release.py"],
        },
        "packages": [
            {
                "name": "aau-federal-portfolio-observatory",
                "SPDXID": "SPDXRef-Package",
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": True,
                "licenseConcluded": "Apache-2.0",
                "licenseDeclared": "Apache-2.0",
                "copyrightText": "NOASSERTION",
            }
        ],
        "files": file_rows,
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": "SPDXRef-Package",
            },
            *relationships,
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?", args.version):
        raise SystemExit("version must be SemVer without a leading v")
    if not re.fullmatch(r"[a-f0-9]{40}", args.source_revision):
        raise SystemExit("source revision must be a full lowercase commit SHA")
    source_date = datetime.fromisoformat(args.source_date.replace("Z", "+00:00")).astimezone(timezone.utc)
    zip_time = (source_date.year, source_date.month, source_date.day, source_date.hour, source_date.minute, source_date.second)
    files = source_bytes()
    manifest = {
        "manifest_version": RELEASE_VERSION,
        "release_version": args.version,
        "source_revision": args.source_revision,
        "source_date": source_date.isoformat().replace("+00:00", "Z"),
        "hash_algorithm": "sha256",
        "files": [
            {"path": name, "sha256": digest(data), "bytes": len(data)}
            for name, data in sorted(files.items())
        ],
        "claims": {
            "official_government_artifact": False,
            "investment_recommendation": False,
            "award_recommendation": False,
            "compliance_certification": False,
            "audited_savings": False,
        },
    }
    files["manifest.json"] = canonical(manifest)
    args.output.mkdir(parents=True, exist_ok=True)
    stem = f"aau-federal-portfolio-observatory-v{args.version}"
    archive = args.output / f"{stem}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(f"{stem}/{name}", zip_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, data)
    spdx_path = args.output / f"{stem}.spdx.json"
    spdx_path.write_bytes(
        canonical(
            spdx_document(
                args.version,
                args.source_revision,
                source_date.isoformat().replace("+00:00", "Z"),
                files,
            )
        )
    )
    sums = args.output / "SHA256SUMS"
    sums.write_text(
        "".join(
            f"{digest(path.read_bytes())}  {path.name}\n"
            for path in (archive, spdx_path)
        )
    )
    print(f"built {archive.name}, {spdx_path.name}, and SHA256SUMS")


if __name__ == "__main__":
    main()
