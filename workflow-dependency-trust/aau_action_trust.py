#!/usr/bin/env python3
"""Lock and verify the repository origin of every pinned GitHub Action commit."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
DEFAULT_LOCK = HERE / "action-trust-lock.json"
LOCK_VERSION = "aau-github-action-trust-lock/1.0"
MAX_BYTES = 1_000_000
SHA = re.compile(r"[0-9a-f]{40}")
USES = re.compile(
    r"^\s*-?\s*uses:\s*"
    r"(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"
    r"(?P<component>(?:/[A-Za-z0-9_.-]+)*)@(?P<revision>[^\s#]+)"
)
BOUNDARIES = {
    "full_commit_sha_required",
    "repository_membership_verified",
    "tag_objects_rejected",
    "commit_signature_observed_not_required",
    "live_reverification_required",
    "not_an_action_code_audit",
    "not_upstream_availability_or_safety_proof",
}


class ActionTrustError(ValueError):
    """Raised when an Action dependency or trust lock fails closed."""


def digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def workflow_files() -> list[Path]:
    paths: set[Path] = set()
    for base in (ROOT / ".github" / "workflows", ROOT / ".github" / "actions"):
        if base.is_dir():
            paths.update(base.rglob("*.yml"))
            paths.update(base.rglob("*.yaml"))
    return sorted(paths)


def read_workflow(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ActionTrustError(f"workflow must be a bounded regular file: {path}")
    return path.read_text()


def scan_dependencies() -> list[dict]:
    found: dict[tuple[str, str], set[str]] = {}
    for path in workflow_files():
        relative = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(read_workflow(path).splitlines(), start=1):
            if not re.match(r"^\s*-?\s*uses:", line):
                continue
            value = line.split("uses:", 1)[1].strip()
            if value.startswith("./"):
                continue
            match = USES.match(line)
            if match is None or SHA.fullmatch(match["revision"]) is None:
                raise ActionTrustError(
                    f"external Action must use a full lowercase commit SHA: {relative}:{number}"
                )
            coordinate = match["repository"] + match["component"]
            key = (match["repository"].lower(), match["revision"])
            found.setdefault(key, set()).add(f"{relative}:{number}:{coordinate}")
    return [
        {
            "repository": repository,
            "commit_sha": commit,
            "uses": sorted(uses),
        }
        for (repository, commit), uses in sorted(found.items())
    ]


def load_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ActionTrustError(f"lock must be a bounded regular file: {path}")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ActionTrustError("lock must contain one JSON object")
    return value


def validate_lock(lock: dict) -> list[dict]:
    if set(lock) != {
        "lock_version", "verified_at", "github_api", "dependencies", "summary",
        "boundary", "lock_sha256",
    } or lock["lock_version"] != LOCK_VERSION:
        raise ActionTrustError("action trust lock fields or version differ from the 1.0 contract")
    try:
        verified = datetime.fromisoformat(lock["verified_at"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ActionTrustError("verified_at must be an ISO 8601 timestamp") from exc
    if verified.tzinfo is None or verified.utcoffset() != timezone.utc.utcoffset(verified):
        raise ActionTrustError("verified_at must identify UTC")
    if lock["github_api"] != "https://api.github.com":
        raise ActionTrustError("the lock may use only GitHub's HTTPS API")
    boundary = lock["boundary"]
    if (
        not isinstance(boundary, dict)
        or set(boundary) != BOUNDARIES
        or any(boundary[key] is not True for key in BOUNDARIES)
    ):
        raise ActionTrustError("every action trust boundary must be explicit and true")
    dependencies = lock["dependencies"]
    if not isinstance(dependencies, list) or not dependencies or len(dependencies) > 100:
        raise ActionTrustError("dependencies must be a non-empty bounded list")
    seen: set[tuple[str, str]] = set()
    signed_count = 0
    for item in dependencies:
        if not isinstance(item, dict) or set(item) != {
            "repository", "commit_sha", "uses", "repository_membership",
            "commit_verification", "commit_url",
        }:
            raise ActionTrustError("dependency fields differ from the 1.0 contract")
        repository = item["repository"]
        commit = item["commit_sha"]
        if (
            not isinstance(repository, str)
            or re.fullmatch(r"[a-z0-9_.-]+/[a-z0-9_.-]+", repository) is None
            or not isinstance(commit, str)
            or SHA.fullmatch(commit) is None
        ):
            raise ActionTrustError("dependency repository or commit is invalid")
        key = (repository, commit)
        if key in seen:
            raise ActionTrustError("dependency repository and commit pairs must be unique")
        seen.add(key)
        if item["repository_membership"] != "verified_by_github_commit_api":
            raise ActionTrustError("dependency repository membership is not verified")
        verification = item["commit_verification"]
        if (
            not isinstance(verification, dict)
            or set(verification) != {"verified", "reason"}
            or not isinstance(verification["verified"], bool)
            or not isinstance(verification["reason"], str)
            or not verification["reason"]
        ):
            raise ActionTrustError("commit signature observation is invalid")
        signed_count += int(verification["verified"])
        if item["commit_url"] != f"https://github.com/{repository}/commit/{commit}":
            raise ActionTrustError("dependency commit URL does not match its repository and SHA")
        uses = item["uses"]
        if not isinstance(uses, list) or not uses or uses != sorted(set(uses)):
            raise ActionTrustError("dependency uses must be a sorted, non-empty unique list")

    scanned = scan_dependencies()
    expected = [
        (item["repository"], item["commit_sha"], item["uses"])
        for item in scanned
    ]
    actual = [
        (item["repository"], item["commit_sha"], item["uses"])
        for item in dependencies
    ]
    if actual != expected:
        raise ActionTrustError("workflow Action references differ from the reviewed trust lock")
    if lock["summary"] != {
        "dependency_count": len(dependencies),
        "workflow_use_count": sum(len(item["uses"]) for item in dependencies),
        "signature_verified_count": signed_count,
        "repository_membership_failure_count": 0,
    }:
        raise ActionTrustError("action trust summary does not recompute")
    unsigned = {key: value for key, value in lock.items() if key != "lock_sha256"}
    if lock["lock_sha256"] != digest(unsigned):
        raise ActionTrustError("action trust lock digest does not recompute")
    return dependencies


def github_commit(repository: str, commit: str, token: str = "") -> dict:
    request = Request(
        f"https://api.github.com/repos/{repository}/commits/{commit}",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AAU-Action-Trust-Lock/1.0",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed GitHub HTTPS origin
            value = json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ActionTrustError(
            f"GitHub did not confirm {commit} as a commit in {repository}: {exc}"
        ) from exc
    if not isinstance(value, dict) or value.get("sha") != commit:
        raise ActionTrustError(f"GitHub returned the wrong commit for {repository}@{commit}")
    verification = value.get("commit", {}).get("verification", {})
    return {
        "repository_membership": "verified_by_github_commit_api",
        "commit_verification": {
            "verified": verification.get("verified") is True,
            "reason": str(verification.get("reason") or "not_reported"),
        },
        "commit_url": f"https://github.com/{repository}/commit/{commit}",
    }


def verify_online(
    dependencies: list[dict],
    token: str,
    fetcher: Callable[[str, str, str], dict] = github_commit,
) -> None:
    for item in dependencies:
        observed = fetcher(item["repository"], item["commit_sha"], token)
        for key in ("repository_membership", "commit_url"):
            if observed[key] != item[key]:
                raise ActionTrustError(
                    f"live repository membership drifted for {item['repository']}"
                )


def build_lock(as_of: str, token: str) -> dict:
    try:
        observed_at = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ActionTrustError("--as-of must be an ISO 8601 timestamp") from exc
    if observed_at.tzinfo is None or observed_at.utcoffset() != timezone.utc.utcoffset(observed_at):
        raise ActionTrustError("--as-of must identify UTC")
    dependencies = []
    for dependency in scan_dependencies():
        dependencies.append({
            **dependency,
            **github_commit(dependency["repository"], dependency["commit_sha"], token),
        })
    signed = sum(item["commit_verification"]["verified"] for item in dependencies)
    lock = {
        "lock_version": LOCK_VERSION,
        "verified_at": as_of,
        "github_api": "https://api.github.com",
        "dependencies": dependencies,
        "summary": {
            "dependency_count": len(dependencies),
            "workflow_use_count": sum(len(item["uses"]) for item in dependencies),
            "signature_verified_count": signed,
            "repository_membership_failure_count": 0,
        },
        "boundary": {key: True for key in sorted(BOUNDARIES)},
        "lock_sha256": "",
    }
    lock["lock_sha256"] = digest(
        {key: value for key, value in lock.items() if key != "lock_sha256"}
    )
    return lock


def write_new(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise ActionTrustError(f"refusing to overwrite action trust lock: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="aau-action-trust",
        description="Verify immutable GitHub Action pins belong to their named repositories.",
    )
    sub = root.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    verify.add_argument("--online", action="store_true")
    verify.add_argument("--token-env", default="GITHUB_TOKEN")
    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("--as-of", required=True)
    snapshot.add_argument("--out", type=Path, required=True)
    snapshot.add_argument("--token-env", default="GITHUB_TOKEN")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        token = os.environ.get(args.token_env, "")
        if args.command == "snapshot":
            lock = build_lock(args.as_of, token)
            write_new(args.out, lock)
            print(
                f"OK: locked {lock['summary']['dependency_count']} Action commits "
                f"across {lock['summary']['workflow_use_count']} workflow uses."
            )
        else:
            lock = load_json(args.lock)
            dependencies = validate_lock(lock)
            if args.online:
                verify_online(dependencies, token)
            mode = "offline + live origin" if args.online else "offline"
            print(
                f"OK: {len(dependencies)} Action commits and "
                f"{lock['summary']['workflow_use_count']} workflow uses passed {mode} trust checks."
            )
        return 0
    except (ActionTrustError, json.JSONDecodeError) as exc:
        print(f"aau-action-trust: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
