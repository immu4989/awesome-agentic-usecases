"""Retain official-source snapshots and compare them offline without policy interpretation."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from difflib import SequenceMatcher
import math
from pathlib import Path
import sys
import urllib.error

import aau_freshness as freshness


FILES = {"registry.json", "capture.json", "content.bin", "summary.json", "manifest.json"}
MAX_DIFF_BYTES = 200_000
MAX_DIFF_TOKENS = 5_000
BOUNDARY = ("Supplied source bytes and declared capture metadata, not authenticated retrieval, historical proof, "
            "policy interpretation, legal currency, applicability, implementation verification, approval, or compliance. "
            "Hashes are not signatures. Registry baselines and human review dates are never updated. Raw content "
            "is untrusted and unsanitized; inspect with safe tools before opening or sharing. A changed fingerprint "
            "does not prove a rule changed; unchanged text does not establish currency.")


def payloads(registry: dict, capture: dict, content: bytes) -> tuple[dict, dict[str, bytes]]:
    freshness.validate_registry(registry)
    freshness._exact(capture, {"capture_version", "source_id", "captured_at", "observed"}, "capture")
    if capture["capture_version"] != "aau-policy-source-capture/1.0":
        raise freshness.FreshnessError("unsupported source capture version")
    freshness._timestamp(capture["captured_at"], "captured_at")
    source = next((s for s in registry["sources"] if s["source_id"] == capture["source_id"]), None)
    if source is None:
        raise freshness.FreshnessError("capture source is not in the retained registry")
    if not isinstance(content, bytes) or not 1 <= len(content) <= freshness.MAX_SOURCE_BYTES:
        raise freshness.FreshnessError("source content requires 1 to 12000000 bytes")
    observed = capture["observed"]
    checked = deepcopy(registry)
    next(s for s in checked["sources"] if s["source_id"] == source["source_id"])["baseline"] = observed
    freshness.validate_registry(checked)
    fingerprint = freshness._fingerprint(content, source["fingerprint_mode"])
    if (observed["content_sha256"] != fingerprint or type(observed["bytes"]) is not int
            or observed["bytes"] != len(content)):
        raise freshness.FreshnessError("capture metadata does not match retained source bytes")
    summary = {"report_version": "aau-policy-source-snapshot/1.0", "source_id": source["source_id"],
               "source_revision": source["source_revision"], "fingerprint_mode": source["fingerprint_mode"],
               "content_sha256": fingerprint, "raw_sha256": freshness.digest(content),
               "registry_sha256": freshness.digest(registry), "capture_sha256": freshness.digest(capture),
               "registered_baseline_sha256": source["baseline"]["content_sha256"],
               "matches_registered_baseline": fingerprint == source["baseline"]["content_sha256"],
               "boundary": BOUNDARY}
    result = {"registry.json": freshness.rendered(registry), "capture.json": freshness.rendered(capture),
              "content.bin": content, "summary.json": freshness.rendered(summary)}
    if any(len(value) > freshness.MAX_REGISTRY_BYTES for name, value in result.items() if name != "content.bin"):
        raise freshness.FreshnessError("snapshot metadata exceeds 2 MB")
    result["manifest.json"] = freshness.rendered({"pack_version": "aau-policy-source-snapshot-pack/1.0",
        "files": {name: freshness.digest(value) for name, value in sorted(result.items())}})
    return summary, result


def create_snapshot(registry: dict, capture: dict, content: bytes, directory: Path) -> dict:
    if directory.exists() or directory.is_symlink():
        raise freshness.FreshnessError("refusing to overwrite a source snapshot")
    summary, files = payloads(registry, capture, content)
    directory.mkdir(parents=True, exist_ok=False)
    for name, value in files.items():
        with (directory / name).open("xb") as stream:
            stream.write(value)
    return summary


def verify_snapshot(directory: Path) -> tuple[dict, dict, bytes, dict]:
    if (directory.is_symlink() or not directory.is_dir()
            or {path.name for path in directory.iterdir()} != FILES):
        raise freshness.FreshnessError("snapshot requires exactly five files in a real directory")
    for path in directory.iterdir():
        limit = freshness.MAX_SOURCE_BYTES if path.name == "content.bin" else freshness.MAX_REGISTRY_BYTES
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise freshness.FreshnessError("snapshot members must be bounded regular non-symlink files")
    registry, capture = (freshness.load_json(directory / name) for name in ("registry.json", "capture.json"))
    with (directory / "content.bin").open("rb") as stream:
        content = stream.read(freshness.MAX_SOURCE_BYTES + 1)
    summary, expected = payloads(registry, capture, content)
    for name, value in expected.items():
        if (directory / name).read_bytes() != value:
            raise freshness.FreshnessError(f"snapshot member does not recompute: {name}")
    return registry, capture, content, summary


def compare_snapshots(before: Path, after: Path) -> dict:
    pairs = [verify_snapshot(path) for path in (before, after)]
    sources = [next(s for s in registry["sources"] if s["source_id"] == capture["source_id"])
               for registry, capture, _, _ in pairs]
    for key in ("source_id", "url", "fingerprint_mode"):
        if sources[0][key] != sources[1][key]:
            raise freshness.FreshnessError("comparison requires the same source identity, URL, and fingerprint mode")
    old, new = (pair[3] for pair in pairs)
    changed = old["content_sha256"] != new["content_sha256"]
    detail = {"status": "fingerprint_unchanged", "spans": []}
    if changed and sources[0]["fingerprint_mode"] == "raw":
        detail["status"] = "raw_content_requires_external_review"
    elif changed:
        normalized = [freshness.fingerprint_input(pair[2], "visible_text_v1") for pair in pairs]
        tokens = [value.decode("utf-8").split() for value in normalized]
        if any(len(value) > MAX_DIFF_BYTES for value in normalized) or any(len(value) > MAX_DIFF_TOKENS for value in tokens):
            detail["status"] = "text_diff_omitted_size_limit"
        else:
            detail["status"] = "bounded_lexical_diff"
            detail["spans"] = [{"operation": tag, "baseline_range": [i, j], "candidate_range": [k, m],
                                "baseline_text": " ".join(tokens[0][i:j]), "candidate_text": " ".join(tokens[1][k:m])}
                               for tag, i, j, k, m in SequenceMatcher(None, *tokens, autojunk=True).get_opcodes()
                               if tag != "equal"]
    result = {"report_version": "aau-policy-source-comparison/1.0", "source_id": sources[0]["source_id"],
              "before_snapshot_sha256": freshness.digest(old), "after_snapshot_sha256": freshness.digest(new),
              "before_captured_at": pairs[0][1]["captured_at"], "after_captured_at": pairs[1][1]["captured_at"],
              "before_revision": sources[0]["source_revision"], "after_revision": sources[1]["source_revision"],
              "raw_bytes_changed": old["raw_sha256"] != new["raw_sha256"], "fingerprint_changed": changed,
              "registered_source_metadata_changed": sources[0] != sources[1],
              "affected_owner_paths": sorted(set(sources[0]["owner_paths"]) | set(sources[1]["owner_paths"])),
              "detail": detail, "boundary": BOUNDARY + " Lexical spans use zero-based half-open word ranges; whitespace is normalized and script/style content excluded in visible_text_v1. Spans are not a semantic or minimal diff. Missing historical snapshots cannot be reconstructed from old hashes. Argument order is caller-supplied, not verified chronology."}
    if len(freshness.rendered(result)) > freshness.MAX_REGISTRY_BYTES:
        raise freshness.FreshnessError("source comparison exceeds 2 MB")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    capture_parser = sub.add_parser("capture")
    capture_parser.add_argument("registry", type=Path)
    capture_parser.add_argument("source_id")
    capture_parser.add_argument("--out", type=Path, required=True)
    capture_parser.add_argument("--timeout", type=float, default=20)
    verify = sub.add_parser("verify")
    verify.add_argument("directory", type=Path)
    compare = sub.add_parser("compare")
    compare.add_argument("before", type=Path)
    compare.add_argument("after", type=Path)
    dest = compare.add_mutually_exclusive_group(required=True)
    dest.add_argument("--out", type=Path)
    dest.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            if args.out.exists() or args.out.is_symlink():
                raise freshness.FreshnessError("refusing to overwrite a source snapshot")
            if not math.isfinite(args.timeout) or not 0 < args.timeout <= 120:
                raise freshness.FreshnessError("timeout must be positive and at most 120 seconds")
            registry = freshness.load_json(args.registry)
            freshness.validate_registry(registry)
            source = next((s for s in registry["sources"] if s["source_id"] == args.source_id), None)
            if source is None:
                raise freshness.FreshnessError("source ID is absent from the approved registry")
            content, observed = freshness.fetch_content(source, args.timeout)
            capture = {"capture_version": "aau-policy-source-capture/1.0", "source_id": args.source_id,
                       "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "observed": observed}
            create_snapshot(registry, capture, content, args.out)
            verify_snapshot(args.out)
        elif args.command == "verify":
            verify_snapshot(args.directory)
        else:
            report = compare_snapshots(args.before, args.after)
            if args.verify:
                if freshness.load_json(args.verify) != report:
                    raise freshness.FreshnessError("source comparison does not recompute")
            else:
                freshness.write_json(report, args.out)
        print("Source evidence recomputed; human review still required. No baseline or issue was changed.")
        return 0
    except (ValueError, OSError, urllib.error.URLError) as exc:
        print(f"Source evidence failed ({type(exc).__name__}); inspect input integrity, registry, network, and destination.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
