#!/usr/bin/env python3
"""Build a deterministic Federal Pilot Kit release, manifest, and SPDX SBOM."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path


KIT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/immu4989/awesome-agentic-usecases"
BUILDER_VERSION = "0.4"
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.-]+)?$")
REVISION = re.compile(r"^[a-f0-9]{40}$")
FIXED_ZIP_MODE = 0o100644 << 16

ROOT_FILES = (
    "README.md",
    "aau_pilot.py",
    "verify_release.py",
    "agency-intake.schema.json",
    "vendor-evidence-response.schema.json",
    "acceptance-test-manifest.schema.json",
    "lesson-record.schema.json",
    "acquisition-review-prompts.json",
    "THREAT_MODEL.md",
    "RELEASE_VERIFICATION.md",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_paths() -> list[Path]:
    paths = [KIT / name for name in ROOT_FILES]
    paths.extend(sorted((KIT / "examples").glob("*/*.json")))
    paths.extend(sorted((KIT / "pilot-launch").glob("*.md")))
    paths.extend(sorted((KIT / "lessons").glob("*.json")))
    paths.extend(sorted((KIT / "lessons").glob("*.md")))
    paths.extend(sorted((KIT / "lessons" / "examples").glob("*.json")))
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise ValueError(f"release source is missing: {missing[0].relative_to(KIT)}")
    if any(path.is_symlink() for path in paths):
        raise ValueError("release sources must not be symbolic links")
    return sorted(paths, key=lambda path: path.relative_to(KIT).as_posix())


def normalized_created(value: str | None) -> tuple[str, tuple[int, int, int, int, int, int]]:
    if value:
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("--source-date must be an ISO 8601 date-time") from exc
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        moment = moment.astimezone(timezone.utc).replace(microsecond=0)
    else:
        moment = datetime(2026, 8, 19, tzinfo=timezone.utc)
    created = moment.isoformat().replace("+00:00", "Z")
    zip_year = min(2107, max(1980, moment.year))
    return created, (zip_year, moment.month, moment.day, moment.hour, moment.minute, moment.second)


def spdx_document(
    version: str,
    revision: str,
    created: str,
    payload: dict[str, bytes],
) -> dict:
    content_fingerprint = sha256(
        "".join(f"{name}\0{sha256(data)}\n" for name, data in payload.items()).encode()
    )
    files = []
    relationships = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": "SPDXRef-Package",
        }
    ]
    sha1_values = []
    for name, data in payload.items():
        file_sha1 = hashlib.sha1(data).hexdigest()
        file_id = f"SPDXRef-File-{hashlib.sha1(name.encode()).hexdigest()[:16]}"
        sha1_values.append(file_sha1)
        files.append(
            {
                "fileName": f"./{name}",
                "SPDXID": file_id,
                "checksums": [
                    {"algorithm": "SHA256", "checksumValue": sha256(data)},
                    {"algorithm": "SHA1", "checksumValue": file_sha1},
                ],
                "licenseConcluded": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-Package",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": file_id,
            }
        )
    verification_code = hashlib.sha1("".join(sorted(sha1_values)).encode()).hexdigest()
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"AAU Federal Pilot Kit {version}",
        "documentNamespace": f"{REPOSITORY}/spdx/federal-pilot-kit/{version}/{content_fingerprint}",
        "creationInfo": {
            "created": created,
            "creators": [
                f"Tool: aau-federal-pilot-release-builder-{BUILDER_VERSION}",
                "Organization: Awesome Agentic Use Cases contributors",
            ],
        },
        "documentDescribes": ["SPDXRef-Package"],
        "packages": [
            {
                "name": "aau-federal-pilot-kit",
                "SPDXID": "SPDXRef-Package",
                "versionInfo": version,
                "downloadLocation": f"{REPOSITORY}/releases/tag/federal-pilot-v{version}",
                "filesAnalyzed": True,
                "packageVerificationCode": {
                    "packageVerificationCodeValue": verification_code,
                },
                "licenseConcluded": "Apache-2.0",
                "licenseDeclared": "Apache-2.0",
                "copyrightText": "NOASSERTION",
                "supplier": "Organization: Awesome Agentic Use Cases contributors",
                "sourceInfo": f"Repository revision: {revision}",
            }
        ],
        "files": files,
        "relationships": relationships,
    }


def write_zip(path: Path, root_name: str, payload: dict[str, bytes], timestamp: tuple[int, ...]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in payload.items():
            info = zipfile.ZipInfo(f"{root_name}/{name}", date_time=timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = FIXED_ZIP_MODE
            info.create_system = 3
            archive.writestr(info, data)


def build(version: str, revision: str, source_date: str | None, output: Path) -> list[Path]:
    if not VERSION.fullmatch(version):
        raise ValueError("version must look like 0.4.0 or 0.4.0-rc.1")
    if revision != "local-uncommitted" and not REVISION.fullmatch(revision):
        raise ValueError("source revision must be a 40-character lowercase Git commit")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"refusing to overwrite non-empty output path: {output}")
    output.mkdir(parents=True, exist_ok=True)
    created, zip_timestamp = normalized_created(source_date)
    payload = {
        path.relative_to(KIT).as_posix(): path.read_bytes()
        for path in source_paths()
    }
    manifest = {
        "release_manifest_version": "aau-federal-pilot-release/0.4",
        "name": "AAU Federal Pilot Kit",
        "version": version,
        "source_repository": REPOSITORY,
        "source_revision": revision,
        "created": created,
        "hash_algorithm": "sha256",
        "files": [
            {"path": name, "sha256": sha256(data), "bytes": len(data)}
            for name, data in payload.items()
        ],
        "claims": {
            "reproducible_source_bundle": True,
            "federal_approval": False,
            "compliance_certification": False,
            "authority_to_operate": False,
        },
    }
    sbom = spdx_document(version, revision, created, payload)
    sbom_bytes = (json.dumps(sbom, indent=2) + "\n").encode()
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()
    payload["RELEASE-MANIFEST.json"] = manifest_bytes
    payload["SBOM.spdx.json"] = sbom_bytes

    stem = f"aau-federal-pilot-kit-v{version}"
    archive_path = output / f"{stem}.zip"
    sbom_path = output / f"{stem}.spdx.json"
    write_zip(archive_path, stem, payload, zip_timestamp)
    sbom_path.write_bytes(sbom_bytes)
    sums_path = output / "SHA256SUMS"
    sums_path.write_text(
        f"{sha256(archive_path.read_bytes())}  {archive_path.name}\n"
        f"{sha256(sbom_bytes)}  {sbom_path.name}\n",
        encoding="utf-8",
    )
    return [archive_path, sbom_path, sums_path]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--version", default="0.4.0")
    value.add_argument("--source-revision", default="local-uncommitted")
    value.add_argument("--source-date")
    value.add_argument("--output", type=Path, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        paths = build(args.version, args.source_revision, args.source_date, args.output)
    except ValueError as exc:
        raise SystemExit(f"release build failed: {exc}") from exc
    print("Federal Pilot Kit release built:")
    for path in paths:
        print(f"- {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
