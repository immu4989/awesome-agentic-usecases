"""Identify the installed first-party implementation without collecting local paths."""

import argparse
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
import platform
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json


def _unreadable(error):
    raise AgentBomError("runtime source tree could not be fully inspected") from error


def runtime_info(root: Path | None = None) -> dict:
    root = root if root is not None else Path(__file__).parent
    if root.is_symlink() or not root.is_dir():
        raise AgentBomError("runtime package must be a real directory")
    files, total = {}, 0
    for directory, folders, names in os.walk(root, followlinks=False, onerror=_unreadable):
        folders[:] = sorted(name for name in folders if name != "__pycache__")
        if any((Path(directory) / name).is_symlink() for name in folders):
            raise AgentBomError("runtime source directories cannot be symlinks")
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            path = Path(directory) / name
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
                raise AgentBomError("runtime source must be a bounded regular file")
            with path.open("rb") as stream:
                data = stream.read(MAX_JSON_BYTES + 1)
            total += len(data)
            if len(data) > MAX_JSON_BYTES or total > 20_000_000 or len(files) >= 500:
                raise AgentBomError("runtime source inventory exceeds its limits")
            files[path.relative_to(root).as_posix()] = digest(data)
    if not files or "__init__.py" not in files:
        raise AgentBomError("runtime package Python sources are unavailable")
    try:
        distribution_version = version("aau-harness")
    except PackageNotFoundError:
        distribution_version = None
    return {"report_version": "aau-runtime-source-receipt/1.0", "distribution_version": distribution_version,
            "python": {"implementation": platform.python_implementation(), "version": platform.python_version()},
            "source_tree_sha256": digest(files), "source_files": dict(sorted(files.items())),
            "boundary": "Inventory of on-disk first-party aau_harness .py bytes, not proof of executed or previously loaded code, authentic origin, dependencies, interpreter bytes, resources, configuration, scoring correctness, or deployment approval. Distribution metadata may describe a different source revision. No local paths, environment variables, credentials, timestamps, or hostnames are collected. Compare source_tree_sha256 separately from Python and distribution metadata; hashes are not signatures. Capture at collection and review time with a trusted harness."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau runtime-info", description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--out", type=Path)
    mode.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    try:
        report = runtime_info()
        if args.verify:
            if load_json(args.verify) != report:
                raise AgentBomError("runtime receipt differs from current first-party sources or declared runtime metadata")
            print("Runtime receipt matches current on-disk sources and metadata; not execution attestation.")
        elif args.out:
            write_json(report, args.out)
        else:
            sys.stdout.write(rendered(report).decode("utf-8"))
        return 0
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
