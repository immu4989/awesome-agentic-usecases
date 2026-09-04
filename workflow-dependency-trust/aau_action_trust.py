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
LOCK_VERSION = "aau-github-action-trust-lock/1.1"
MAX_BYTES = 1_000_000
SHA = re.compile(r"[0-9a-f]{40}")
USES = re.compile(
    r"^\s*-?\s*uses:\s*"
    r"(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"
    r"(?P<component>(?:/[A-Za-z0-9_.-]+)*)@(?P<revision>[^\s#]+)"
    r"(?:\s+#.*)?\s*$"
)
USES_KEY = re.compile(r"^\s*-?\s*uses\s*:")
QUOTED_USES_KEY = re.compile(r'''^\s*-?\s*["']uses["']\s*:''')
FLOW_USES_KEY = re.compile(
    r'''^\s*(?:-\s*)?(?:[A-Za-z_][A-Za-z0-9_-]*\s*:\s*)?[\[{].*["']?uses["']?\s*:'''
)
BLOCK_SCALAR = re.compile(
    r"^(?P<indent> *)(?:-\s*)?[^#:\s][^:]*:\s*[|>]"
    r"(?:[1-9][+-]?|[+-][1-9]?)?\s*(?:#.*)?$"
)
JOB_KEY = re.compile(r"(?P<job>[A-Za-z_][A-Za-z0-9_-]*):(?P<tail>.*)$")
COORDINATE = re.compile(
    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*"
)
BOUNDARIES = {
    "full_commit_sha_required",
    "repository_membership_verified",
    "tag_objects_rejected",
    "commit_signature_observed_not_required",
    "live_reverification_required",
    "stable_scope_ordinal_locator",
    "line_numbers_not_trust_identity",
    "yaml_aliases_cannot_hide_action_uses",
    "not_an_action_code_audit",
    "not_workflow_behavior_or_order_audit",
    "not_upstream_availability_or_safety_proof",
}


class ActionTrustError(ValueError):
    """Raised when an Action dependency or trust lock fails closed."""


def digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def workflow_files(root: Path = ROOT) -> list[Path]:
    paths: set[Path] = set()
    for base in (root / ".github" / "workflows", root / ".github" / "actions"):
        if base.is_dir():
            paths.update(base.rglob("*.yml"))
            paths.update(base.rglob("*.yaml"))
    return sorted(paths)


