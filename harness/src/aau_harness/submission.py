"""Build privacy-bounded community evidence bundles from Agent Evidence Starters.

The command never uploads a bundle or opens a pull request. It validates a local
starter and public aggregate receipts, derives an evidence level from declared
artifacts, and writes a deterministic, inspectable contribution directory.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from .evaluate import RECEIPT_VERSION, load_suite
from .starter import (
    PACKAGE_VERSION,
    STARTER_VERSION,
    doctor_project,
    safe_regular_file,
    validated_fingerprints,
)


SUBMISSION_VERSION = "aau-community-evidence/1.0"
MANIFEST_VERSION = "aau-community-evidence-manifest/1.0"
CHECKS_VERSION = "aau-community-evidence-checks/1.0"
PRIVACY_VERSION = "aau-community-evidence-privacy/1.0"
LEVELS = ("Generated", "Domain reviewed", "Reproduced", "Verified")
LEVEL_RANK = {level: index for index, level in enumerate(LEVELS)}
MAX_PACK_FILE_BYTES = 2_000_000
MAX_RECEIPTS = 12
SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
GITHUB_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SAFE_ADAPTER_KINDS = {"command", "endpoint"}
RECEIPT_TOP_LEVEL = {
    "receipt_version",
    "suite_id",
    "suite_sha256",
    "adapter_kind",
    "scenario_count",
    "metrics",
    "results",
    "privacy",
    "boundary",
}
STARTER_MANIFEST_FIELDS = {
    "starter_version",
    "name",
    "title",
    "template_id",
    "primary_adapter",
    "package_version",
    "status",
    "human_authority",
    "generated_file_sha256",
    "boundary",
}
SENSITIVE_PATTERNS = (
    ("email_address", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("us_social_security_number", re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b")),
    ("payment_card_like_number", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    (
        "credential_or_private_key",
        re.compile(
            r"(?:api[_ -]?key|access[_ -]?token|client[_ -]?secret|password)\s*[:=]|"
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
            re.I,
        ),
    ),
    (
        "classified_or_controlled_marker",
        re.compile(r"\b(?:TOP SECRET|SECRET//|CUI//|SOURCE SELECTION INFORMATION)\b", re.I),
    ),
)


class SubmissionError(ValueError):
    """Raised when a bundle cannot support a safe, truthful public claim."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode())


def render_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def suite_sha256(suite: dict[str, Any]) -> str:
    canonical = json.dumps(suite, sort_keys=True, separators=(",", ":")) + "\n"
    return sha256_text(canonical)


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise SubmissionError(f"{label} must be a regular file")
        if path.stat().st_size > MAX_PACK_FILE_BYTES:
            raise SubmissionError(f"{label} exceeds the 2 MB limit")
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SubmissionError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise SubmissionError(f"{label} must contain a JSON object")
    return value


def _nonempty(value: Any, *, maximum: int = 500) -> bool:
    return isinstance(value, str) and 0 < len(value.strip()) <= maximum


def normalize_github(value: str) -> str:
    handle = value.strip().lstrip("@")
    if not GITHUB_PATTERN.fullmatch(handle):
        raise SubmissionError("GitHub handle is invalid")
    return handle


def normalize_tags(values: list[str]) -> list[str]:
    tags = []
    for value in values:
        for item in value.split(","):
            normalized = item.strip().lower()
            if normalized and normalized not in tags:
                tags.append(normalized)
    if not 2 <= len(tags) <= 6 or any(len(tag) > 40 for tag in tags):
        raise SubmissionError("provide two to six unique tags of at most 40 characters")
    return tags


def sensitive_findings(values: dict[str, str]) -> list[dict[str, str]]:
    findings = []
    for field, value in values.items():
        for finding_id, pattern in SENSITIVE_PATTERNS:
            if pattern.search(value):
                findings.append(
                    {
                        "finding": finding_id,
                        "field": field,
                        "value_fingerprint": sha256_text(value)[:16],
                    }
                )
    return findings


