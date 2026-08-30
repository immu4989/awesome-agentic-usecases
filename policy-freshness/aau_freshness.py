"""Human-reviewed source freshness monitoring for AAU policy-dependent artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


REGISTRY_VERSION = "aau-policy-source-registry/1.0"
REPORT_VERSION = "aau-policy-freshness-report/1.0"
MAX_REGISTRY_BYTES = 2_000_000
MAX_SOURCE_BYTES = 12_000_000
MAX_SOURCES = 250
HEX = set("0123456789abcdef")
STATUS_ORDER = {"source_changed": 0, "unreachable": 1, "review_due": 2, "current": 3}
BOUNDARY_KEYS = {
    "metadata_and_bytes_only",
    "no_automatic_policy_interpretation",
    "no_automatic_lab_update",
    "human_domain_review_required",
    "not_legal_or_compliance_monitoring",
}


class _VisibleText(HTMLParser):
    """Extract stable visible text while ignoring volatile page machinery."""

    SKIP = {"script", "style", "noscript", "svg", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.SKIP:
            self.depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.depth:
            self.parts.append(data)


def _fingerprint(payload: bytes, mode: str) -> str:
    if mode == "raw":
        return digest(payload)
    if mode != "visible_text_v1":
        raise FreshnessError(f"unsupported fingerprint mode: {mode}")
    parser = _VisibleText()
    try:
        parser.feed(payload.decode("utf-8", errors="replace"))
    except Exception as exc:  # HTMLParser can reject pathologically malformed documents.
        raise FreshnessError("unable to normalize source HTML") from exc
    normalized = " ".join(" ".join(parser.parts).split()).encode()
    if not normalized:
        raise FreshnessError("normalized source HTML contains no visible text")
    return digest(normalized)


class FreshnessError(ValueError):
    """Raised when a source registry or report violates the public contract."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def rendered(value: Any) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode()


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(payload).hexdigest()


def _text(value: Any, label: str, limit: int = 600) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise FreshnessError(f"{label} must be non-empty text of at most {limit} characters")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise FreshnessError(f"{label} fields differ from the 1.0 contract")
    return value


def _date(value: Any, label: str) -> str:
    value = _text(value, label, 10)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise FreshnessError(f"{label} must use YYYY-MM-DD") from exc
    return value


def _timestamp(value: Any, label: str) -> str:
    value = _text(value, label, 40)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FreshnessError(f"{label} must use ISO-8601") from exc
    if parsed.tzinfo is None:
        raise FreshnessError(f"{label} must include a timezone")
    return value


def _sha_or_none(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) != 64 or any(char not in HEX for char in value):
        raise FreshnessError(f"{label} must be null or a lowercase SHA-256 digest")
    return value


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REGISTRY_BYTES:
        raise FreshnessError(f"invalid, oversized, or symbolic-link file: {path}")
    try:
        value = json.loads(path.read_text())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FreshnessError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FreshnessError(f"expected one JSON object in {path}")
    return value


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise FreshnessError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(rendered(value))


def validate_registry(registry: dict[str, Any], root: Path | None = None) -> None:
    _exact(
        registry,
        {"registry_version", "registry_id", "baseline_captured_at", "sources", "boundary"},
        "source registry",
    )
    if registry["registry_version"] != REGISTRY_VERSION:
        raise FreshnessError(f"registry_version must be {REGISTRY_VERSION}")
    _text(registry["registry_id"], "registry_id", 120)
    if registry["baseline_captured_at"] is not None:
        _timestamp(registry["baseline_captured_at"], "baseline_captured_at")
    sources = registry["sources"]
    if not isinstance(sources, list) or not 1 <= len(sources) <= MAX_SOURCES:
        raise FreshnessError(f"sources must contain 1 to {MAX_SOURCES} entries")
    ids: set[str] = set()
    for index, source in enumerate(sources):
        source = _exact(
            source,
            {
                "source_id",
                "title",
                "authority",
                "url",
                "allowed_hosts",
                "fingerprint_mode",
                "owner_paths",
                "verified_on",
                "review_due",
                "baseline",
            },
            f"sources[{index}]",
        )
        source_id = _text(source["source_id"], "source_id", 120)
        if source_id in ids:
            raise FreshnessError(f"duplicate source_id: {source_id}")
        ids.add(source_id)
        _text(source["title"], "source title", 300)
        _text(source["authority"], "source authority", 200)
        url = _text(source["url"], "source URL", 800)
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise FreshnessError("source URLs must use HTTPS and include a host")
        hosts = source["allowed_hosts"]
        if not isinstance(hosts, list) or not hosts or len(hosts) != len(set(hosts)):
            raise FreshnessError("allowed_hosts must be a unique non-empty list")
        for host in hosts:
            _text(host, "allowed host", 200)
        if parsed.hostname not in hosts:
            raise FreshnessError("source URL host must appear in allowed_hosts")
        if source["fingerprint_mode"] not in {"raw", "visible_text_v1"}:
            raise FreshnessError("fingerprint_mode must be raw or visible_text_v1")
        owner_paths = source["owner_paths"]
        if not isinstance(owner_paths, list) or not owner_paths or len(owner_paths) != len(set(owner_paths)):
            raise FreshnessError("owner_paths must be a unique non-empty list")
        for owner in owner_paths:
            owner = _text(owner, "owner path", 300)
            pure = Path(owner)
            if pure.is_absolute() or ".." in pure.parts:
                raise FreshnessError("owner paths must be repository relative")
            if root is not None and not (root / pure).exists():
                raise FreshnessError(f"owner path does not exist: {owner}")
        _date(source["verified_on"], "verified_on")
        _date(source["review_due"], "review_due")
        baseline = _exact(
            source["baseline"],
            {"content_sha256", "bytes", "etag", "last_modified", "final_url", "content_type"},
            "source baseline",
        )
        fingerprint = _sha_or_none(baseline["content_sha256"], "baseline content_sha256")
        if fingerprint is None:
            if any(baseline[key] is not None for key in baseline if key != "content_sha256"):
                raise FreshnessError("an uncaptured baseline must contain only null values")
        else:
            if not isinstance(baseline["bytes"], int) or not 0 <= baseline["bytes"] <= MAX_SOURCE_BYTES:
                raise FreshnessError("baseline bytes are invalid")
            for key in ("etag", "last_modified", "content_type"):
                if baseline[key] is not None and not isinstance(baseline[key], str):
                    raise FreshnessError(f"baseline {key} must be text or null")
            final_url = _text(baseline["final_url"], "baseline final_url", 800)
            final_host = urllib.parse.urlparse(final_url).hostname
            if not final_url.startswith("https://") or final_host not in hosts:
                raise FreshnessError("baseline final_url must remain on an allowed HTTPS host")
    boundary = _exact(registry["boundary"], BOUNDARY_KEYS, "registry boundary")
    if any(boundary[key] is not True for key in BOUNDARY_KEYS):
        raise FreshnessError("all source registry boundaries must be true")