def read_workflow(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ActionTrustError(f"workflow must be a bounded regular file: {path}")
    return path.read_text()


def _structural_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Return YAML structure lines while masking literal and folded scalar bodies."""
    structural: list[tuple[int, str]] = []
    scalar_indent: int | None = None
    for number, line in enumerate(lines, start=1):
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if scalar_indent is not None:
            if not stripped or stripped.startswith("#") or indent > scalar_indent:
                continue
            scalar_indent = None
        structural.append((number, line))
        match = BLOCK_SCALAR.fullmatch(line)
        if match:
            scalar_indent = len(match["indent"])
    return structural


def _scope_map(
    path: Path,
    root: Path,
    lines: list[tuple[int, str]],
) -> dict[int, str]:
    relative = path.relative_to(root).as_posix()
    for number, line in lines:
        if QUOTED_USES_KEY.match(line) or FLOW_USES_KEY.match(line):
            raise ActionTrustError(
                f"uses must use a canonical expanded mapping: {relative}:{number}"
            )
        if (
            re.match(r"^\s*(?:-\s*)?<<\s*:", line)
            or re.match(r"^\s*-\s*\*[A-Za-z0-9_-]+\s*(?:#.*)?$", line)
            or re.match(
                r"^\s*[A-Za-z_][A-Za-z0-9_-]*\s*:\s*\*[A-Za-z0-9_-]+\s*(?:#.*)?$",
                line,
            )
        ):
            raise ActionTrustError(
                f"YAML aliases cannot define workflow trust structure: {relative}:{number}"
            )
    if relative.startswith(".github/actions/"):
        return {
            number: "composite"
            for number, line in lines
            if USES_KEY.match(line)
        }
    scopes: dict[int, str] = {}
    in_jobs = False
    current_job: str | None = None
    seen_jobs: set[str] = set()
    for number, line in lines:
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if indent == 0 and stripped and not stripped.startswith("#"):
            in_jobs = bool(re.fullmatch(r"jobs:\s*(?:#.*)?", stripped))
            current_job = None
        elif in_jobs and indent == 2:
            match = JOB_KEY.fullmatch(stripped)
            if match:
                current_job = match["job"]
                tail = match["tail"].strip()
                if tail and not tail.startswith("#"):
                    raise ActionTrustError(
                        f"workflow jobs must use an expanded mapping: {relative}:{number}"
                    )
                if current_job in seen_jobs:
                    raise ActionTrustError(
                        f"workflow job identifiers must be unique: {relative}:{number}"
                    )
                seen_jobs.add(current_job)
        if USES_KEY.match(line):
            if not in_jobs or current_job is None:
                raise ActionTrustError(
                    f"external or local uses must belong to a recognized job: {relative}:{number}"
                )
            scopes[number] = f"job:{current_job}"
    return scopes


def scan_dependencies(root: Path = ROOT) -> list[dict]:
    found: dict[tuple[str, str], set[tuple[str, str, int, str]]] = {}
    for path in workflow_files(root):
        relative = path.relative_to(root).as_posix()
        lines = read_workflow(path).splitlines()
        structural = _structural_lines(lines)
        scopes = _scope_map(path, root, structural)
        ordinals: dict[str, int] = {}
        for number, line in structural:
            if not USES_KEY.match(line):
                continue
            value = line.split("uses:", 1)[1].strip()
            if value.startswith(("./", "$/")):
                continue
            match = USES.match(line)
            if match is None or SHA.fullmatch(match["revision"]) is None:
                raise ActionTrustError(
                    f"external Action must use a full lowercase commit SHA: {relative}:{number}"
                )
            coordinate = match["repository"] + match["component"]
            key = (match["repository"].lower(), match["revision"])
            scope = scopes[number]
            ordinal = ordinals.get(scope, 0) + 1
            ordinals[scope] = ordinal
            found.setdefault(key, set()).add((relative, scope, ordinal, coordinate))
    return [
        {
            "repository": repository,
            "commit_sha": commit,
            "uses": [
                {
                    "path": path,
                    "scope": scope,
                    "ordinal": ordinal,
                    "coordinate": coordinate,
                }
                for path, scope, ordinal, coordinate in sorted(uses)
            ],
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
        raise ActionTrustError("action trust lock fields or version differ from the 1.1 contract")
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
    seen_uses: set[tuple[str, str, int]] = set()
    signed_count = 0
    for item in dependencies:
        if not isinstance(item, dict) or set(item) != {
            "repository", "commit_sha", "uses", "repository_membership",
            "commit_verification", "commit_url",
        }:
            raise ActionTrustError("dependency fields differ from the 1.1 contract")
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
        if not isinstance(uses, list) or not uses:
            raise ActionTrustError("dependency uses must be a non-empty list")
        use_keys = []
        for use in uses:
            if not isinstance(use, dict) or set(use) != {
                "path",
                "scope",
                "ordinal",
                "coordinate",
            }:
                raise ActionTrustError("dependency use locator fields are invalid")
            path, scope = use["path"], use["scope"]
            ordinal, coordinate = use["ordinal"], use["coordinate"]
            if (
                not isinstance(path, str)
                or not path.startswith(".github/")
                or Path(path).is_absolute()
                or ".." in Path(path).parts
                or not isinstance(scope, str)
                or re.fullmatch(r"(?:job:[A-Za-z_][A-Za-z0-9_-]*|composite)", scope)
                is None
                or not isinstance(ordinal, int)
                or isinstance(ordinal, bool)
                or ordinal < 1
                or not isinstance(coordinate, str)
                or COORDINATE.fullmatch(coordinate) is None
            ):
                raise ActionTrustError("dependency use locator value is invalid")
            locator = (path, scope, ordinal)
            if locator in seen_uses:
                raise ActionTrustError("dependency use locators must be globally unique")
            seen_uses.add(locator)
            use_keys.append((path, scope, ordinal, coordinate))
        if use_keys != sorted(set(use_keys)):
            raise ActionTrustError("dependency uses must be sorted and unique")

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
            "User-Agent": "AAU-Action-Trust-Lock/1.1",
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
