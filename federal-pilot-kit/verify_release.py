#!/usr/bin/env python3
"""Verify checksums, archive safety, manifest integrity, and SBOM parity."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


SHA256 = re.compile(r"^[a-f0-9]{64}$")
MAX_FILES = 200
MAX_TOTAL_BYTES = 25_000_000
MAX_JSON_BYTES = 5_000_000
MAX_RELEASE_ARTIFACT_BYTES = 30_000_000


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    if len(data) > MAX_JSON_BYTES:
        raise ValueError(f"{label} exceeds the {MAX_JSON_BYTES}-byte limit")
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} root must be an object")
    return value


def checksum_entries(path: Path) -> dict[str, str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("SHA256SUMS must be a regular file")
    if path.stat().st_size > 10_000:
        raise ValueError("SHA256SUMS exceeds the 10,000-byte limit")
    entries: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        parts = line.split("  ", 1)
        if len(parts) != 2 or not SHA256.fullmatch(parts[0]):
            raise ValueError(f"invalid SHA256SUMS line {number}")
        name = parts[1]
        if name != Path(name).name or name in entries:
            raise ValueError(f"unsafe or duplicate checksum path on line {number}")
        entries[name] = parts[0]
    if len(entries) != 2:
        raise ValueError("SHA256SUMS must list exactly the release archive and external SBOM")
    return entries


def safe_members(archive: zipfile.ZipFile) -> tuple[str, dict[str, zipfile.ZipInfo]]:
    members = archive.infolist()
    if not members or len(members) > MAX_FILES:
        raise ValueError(f"archive must contain 1-{MAX_FILES} files")
    names: set[str] = set()
    roots: set[str] = set()
    result: dict[str, zipfile.ZipInfo] = {}
    total = 0
    for member in members:
        name = member.filename
        path = PurePosixPath(name)
        if (
            name in names
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or path.as_posix() != name
        ):
            raise ValueError(f"unsafe or duplicate archive path: {name}")
        if len(path.parts) < 2 or name.endswith("/"):
            raise ValueError(f"archive member must be a file below one release root: {name}")
        mode = (member.external_attr >> 16) & 0o170000
        if mode == 0o120000:
            raise ValueError(f"symbolic links are not permitted in the release: {name}")
        if member.file_size > 1_000_000 and member.compress_size == 0:
            raise ValueError(f"suspicious zero-byte compression record: {name}")
        if member.compress_size and member.file_size / member.compress_size > 100:
            raise ValueError(f"archive compression ratio exceeds 100:1: {name}")
        total += member.file_size
        if total > MAX_TOTAL_BYTES:
            raise ValueError(f"archive expands beyond {MAX_TOTAL_BYTES} bytes")
        names.add(name)
        roots.add(path.parts[0])
        result[PurePosixPath(*path.parts[1:]).as_posix()] = member
    if len(roots) != 1:
        raise ValueError("archive must use exactly one release root directory")
    return roots.pop(), result


def verify(directory: Path) -> dict[str, Any]:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("release path must be a regular directory")
    checksums = checksum_entries(directory / "SHA256SUMS")
    archive_names = [name for name in checksums if name.endswith(".zip")]
    sbom_names = [name for name in checksums if name.endswith(".spdx.json")]
    if len(archive_names) != 1 or len(sbom_names) != 1:
        raise ValueError("checksums must identify one .zip archive and one .spdx.json SBOM")
    for name, expected in checksums.items():
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"release artifact must be a regular file: {name}")
        if path.stat().st_size > MAX_RELEASE_ARTIFACT_BYTES:
            raise ValueError(f"release artifact exceeds {MAX_RELEASE_ARTIFACT_BYTES} bytes: {name}")
        if digest(path.read_bytes()) != expected:
            raise ValueError(f"checksum mismatch: {name}")

    archive_path = directory / archive_names[0]
    with zipfile.ZipFile(archive_path) as archive:
        root, members = safe_members(archive)
        for required in ("RELEASE-MANIFEST.json", "SBOM.spdx.json"):
            if required not in members:
                raise ValueError(f"archive is missing {required}")
        manifest = load_json_bytes(
            archive.read(members["RELEASE-MANIFEST.json"]), "release manifest"
        )
        internal_sbom_bytes = archive.read(members["SBOM.spdx.json"])
        sbom = load_json_bytes(internal_sbom_bytes, "internal SPDX SBOM")
        external_sbom_bytes = (directory / sbom_names[0]).read_bytes()
        if internal_sbom_bytes != external_sbom_bytes:
            raise ValueError("external and archived SPDX SBOM files differ")

        version = manifest.get("version")
        expected_root = f"aau-federal-pilot-kit-v{version}"
        if manifest.get("release_manifest_version") != "aau-federal-pilot-release/0.3":
            raise ValueError("release manifest contract version is not supported")
        if root != expected_root or archive_path.name != f"{expected_root}.zip":
            raise ValueError("archive name, root, and manifest version do not agree")
        if sbom_names[0] != f"{expected_root}.spdx.json":
            raise ValueError("external SBOM name and manifest version do not agree")
        packages = sbom.get("packages")
        if (
            sbom.get("spdxVersion") != "SPDX-2.3"
            or not isinstance(packages, list)
            or len(packages) != 1
            or not isinstance(packages[0], dict)
            or packages[0].get("name") != "aau-federal-pilot-kit"
            or packages[0].get("versionInfo") != version
        ):
            raise ValueError("SPDX document does not identify this release package and version")

        listed = manifest.get("files")
        if not isinstance(listed, list):
            raise ValueError("release manifest files must be an array")
        manifest_files: dict[str, dict[str, Any]] = {}
        for item in listed:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise ValueError("release manifest entries must be objects with paths")
            name = item["path"]
            if name in manifest_files or name not in members:
                raise ValueError(f"duplicate or missing manifest payload: {name}")
            if not SHA256.fullmatch(str(item.get("sha256", ""))):
                raise ValueError(f"invalid manifest digest: {name}")
            data = archive.read(members[name])
            if digest(data) != item["sha256"] or len(data) != item.get("bytes"):
                raise ValueError(f"manifest mismatch: {name}")
            manifest_files[name] = item
        payload_names = set(members) - {"RELEASE-MANIFEST.json", "SBOM.spdx.json"}
        if set(manifest_files) != payload_names:
            raise ValueError("release manifest does not cover the exact archive payload")

        sbom_files = sbom.get("files")
        if not isinstance(sbom_files, list):
            raise ValueError("SPDX files must be an array")
        sbom_digests: dict[str, str] = {}
        for item in sbom_files:
            if not isinstance(item, dict) or not isinstance(item.get("fileName"), str):
                raise ValueError("SPDX file entries must include fileName")
            name = item["fileName"].removeprefix("./")
            values = {
                check.get("algorithm"): check.get("checksumValue")
                for check in item.get("checksums", [])
                if isinstance(check, dict)
            }
            if name in sbom_digests or not SHA256.fullmatch(str(values.get("SHA256", ""))):
                raise ValueError(f"duplicate or invalid SPDX file entry: {name}")
            sbom_digests[name] = values["SHA256"]
        expected_sbom = {name: item["sha256"] for name, item in manifest_files.items()}
        if sbom_digests != expected_sbom:
            raise ValueError("SPDX inventory and release manifest differ")

    claims = manifest.get("claims", {})
    if any(
        claims.get(key) is not False
        for key in ("federal_approval", "compliance_certification", "authority_to_operate")
    ):
        raise ValueError("release manifest must preserve non-approval boundaries")
    return {
        "verified": True,
        "archive": archive_path.name,
        "release_root": root,
        "payload_files": len(manifest_files),
        "version": version,
        "source_revision": manifest.get("source_revision"),
        "sbom_format": sbom.get("spdxVersion"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = verify(args.directory)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"RELEASE INVALID — {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"RELEASE VERIFIED — {result['version']} · {result['payload_files']} files · "
            f"{result['sbom_format']}"
        )
        print("Local integrity is verified. Check the GitHub attestation separately for build provenance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