def validate_receipt(receipt: dict[str, Any], suite: dict[str, Any], label: str) -> None:
    unexpected = set(receipt) - RECEIPT_TOP_LEVEL
    if unexpected:
        raise SubmissionError(f"{label} has unsupported public fields: {', '.join(sorted(unexpected))}")
    if receipt.get("receipt_version") != RECEIPT_VERSION:
        raise SubmissionError(f"{label} must use {RECEIPT_VERSION}")
    expected_hash = suite_sha256(suite)
    if receipt.get("suite_id") != suite["suite_id"] or receipt.get("suite_sha256") != expected_hash:
        raise SubmissionError(f"{label} does not match suite.json")
    if receipt.get("adapter_kind") not in SAFE_ADAPTER_KINDS:
        raise SubmissionError(f"{label} must measure a command or endpoint adapter, not a mock")
    if receipt.get("scenario_count") != len(suite["cases"]):
        raise SubmissionError(f"{label}.scenario_count does not match suite.json")

    metrics = receipt.get("metrics")
    required_metrics = {
        "submitted_rate",
        "outcome_exact_rate",
        "no_forbidden_attempt_rate",
        "no_forbidden_execute_rate",
        "exact_rate",
        "mean_latency_s",
    }
    if not isinstance(metrics, dict) or set(metrics) != required_metrics:
        raise SubmissionError(f"{label}.metrics must contain the exact public metric set")
    for name in required_metrics - {"mean_latency_s"}:
        if type(metrics[name]) not in (int, float) or not math.isfinite(metrics[name]) or not 0 <= metrics[name] <= 1:
            raise SubmissionError(f"{label}.metrics.{name} must be between zero and one")
    if (
        type(metrics["mean_latency_s"]) not in (int, float)
        or not math.isfinite(metrics["mean_latency_s"])
        or metrics["mean_latency_s"] < 0
    ):
        raise SubmissionError(f"{label}.metrics.mean_latency_s must be non-negative")

    privacy = receipt.get("privacy")
    required_privacy = {
        "suite_sharing_attested": True,
        "scenario_inputs_included": False,
        "expected_answers_included": False,
        "adapter_responses_included": False,
        "reasoning_included": False,
        "credentials_included": False,
    }
    if privacy != required_privacy:
        raise SubmissionError(f"{label} is not a privacy-bounded public receipt")
    results = receipt.get("results")
    if not isinstance(results, list) or len(results) != len(suite["cases"]):
        raise SubmissionError(f"{label}.results must contain one aggregate row per scenario")
    scenario_ids = [case["scenario_id"] for case in suite["cases"]]
    if [row.get("scenario_id") for row in results if isinstance(row, dict)] != scenario_ids:
        raise SubmissionError(f"{label}.results scenario order or identifiers drifted")
    allowed_result = {
        "scenario_id",
        "submitted",
        "outcome_exact",
        "no_forbidden_attempt",
        "no_forbidden_execute",
        "exact",
        "failure_codes",
        "latency_s",
    }
    if any(not isinstance(row, dict) or set(row) != allowed_result for row in results):
        raise SubmissionError(f"{label}.results contains private or unsupported fields")
    for row in results:
        for field in (
            "submitted",
            "outcome_exact",
            "no_forbidden_attempt",
            "no_forbidden_execute",
            "exact",
        ):
            if type(row[field]) is not bool:
                raise SubmissionError(f"{label}.results.{field} must be boolean")
        if not isinstance(row["failure_codes"], list) or not all(
            isinstance(code, str) for code in row["failure_codes"]
        ):
            raise SubmissionError(f"{label}.results.failure_codes must be a string list")
        if (
            type(row["latency_s"]) not in (int, float)
            or not math.isfinite(row["latency_s"])
            or row["latency_s"] < 0
        ):
            raise SubmissionError(f"{label}.results.latency_s must be non-negative")
        expected_exact = (
            row["outcome_exact"]
            and row["no_forbidden_attempt"]
            and row["no_forbidden_execute"]
        )
        if row["exact"] is not expected_exact:
            raise SubmissionError(f"{label}.results.exact is inconsistent")
    metric_fields = {
        "submitted_rate": "submitted",
        "outcome_exact_rate": "outcome_exact",
        "no_forbidden_attempt_rate": "no_forbidden_attempt",
        "no_forbidden_execute_rate": "no_forbidden_execute",
        "exact_rate": "exact",
    }
    for metric, field in metric_fields.items():
        expected = round(sum(row[field] for row in results) / len(results), 6)
        if metrics[metric] != expected:
            raise SubmissionError(f"{label}.metrics.{metric} is inconsistent with results")
    expected_latency = round(sum(row["latency_s"] for row in results) / len(results), 6)
    if metrics["mean_latency_s"] != expected_latency:
        raise SubmissionError(f"{label}.metrics.mean_latency_s is inconsistent with results")
    if not _nonempty(receipt.get("boundary"), maximum=1_000):
        raise SubmissionError(f"{label}.boundary is required")
    if sensitive_findings({label: render_json(receipt)}):
        raise SubmissionError(f"{label} failed the local sensitive-data scan")


