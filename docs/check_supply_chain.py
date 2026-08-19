#!/usr/bin/env python3
"""Fail when workflow dependencies or repository trust controls drift."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
PINNED_ACTION = re.compile(
    r"^\s*-?\s*uses:\s+[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+@[a-f0-9]{40}(?:\s+#.*)?$"
)


def fail(message: str) -> None:
    raise SystemExit(f"Supply-chain check failed: {message}")


def main() -> None:
    workflow_paths = sorted(WORKFLOWS.glob("*.yml"))
    if not workflow_paths:
        fail("no GitHub Actions workflows found")
    action_count = 0
    for path in workflow_paths:
        source = path.read_text()
        uses = [line for line in source.splitlines() if re.match(r"^\s*-?\s*uses:", line)]
        action_count += len(uses)
        for line in uses:
            if not PINNED_ACTION.fullmatch(line):
                fail(f"{path.relative_to(ROOT)} has a mutable or malformed Action ref: {line.strip()}")
        if "permissions:" not in source:
            fail(f"{path.relative_to(ROOT)} does not declare permissions")
        checkouts = source.count("uses: actions/checkout@")
        if source.count("persist-credentials: false") != checkouts:
            fail(f"{path.relative_to(ROOT)} must disable persisted credentials on every checkout")

    required = {
        ROOT / ".github" / "dependabot.yml": ("package-ecosystem: github-actions",),
        WORKFLOWS / "security.yml": (
            "github/codeql-action/init@",
            "actions/dependency-review-action@",
            "ossf/scorecard-action@",
        ),
        WORKFLOWS / "federal-pilot-release.yml": (
            "actions/attest-build-provenance@",
            "actions/attest-sbom@",
            "SHA256SUMS",
            "build_release.py",
        ),
        ROOT / "federal-pilot-kit" / "THREAT_MODEL.md": ("## Security invariants",),
        ROOT / "federal-pilot-kit" / "RELEASE_VERIFICATION.md": ("gh attestation verify",),
        ROOT / "federal-pilot-kit" / "pilot-launch" / "README.md": ("30-Day",),
    }
    for path, tokens in required.items():
        if not path.is_file():
            fail(f"missing {path.relative_to(ROOT)}")
        source = path.read_text()
        for token in tokens:
            if token not in source:
                fail(f"{path.relative_to(ROOT)} is missing {token!r}")

    print(
        f"Supply-chain controls verified: {len(workflow_paths)} workflows, "
        f"{action_count} immutable Action references, release provenance, SBOM, and threat model"
    )


if __name__ == "__main__":
    main()