def _fetch(source: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        source["url"],
        headers={
            "User-Agent": "AAU-Policy-Freshness/1.0 (+https://github.com/immu4989/awesome-agentic-usecases)",
            "Accept": "text/html,application/pdf,text/plain,application/json;q=0.9,*/*;q=0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final_url = response.geturl()
        parsed = urllib.parse.urlparse(final_url)
        if parsed.scheme != "https" or parsed.hostname not in source["allowed_hosts"]:
            raise FreshnessError(f"source redirected outside allowed hosts: {source['source_id']}")
        payload = response.read(MAX_SOURCE_BYTES + 1)
        if len(payload) > MAX_SOURCE_BYTES:
            raise FreshnessError(f"source exceeds {MAX_SOURCE_BYTES} bytes: {source['source_id']}")
        return {
            "content_sha256": _fingerprint(payload, source["fingerprint_mode"]),
            "bytes": len(payload),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "final_url": final_url,
            "content_type": response.headers.get("Content-Type"),
        }


def refresh_registry(registry: dict[str, Any], root: Path, timeout: float, today: date) -> dict[str, Any]:
    validate_registry(registry, root)
    refreshed = json.loads(json.dumps(registry))
    for source in refreshed["sources"]:
        source["baseline"] = _fetch(source, timeout)
        source["verified_on"] = today.isoformat()
    refreshed["baseline_captured_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    validate_registry(refreshed, root)
    return refreshed


def _error_code(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP_{exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return "URL_ERROR"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "TIMEOUT"
    if isinstance(exc, FreshnessError):
        return "BOUNDARY_ERROR"
    return "FETCH_ERROR"


def scan_registry(registry: dict[str, Any], root: Path, timeout: float, as_of: date) -> dict[str, Any]:
    validate_registry(registry, root)
    rows = []
    for source in registry["sources"]:
        baseline = source["baseline"]
        observed = None
        error = None
        try:
            observed = _fetch(source, timeout)
        except (FreshnessError, urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            error = _error_code(exc)
        if error:
            status = "unreachable"
        elif baseline["content_sha256"] is None:
            status = "source_changed"
            error = "BASELINE_MISSING"
        elif observed["content_sha256"] != baseline["content_sha256"]:
            status = "source_changed"
        elif as_of > date.fromisoformat(source["review_due"]):
            status = "review_due"
        else:
            status = "current"
        rows.append(
            {
                "source_id": source["source_id"],
                "title": source["title"],
                "authority": source["authority"],
                "url": source["url"],
                "owner_paths": source["owner_paths"],
                "verified_on": source["verified_on"],
                "review_due": source["review_due"],
                "status": status,
                "error_code": error,
                "baseline": baseline,
                "observed": observed,
                "interpretation": "human_review_required" if status != "current" else "none",
            }
        )
    counts = {status: sum(row["status"] == status for row in rows) for status in STATUS_ORDER}
    report = {
        "report_version": REPORT_VERSION,
        "registry_id": registry["registry_id"],
        "registry_sha256": digest(registry),
        "as_of": as_of.isoformat(),
        "summary": {
            "source_count": len(rows),
            **{f"{status}_count": count for status, count in counts.items()},
            "human_review_required_count": len(rows) - counts["current"],
        },
        "sources": sorted(rows, key=lambda item: (STATUS_ORDER[item["status"]], item["source_id"])),
        "boundary": {
            "bytes_and_metadata_not_policy_meaning": True,
            "changed_does_not_mean_rule_changed": True,
            "unchanged_does_not_prove_current_law_or_guidance": True,
            "no_automatic_source_or_lab_update": True,
            "human_domain_review_required": True,
            "not_legal_compliance_or_regulatory_monitoring": True,
        },
        "report_sha256": "",
    }
    report["report_sha256"] = digest({key: value for key, value in report.items() if key != "report_sha256"})
    return report


def offline_report(registry: dict[str, Any], root: Path, as_of: date) -> dict[str, Any]:
    """Create a deterministic due-date report without making network requests."""

    validate_registry(registry, root)
    rows = []
    for source in registry["sources"]:
        status = "review_due" if as_of > date.fromisoformat(source["review_due"]) else "current"
        rows.append(
            {
                "source_id": source["source_id"],
                "title": source["title"],
                "authority": source["authority"],
                "owner_paths": source["owner_paths"],
                "review_due": source["review_due"],
                "baseline_present": source["baseline"]["content_sha256"] is not None,
                "status": status,
            }
        )
    return {
        "offline_report_version": "aau-policy-freshness-offline/1.0",
        "registry_id": registry["registry_id"],
        "registry_sha256": digest(registry),
        "as_of": as_of.isoformat(),
        "source_count": len(rows),
        "review_due_count": sum(row["status"] == "review_due" for row in rows),
        "baseline_missing_count": sum(not row["baseline_present"] for row in rows),
        "sources": rows,
        "boundary": "Offline validation checks structure, owner paths, baseline presence, and dates; it does not contact or interpret a source.",
    }


def issue_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "## Policy source freshness review",
        "",
        f"Automated byte/metadata scan `{report['report_sha256']}` found **{summary['human_review_required_count']}** source(s) requiring human review.",
        "",
        "| Status | Source | Authority | Affected repository paths |",
        "|---|---|---|---|",
    ]
    for source in report["sources"]:
        if source["status"] == "current":
            continue
        owners = "<br>".join(f"`{path}`" for path in source["owner_paths"])
        lines.append(
            f"| `{source['status']}` | [{source['title']}]({source['url']}) | {source['authority']} | {owners} |"
        )
    lines.extend(
        [
            "",
            "A changed byte stream does not prove that policy meaning changed, and an unchanged byte stream does not prove legal currency or applicability. A qualified owner must review the official source, record the conclusion, update affected artifacts if necessary, then explicitly capture a new baseline.",
            "",
            "This workflow is not legal, regulatory, or compliance monitoring.",
        ]
    )
    return "\n".join(lines) + "\n"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Monitor official-source freshness without interpreting policy")
    sub = root.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("registry", type=Path)
    validate.add_argument("--root", type=Path, default=Path.cwd())
    offline = sub.add_parser("offline")
    offline.add_argument("registry", type=Path)
    offline.add_argument("--root", type=Path, default=Path.cwd())
    offline.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    offline.add_argument("--out", type=Path)
    refresh = sub.add_parser("refresh")
    refresh.add_argument("registry", type=Path)
    refresh.add_argument("--root", type=Path, default=Path.cwd())
    refresh.add_argument("--timeout", type=float, default=25.0)
    refresh.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    refresh.add_argument("--out", type=Path, required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("registry", type=Path)
    scan.add_argument("--root", type=Path, default=Path.cwd())
    scan.add_argument("--timeout", type=float, default=25.0)
    scan.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    scan.add_argument("--out", type=Path, required=True)
    body = sub.add_parser("issue-body")
    body.add_argument("report", type=Path)
    body.add_argument("--out", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "issue-body":
            report = load_json(args.report)
            if args.out.exists() or args.out.is_symlink():
                raise FreshnessError(f"refusing to overwrite: {args.out}")
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(issue_markdown(report))
            print(f"OK: review issue body written to {args.out}.")
            return 0
        registry = load_json(args.registry)
        if args.command == "validate":
            validate_registry(registry, args.root)
            print(f"OK: {len(registry['sources'])} source records and owner paths verified.")
        elif args.command == "offline":
            report = offline_report(registry, args.root, args.as_of)
            if args.out:
                write_json(report, args.out)
            else:
                print(json.dumps(report, indent=2))
        elif args.command == "refresh":
            refreshed = refresh_registry(registry, args.root, args.timeout, args.as_of)
            write_json(refreshed, args.out)
            print(f"OK: captured {len(refreshed['sources'])} explicit source baselines in {args.out}.")
        else:
            report = scan_registry(registry, args.root, args.timeout, args.as_of)
            write_json(report, args.out)
            print(
                f"OK: scanned {report['summary']['source_count']} sources; "
                f"{report['summary']['human_review_required_count']} require human review."
            )
        return 0
    except (FreshnessError, urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        print(f"aau policy freshness: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