def sanitize_starter_manifest(value: dict[str, Any]) -> dict[str, Any]:
    """Return the fixed public starter contract or reject ambiguous/private fields."""
    if set(value) != STARTER_MANIFEST_FIELDS:
        raise SubmissionError("starter manifest contains private, missing, or unsupported fields")
    if value.get("starter_version") != STARTER_VERSION:
        raise SubmissionError(f"starter manifest must use {STARTER_VERSION}")
    fingerprints, problems = validated_fingerprints(value.get("generated_file_sha256"))
    if problems:
        raise SubmissionError("starter manifest fingerprints are invalid: " + "; ".join(problems))
    if value.get("primary_adapter") not in SAFE_ADAPTER_KINDS:
        raise SubmissionError("starter manifest primary_adapter must be command or endpoint")
    for field in ("name", "title", "template_id", "package_version", "status", "boundary"):
        if not _nonempty(value.get(field), maximum=1_000):
            raise SubmissionError(f"starter manifest {field} is required")
    authority = value.get("human_authority")
    if not isinstance(authority, dict) or set(authority) != {
        "accountable_role",
        "protected_action",
    }:
        raise SubmissionError("starter manifest human_authority is invalid")
    if not all(_nonempty(authority.get(field), maximum=500) for field in authority):
        raise SubmissionError("starter manifest human_authority fields are required")
    public_value = {
        **value,
        "human_authority": dict(authority),
        "generated_file_sha256": fingerprints,
    }
    findings = sensitive_findings(
        {
            "starter-manifest.json": render_json(
                {key: item for key, item in public_value.items() if key != "generated_file_sha256"}
            )
        }
    )
    if findings:
        raise SubmissionError("starter manifest failed the local sensitive-data scan")
    return public_value


def resolve_metadata(
    *,
    submission_id: str,
    contributor_name: str,
    github: str,
    summary: str,
    why_fork: str,
    beneficiaries: str,
    industry: str,
    failure_shape: str,
    tags: list[str],
    review: dict[str, Any] | None = None,
    reproduction: dict[str, Any] | None = None,
    origin: str = "community-submission",
) -> dict[str, Any]:
    if not SLUG_PATTERN.fullmatch(submission_id):
        raise SubmissionError("submission id must be a 1-63 character lowercase hyphenated slug")
    text_fields = {
        "contributor_name": contributor_name,
        "summary": summary,
        "why_fork": why_fork,
        "beneficiaries": beneficiaries,
        "industry": industry,
        "failure_shape": failure_shape,
    }
    for field, value in text_fields.items():
        if not _nonempty(value, maximum=240):
            raise SubmissionError(f"{field.replace('_', ' ')} must contain 1 to 240 characters")
    if origin not in {"community-submission", "maintainer-reference"}:
        raise SubmissionError("origin must be community-submission or maintainer-reference")
    resolved_review = review or {}
    allowed_review = {"reviewer", "reviewer_role", "scope", "reviewed_at", "sources"}
    if set(resolved_review) - allowed_review:
        raise SubmissionError("review contains unsupported fields")
    sources = resolved_review.get("sources", [])
    if not isinstance(sources, list) or len(sources) > 8:
        raise SubmissionError("review.sources must contain at most eight URLs")
    if any(not isinstance(url, str) or not url.startswith("https://") for url in sources):
        raise SubmissionError("every review source must be an https:// URL")
    resolved_reproduction = reproduction or {}
    allowed_reproduction = {"reproducer_name", "reproducer_github", "scope", "receipt_file"}
    if set(resolved_reproduction) - allowed_reproduction:
        raise SubmissionError("reproduction contains unsupported fields")
    if resolved_reproduction.get("reproducer_github"):
        resolved_reproduction["reproducer_github"] = normalize_github(
            resolved_reproduction["reproducer_github"]
        )
    metadata = {
        "schema_version": SUBMISSION_VERSION,
        "id": submission_id,
        "origin": origin,
        "contributor": {"name": contributor_name.strip(), "github": normalize_github(github)},
        "summary": summary.strip(),
        "why_fork": why_fork.strip(),
        "beneficiaries": beneficiaries.strip(),
        "industry": industry.strip(),
        "failure_shape": failure_shape.strip(),
        "tags": normalize_tags(tags),
        "review": resolved_review,
        "reproduction": resolved_reproduction,
    }
    findings = sensitive_findings(
        {
            "contributor.name": metadata["contributor"]["name"],
            "summary": metadata["summary"],
            "why_fork": metadata["why_fork"],
            "beneficiaries": metadata["beneficiaries"],
            "industry": metadata["industry"],
            "failure_shape": metadata["failure_shape"],
            "review": render_json(metadata["review"]),
            "reproduction": render_json(metadata["reproduction"]),
        }
    )
    if findings:
        labels = ", ".join(sorted({item["finding"] for item in findings}))
        raise SubmissionError(f"submission metadata failed the local sensitive-data scan: {labels}")
    return metadata


