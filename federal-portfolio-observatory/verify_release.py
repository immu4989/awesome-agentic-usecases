#!/usr/bin/env python3
"""Verify a Portfolio Observatory ZIP, SPDX inventory, and checksum file."""

from __future__ import annotations

import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath


RELEASE_VERSION = "aau-federal-portfolio-release/0.5"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"release verification failed: {message}")


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: verify_release.py DIST_DIRECTORY")
    directory = Path(sys.argv[1])
    if not directory.is_dir():
        fail("release path must be a directory")
    sums_path = directory / "SHA256SUMS"
    if not sums_path.is_file():
        fail("SHA256SUMS is missing")
    sums = {}
    for line in sums_path.read_text().splitlines():
        checksum, name = line.split("  ", 1)
        if PurePosixPath(name).name != name or name in sums:
            fail("checksum file contains an unsafe or duplicate name")
        sums[name] = checksum
    if len(sums) != 2:
        fail("checksum file must name exactly the ZIP and SPDX document")
    for name, expected in sums.items():
        path = directory / name
        if not path.is_file() or digest(path.read_bytes()) != expected:
            fail(f"checksum differs for {name}")
    archives = [name for name in sums if name.endswith(".zip")]
    spdx_names = [name for name in sums if name.endswith(".spdx.json")]
    if len(archives) != 1 or len(spdx_names) != 1:
        fail("release must contain one ZIP and one SPDX document")
    archive = directory / archives[0]
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)):
            fail("ZIP contains duplicate names")
        roots = {PurePosixPath(name).parts[0] for name in names}
        if len(roots) != 1:
            fail("ZIP must have one release root")
        root = next(iter(roots))
        for info in bundle.infolist():
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or stat.S_ISLNK(info.external_attr >> 16):
                fail(f"unsafe ZIP member: {info.filename}")
        manifest_name = f"{root}/manifest.json"
        if manifest_name not in names:
            fail("manifest is missing from ZIP")
        manifest = json.loads(bundle.read(manifest_name))
        if manifest.get("manifest_version") != RELEASE_VERSION:
            fail("manifest version is invalid")
        listed = {item["path"]: item for item in manifest.get("files", [])}
        actual = {name.removeprefix(f"{root}/") for name in names} - {"manifest.json"}
        if set(listed) != actual:
            fail("manifest and ZIP member sets differ")
        for name, item in listed.items():
            data = bundle.read(f"{root}/{name}")
            if len(data) != item["bytes"] or digest(data) != item["sha256"]:
                fail(f"manifest evidence differs for {name}")
        spdx = json.loads((directory / spdx_names[0]).read_text())
        if spdx.get("spdxVersion") != "SPDX-2.3":
            fail("SPDX version is invalid")
        spdx_files = {
            item["fileName"].removeprefix("./"): item["checksums"][0]["checksumValue"]
            for item in spdx.get("files", [])
        }
        all_files = actual | {"manifest.json"}
        if set(spdx_files) != all_files:
            fail("SPDX and ZIP file sets differ")
        for name in all_files:
            if spdx_files[name] != digest(bundle.read(f"{root}/{name}")):
                fail(f"SPDX digest differs for {name}")
    print(f"Portfolio Observatory release verified: {root}")


if __name__ == "__main__":
    main()