def evidence_checks(
    metadata: dict[str, Any],
    starter_manifest: dict[str, Any],
    suite: dict[str, Any],
    receipts: list[tuple[str, dict[str, Any], str]],
) -> dict[str, Any]:
    suite_text = render_json(suite)
    original_suite_hash = starter_manifest.get("generated_file_sha256", {}).get("suite.json")
    adapted = bool(original_suite_hash and original_suite_hash != sha256_text(suite_text))
    review = metadata.get("review", {})
    review_complete = all(
        _nonempty(review.get(field), maximum=500)
        for field in ("reviewer", "reviewer_role", "scope", "reviewed_at")
    )
    sources = review.get("sources", []) if isinstance(review.get("sources", []), list) else []
    receipt_hashes = {digest for _, _, digest in receipts}
    reproduction = metadata.get("reproduction", {})
    contributor = metadata["contributor"]["github"].lower()
    reproducer = str(reproduction.get("reproducer_github", "")).lower()
    reproduction_file = reproduction.get("receipt_file", "")
    reproduction_complete = (
        _nonempty(reproduction.get("reproducer_name"), maximum=240)
        and bool(reproducer)
        and reproducer != contributor
        and _nonempty(reproduction.get("scope"), maximum=500)
        and reproduction_file in {name for name, _, _ in receipts}
    )

    checks = [
        {
            "id": "starter-contract",
            "stage": "Generated",
            "passed": starter_manifest.get("starter_version") == STARTER_VERSION,
            "detail": f"starter contract {starter_manifest.get('starter_version', 'missing')}",
        },
        {
            "id": "public-agent-receipt",
            "stage": "Generated",
            "passed": bool(receipts),
            "detail": f"{len(receipts)} non-mock privacy-bounded receipt(s)",
        },
        {
            "id": "protected-human-authority",
            "stage": "Generated",
            "passed": all(
                _nonempty(suite.get("human_authority", {}).get(field), maximum=500)
                for field in ("accountable_role", "protected_action")
            ),
            "detail": suite.get("human_authority", {}).get("accountable_role", "missing"),
        },
        {
            "id": "adapted-suite",
            "stage": "Domain reviewed",
            "passed": adapted,
            "detail": "suite differs from generated template" if adapted else "starter smoke suite is unchanged",
        },
        {
            "id": "scenario-depth",
            "stage": "Domain reviewed",
            "passed": len(suite["cases"]) >= 10,
            "detail": f"{len(suite['cases'])}/10 synthetic cases",
        },
        {
            "id": "named-domain-review",
            "stage": "Domain reviewed",
            "passed": review_complete,
            "detail": review.get("scope", "named review is incomplete"),
        },
        {
            "id": "source-ledger",
            "stage": "Domain reviewed",
            "passed": len(sources) >= 2,
            "detail": f"{len(sources)}/2 https source links",
        },
        {
            "id": "repeated-receipts",
            "stage": "Reproduced",
            "passed": len(receipts) >= 3 and len(receipt_hashes) >= 3,
            "detail": f"{len(receipts)} receipts · {len(receipt_hashes)} distinct hashes",
        },
        {
            "id": "named-independent-reproduction",
            "stage": "Verified",
            "passed": bool(reproduction_complete),
            "detail": (
                f"named reproduction by @{reproduction.get('reproducer_github')}"
                if reproduction_complete
                else "different named reproducer and linked receipt required"
            ),
        },
    ]
    level = "Draft"
    for candidate in LEVELS:
        required = [check for check in checks if LEVEL_RANK[check["stage"]] <= LEVEL_RANK[candidate]]
        if required and all(check["passed"] for check in required):
            level = candidate
        else:
            break
    return {
        "checks_version": CHECKS_VERSION,
        "level": level,
        "levels": list(LEVELS),
        "score": {
            "passed": sum(check["passed"] for check in checks),
            "total": len(checks),
        },
        "checks": checks,
        "boundary": (
            "Evidence levels are derived from submitted artifacts. They are not identity "
            "verification, certification, endorsement, production validation, or authority to deploy."
        ),
    }


def source_ledger(metadata: dict[str, Any]) -> str:
    review = metadata.get("review", {})
    lines = [
        "# Source and review ledger",
        "",
        "This ledger records contributor-supplied review scope. URLs and reviewer identity must be",
        "checked by maintainers and do not imply regulator or government approval.",
        "",
        f"- Reviewer: {review.get('reviewer') or 'Not yet supplied'}",
        f"- Role: {review.get('reviewer_role') or 'Not yet supplied'}",
        f"- Reviewed at: {review.get('reviewed_at') or 'Not yet supplied'}",
        f"- Scope: {review.get('scope') or 'Not yet supplied'}",
        "",
        "## Sources",
        "",
    ]
    sources = review.get("sources", [])
    lines.extend(f"- {url}" for url in sources)
    if not sources:
        lines.append("- No source URLs supplied; Domain reviewed cannot be derived.")
    return "\n".join(lines) + "\n"


def share_card(metadata: dict[str, Any], checks: dict[str, Any], suite: dict[str, Any]) -> str:
    title = html.escape(metadata["id"].replace("-", " ").title())
    industry = html.escape(metadata["industry"])
    level = html.escape(checks["level"])
    role = html.escape(suite["human_authority"]["accountable_role"])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-labelledby="title desc">
  <title id="title">{title} community evidence card</title>
  <desc id="desc">AAU community evidence level {level}, derived from public synthetic artifacts.</desc>
  <defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#07131f"/><stop offset=".62" stop-color="#10263c"/><stop offset="1" stop-color="#241b38"/></linearGradient><filter id="g"><feGaussianBlur stdDeviation="8" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
  <rect width="1200" height="630" rx="38" fill="url(#bg)"/><path d="M76 470H1125" stroke="#28445e" stroke-width="3" stroke-dasharray="8 10"/>
  <g font-family="ui-monospace,SFMono-Regular,Menlo,monospace" fill="#edf7ff">
    <text x="76" y="72" fill="#58e1ba" font-size="17" letter-spacing="4">AAU / BUILT WITH EVIDENCE</text>
    <text x="76" y="142" font-size="42" font-weight="800">{title}</text><text x="76" y="182" fill="#9fb4c9" font-size="20">{industry}</text>
    <g filter="url(#g)"><circle cx="160" cy="330" r="54" fill="#123e47" stroke="#58e1ba" stroke-width="3"/><circle cx="450" cy="330" r="54" fill="#1a3156" stroke="#73a8ff" stroke-width="3"/><circle cx="740" cy="330" r="54" fill="#3b2e1a" stroke="#ffc96b" stroke-width="3"/><circle cx="1030" cy="330" r="54" fill="#34213e" stroke="#dc90ff" stroke-width="3"/></g>
    <g text-anchor="middle" font-size="14" font-weight="800"><text x="160" y="326">CONNECT</text><text x="160" y="347">AGENT</text><text x="450" y="326">REVIEW</text><text x="450" y="347">DOMAIN</text><text x="740" y="326">REPEAT</text><text x="740" y="347">RUNS</text><text x="1030" y="326">REPRODUCE</text><text x="1030" y="347">PUBLICLY</text></g>
    <text x="76" y="505" fill="#9fb4c9" font-size="15">DERIVED EVIDENCE LEVEL</text><text x="76" y="554" fill="#ffffff" font-size="35" font-weight="800">{level}</text>
    <text x="560" y="505" fill="#ffc96b" font-size="15">PROTECTED HUMAN AUTHORITY</text><text x="560" y="545" fill="#ffffff" font-size="20" font-weight="700">{role}</text>
    <text x="76" y="597" fill="#58e1ba" font-size="14">PUBLIC RECEIPTS · SYNTHETIC SUITE · SHA-256 MANIFEST · NO PRIVATE TRACES</text>
  </g>
</svg>
'''


def contribution_readme(metadata: dict[str, Any], checks: dict[str, Any]) -> str:
    return f'''# {metadata["id"].replace("-", " ").title()}

> Built with AAU · derived evidence level: **{checks["level"]}**

{metadata["summary"]}

## Who this helps

{metadata["beneficiaries"]}

## Why fork it

{metadata["why_fork"]}

## Inspect before sharing

```bash
python -m pip install aau-harness=={PACKAGE_VERSION}
aau submit --validate .
```

The validator recomputes the manifest, privacy boundary, suite/receipt binding, and progressive
evidence checks. This directory contains aggregate public receipts and a reviewed synthetic suite;
it intentionally excludes prompts, raw responses, reasoning, credentials, headers, and private
debug traces.

**Boundary:** the evidence level is not identity verification, certification, endorsement,
production validation, legal advice, or permission to automate a protected decision.
'''


def contribution_checklist() -> str:
    return '''# Contribution checklist

- [ ] Every scenario is synthetic or public and has completed human review.
- [ ] Receipt files contain aggregate public fields only.
- [ ] The contributor, reviewer, and reproducer claims are accurate and permissioned.
- [ ] Source URLs are current, primary where possible, and match the stated scope.
- [ ] Protected human authority remains explicit.
- [ ] `aau submit --validate .` passes from the public package.
- [ ] The pull request does not claim certification, endorsement, or production approval.
'''


def build_pack_files(
    metadata: dict[str, Any],
    starter_manifest: dict[str, Any],
    suite: dict[str, Any],
    receipts: list[tuple[str, dict[str, Any], str]],
) -> dict[str, str]:
    checks = evidence_checks(metadata, starter_manifest, suite, receipts)
    metadata = {
        **metadata,
        "package_version": PACKAGE_VERSION,
        "starter_version": starter_manifest.get("starter_version"),
        "suite_id": suite["suite_id"],
        "suite_sha256": suite_sha256(suite),
        "receipt_files": [name for name, _, _ in receipts],
    }
    scan = {
        "privacy_version": PRIVACY_VERSION,
        "status": "passed_no_common_sensitive_pattern_detected",
        "findings": [],
        "scanned": ["submission metadata", "suite.json", *metadata["receipt_files"]],
        "boundary": "Pattern absence does not prove a file contains no sensitive information; authorized human review remains required.",
    }
    files = {
        "submission.json": render_json(metadata),
        "starter-manifest.json": render_json(starter_manifest),
        "suite.json": render_json(suite),
        "checks.json": render_json(checks),
        "privacy-scan.json": render_json(scan),
        "SOURCE_LEDGER.md": source_ledger(metadata),
        "README.md": contribution_readme(metadata, checks),
        "CONTRIBUTION_CHECKLIST.md": contribution_checklist(),
        "assets/evidence-card.svg": share_card(metadata, checks, suite),
    }
    for name, receipt, _ in receipts:
        files[name] = render_json(receipt)
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "submission_id": metadata["id"],
        "hash_algorithm": "sha256",
        "files": [
            {"path": name, "bytes": len(contents.encode()), "sha256": sha256_text(contents)}
            for name, contents in sorted(files.items())
        ],
        "claims": {
            "byte_integrity_only": True,
            "identity_verified": False,
            "certification_proved": False,
            "production_validation_proved": False,
            "government_endorsement_proved": False,
        },
    }
    return {**files, "manifest.json": render_json(manifest)}


def _write_atomic(target: Path, files: dict[str, str]) -> dict[str, Any]:
    destination = target.resolve()
    if destination.exists():
        raise SubmissionError(f"refusing to overwrite existing path: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{destination.name}-", dir=destination.parent) as temporary:
        stage = Path(temporary) / destination.name
        stage.mkdir()
        for name, contents in files.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        report = validate_pack(stage)
        stage.replace(destination)
    return {**report, "path": str(destination)}


def build_submission(
    starter: Path,
    receipt_paths: list[Path],
    output: Path,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    root = starter.resolve()
    report = doctor_project(root)
    if not report.ready:
        failures = "; ".join(check.message for check in report.checks if check.status == "fail")
        raise SubmissionError(f"starter doctor failed: {failures}")
    if not 1 <= len(receipt_paths) <= MAX_RECEIPTS:
        raise SubmissionError(f"provide one to {MAX_RECEIPTS} public receipt files")
    starter_manifest = sanitize_starter_manifest(
        _read_json(safe_regular_file(root, "aau-starter.json"), "starter manifest")
    )
    suite = load_suite(safe_regular_file(root, "suite.json"))
    if starter_manifest["human_authority"] != suite.get("human_authority"):
        raise SubmissionError("starter manifest and suite human authority do not match")
    scan_values = {
        "suite.description": str(suite.get("description", "")),
        "suite.cases": render_json(suite.get("cases", [])),
    }
    suite_findings = sensitive_findings(scan_values)
    if suite_findings:
        labels = ", ".join(sorted({item["finding"] for item in suite_findings}))
        raise SubmissionError(f"suite failed the local sensitive-data scan: {labels}")

    receipts = []
    for index, source in enumerate(receipt_paths, start=1):
        receipt = _read_json(source.resolve(), f"receipt {index}")
        validate_receipt(receipt, suite, f"receipt {index}")
        name = f"receipts/run-{index:02d}.json"
        receipts.append((name, receipt, sha256_text(render_json(receipt))))
    metadata = {**metadata, "reproduction": dict(metadata.get("reproduction", {}))}
    reproduction = metadata["reproduction"]
    requested_reproduction = reproduction.get("receipt_file")
    if requested_reproduction:
        if not re.fullmatch(r"run-\d{2}", requested_reproduction):
            raise SubmissionError("reproduction receipt must use a run-NN selector")
        index = int(requested_reproduction.split("-")[1])
        if not 1 <= index <= len(receipts):
            raise SubmissionError("reproduction receipt selector is outside the supplied receipts")
        reproduction["receipt_file"] = receipts[index - 1][0]
    files = build_pack_files(metadata, starter_manifest, suite, receipts)
    return _write_atomic(output, files)


def _safe_pack_file(root: Path, relative: str) -> Path:
    path = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise SubmissionError(f"unsafe pack path: {relative}")
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        raise SubmissionError(f"pack file must be regular and internal: {relative}")
    if path.stat().st_size > MAX_PACK_FILE_BYTES:
        raise SubmissionError(f"pack file exceeds 2 MB: {relative}")
    return path


def validate_pack(path: Path) -> dict[str, Any]:
    root = path.resolve()
    if not root.is_dir():
        raise SubmissionError(f"submission pack is not a directory: {root}")
    if any(item.is_symlink() for item in root.rglob("*")):
        raise SubmissionError("submission pack cannot contain symlinks")
    manifest = _read_json(_safe_pack_file(root, "manifest.json"), "manifest.json")
    if set(manifest) != {
        "manifest_version",
        "submission_id",
        "hash_algorithm",
        "files",
        "claims",
    }:
        raise SubmissionError("manifest.json contains missing or unsupported fields")
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise SubmissionError(f"manifest.json must use {MANIFEST_VERSION}")
    if manifest.get("hash_algorithm") != "sha256":
        raise SubmissionError("manifest.json hash_algorithm must be sha256")
    if manifest.get("claims") != {
        "byte_integrity_only": True,
        "identity_verified": False,
        "certification_proved": False,
        "production_validation_proved": False,
        "government_endorsement_proved": False,
    }:
        raise SubmissionError("manifest.json claims must preserve the public evidence boundary")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise SubmissionError("manifest.json.files must be a non-empty array")
    declared = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256"}:
            raise SubmissionError("manifest rows must contain exactly path, bytes, and sha256")
        name = row["path"]
        if not isinstance(name, str) or name in declared or not SHA256_PATTERN.fullmatch(str(row["sha256"])):
            raise SubmissionError("manifest contains a duplicate, unsafe, or invalid row")
        declared.add(name)
        file_path = _safe_pack_file(root, name)
        data = file_path.read_bytes()
        if len(data) != row["bytes"] or sha256_bytes(data) != row["sha256"]:
            raise SubmissionError(f"manifest mismatch: {name}")
    actual = {
        str(item.relative_to(root))
        for item in root.rglob("*")
        if item.is_file()
        and not item.is_symlink()
        and item.relative_to(root) != Path("manifest.json")
    }
    if actual != declared:
        raise SubmissionError("pack contains undeclared or missing files")

    metadata = _read_json(_safe_pack_file(root, "submission.json"), "submission.json")
    if metadata.get("schema_version") != SUBMISSION_VERSION:
        raise SubmissionError(f"submission.json must use {SUBMISSION_VERSION}")
    metadata_fields = {
        "schema_version",
        "id",
        "origin",
        "contributor",
        "summary",
        "why_fork",
        "beneficiaries",
        "industry",
        "failure_shape",
        "tags",
        "review",
        "reproduction",
        "package_version",
        "starter_version",
        "suite_id",
        "suite_sha256",
        "receipt_files",
    }
    if set(metadata) != metadata_fields:
        raise SubmissionError("submission.json contains private, missing, or unsupported fields")
    if manifest.get("submission_id") != metadata.get("id"):
        raise SubmissionError("manifest.json submission_id does not match submission.json")
    normalized = resolve_metadata(
        submission_id=metadata.get("id", ""),
        contributor_name=metadata.get("contributor", {}).get("name", ""),
        github=metadata.get("contributor", {}).get("github", ""),
        summary=metadata.get("summary", ""),
        why_fork=metadata.get("why_fork", ""),
        beneficiaries=metadata.get("beneficiaries", ""),
        industry=metadata.get("industry", ""),
        failure_shape=metadata.get("failure_shape", ""),
        tags=metadata.get("tags", []),
        review=metadata.get("review"),
        reproduction=metadata.get("reproduction"),
        origin=metadata.get("origin", ""),
    )
    for field in (
        "schema_version",
        "id",
        "origin",
        "contributor",
        "summary",
        "why_fork",
        "beneficiaries",
        "industry",
        "failure_shape",
        "tags",
        "review",
        "reproduction",
    ):
        if metadata[field] != normalized[field]:
            raise SubmissionError(f"submission.json.{field} is not normalized")
    starter_manifest = _read_json(
        _safe_pack_file(root, "starter-manifest.json"), "starter-manifest.json"
    )
    starter_manifest = sanitize_starter_manifest(starter_manifest)
    suite = load_suite(_safe_pack_file(root, "suite.json"))
    if starter_manifest["human_authority"] != suite.get("human_authority"):
        raise SubmissionError("starter manifest and suite human authority do not match")
    if metadata.get("suite_id") != suite["suite_id"] or metadata.get("suite_sha256") != suite_sha256(suite):
        raise SubmissionError("submission.json does not match suite.json")
    receipt_files = metadata.get("receipt_files")
    if (
        not isinstance(receipt_files, list)
        or not 1 <= len(receipt_files) <= MAX_RECEIPTS
        or len(receipt_files) != len(set(receipt_files))
    ):
        raise SubmissionError("submission.json receipt_files is invalid")
    expected_receipt_files = [
        f"receipts/run-{index:02d}.json" for index in range(1, len(receipt_files) + 1)
    ]
    if receipt_files != expected_receipt_files:
        raise SubmissionError("submission.json receipt_files must be sequential")
    expected_files = {
        "submission.json",
        "starter-manifest.json",
        "suite.json",
        "checks.json",
        "privacy-scan.json",
        "SOURCE_LEDGER.md",
        "README.md",
        "CONTRIBUTION_CHECKLIST.md",
        "assets/evidence-card.svg",
        *receipt_files,
    }
    if declared != expected_files:
        raise SubmissionError("manifest declares missing or unsupported contribution files")
    receipts = []
    for index, name in enumerate(receipt_files, start=1):
        if not isinstance(name, str) or not re.fullmatch(r"receipts/run-\d{2}\.json", name):
            raise SubmissionError("receipt path must use receipts/run-NN.json")
        receipt = _read_json(_safe_pack_file(root, name), name)
        validate_receipt(receipt, suite, name)
        receipts.append((name, receipt, sha256_text(render_json(receipt))))

    expected_checks = evidence_checks(metadata, starter_manifest, suite, receipts)
    checks = _read_json(_safe_pack_file(root, "checks.json"), "checks.json")
    if checks != expected_checks:
        raise SubmissionError("checks.json is stale or hand-edited")
    scan = _read_json(_safe_pack_file(root, "privacy-scan.json"), "privacy-scan.json")
    expected_scan = {
        "privacy_version": PRIVACY_VERSION,
        "status": "passed_no_common_sensitive_pattern_detected",
        "findings": [],
        "scanned": ["submission metadata", "suite.json", *receipt_files],
        "boundary": "Pattern absence does not prove a file contains no sensitive information; authorized human review remains required.",
    }
    if scan != expected_scan:
        raise SubmissionError("privacy-scan.json is missing or reports findings")
    public_text = {}
    for name in sorted(declared):
        try:
            public_text[name] = _safe_pack_file(root, name).read_text()
        except UnicodeDecodeError as exc:
            raise SubmissionError(f"pack file must be UTF-8 text: {name}") from exc
    findings = sensitive_findings(public_text)
    if findings:
        raise SubmissionError("pack content fails the current sensitive-data scan")
    card = public_text["assets/evidence-card.svg"]
    if not card.lstrip().startswith("<svg") or re.search(
        r"<script\b|javascript:|\bon(?:load|error|click)\s*=", card, re.I
    ):
        raise SubmissionError("evidence card must be a passive SVG")
    return {
        "validation_version": "aau-community-evidence-validation/1.0",
        "ready": True,
        "path": str(root),
        "submission_id": metadata["id"],
        "level": checks["level"],
        "score": checks["score"],
        "receipt_count": len(receipts),
        "file_count": len(declared) + 1,
        "boundary": checks["boundary"],
    }


def render_report(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"READY  {report['submission_id']} · {report['level']}",
            f"       {report['score']['passed']}/{report['score']['total']} evidence checks",
            f"       {report['receipt_count']} public receipt(s) · {report['file_count']} files",
            "",
            report["boundary"],
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aau submit",
        description="Build or validate a privacy-bounded community evidence contribution.",
    )
    parser.add_argument("starter", nargs="?", type=Path, help="Agent Evidence Starter directory")
    parser.add_argument("--validate", type=Path, metavar="PACK", help="validate an existing pack")
    parser.add_argument("--receipt", type=Path, action="append", default=[], help="public receipt; repeat for multiple runs")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--id")
    parser.add_argument("--contributor-name")
    parser.add_argument("--github")
    parser.add_argument("--summary")
    parser.add_argument("--why-fork")
    parser.add_argument("--beneficiaries")
    parser.add_argument("--industry")
    parser.add_argument("--failure-shape")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument(
        "--origin",
        choices=("community-submission", "maintainer-reference"),
        default="community-submission",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--reviewer")
    parser.add_argument("--reviewer-role")
    parser.add_argument("--review-scope")
    parser.add_argument("--reviewed-at")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--reproducer-name")
    parser.add_argument("--reproducer-github")
    parser.add_argument("--reproduction-scope")
    parser.add_argument("--reproduction-receipt", help="run-NN selector from supplied receipts")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.validate:
            if args.starter:
                raise SubmissionError("do not provide STARTER with --validate")
            report = validate_pack(args.validate)
        else:
            required = {
                "STARTER": args.starter,
                "--id": args.id,
                "--contributor-name": args.contributor_name,
                "--github": args.github,
                "--summary": args.summary,
                "--why-fork": args.why_fork,
                "--beneficiaries": args.beneficiaries,
                "--industry": args.industry,
                "--failure-shape": args.failure_shape,
            }
            missing = [name for name, value in required.items() if value is None]
            if missing:
                raise SubmissionError("missing build arguments: " + ", ".join(missing))
            review = {
                key: value
                for key, value in {
                    "reviewer": args.reviewer,
                    "reviewer_role": args.reviewer_role,
                    "scope": args.review_scope,
                    "reviewed_at": args.reviewed_at,
                    "sources": args.source,
                }.items()
                if value not in (None, [])
            }
            reproduction = {
                key: value
                for key, value in {
                    "reproducer_name": args.reproducer_name,
                    "reproducer_github": args.reproducer_github,
                    "scope": args.reproduction_scope,
                    "receipt_file": args.reproduction_receipt,
                }.items()
                if value is not None
            }
            metadata = resolve_metadata(
                submission_id=args.id,
                contributor_name=args.contributor_name,
                github=args.github,
                summary=args.summary,
                why_fork=args.why_fork,
                beneficiaries=args.beneficiaries,
                industry=args.industry,
                failure_shape=args.failure_shape,
                tags=args.tag,
                review=review,
                reproduction=reproduction,
                origin=args.origin,
            )
            output = args.out or Path(f"{args.id}-aau-submission")
            report = build_submission(args.starter, args.receipt, output, metadata)
        print(json.dumps(report, indent=2) if args.json else render_report(report))
        return 0
    except (OSError, SubmissionError, ValueError, json.JSONDecodeError) as exc:
        print(f"aau submit stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
