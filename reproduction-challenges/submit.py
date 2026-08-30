"""Validate the public challenge campaign and build one fork submission."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
EXCHANGE_PATH = ROOT / "independent-reproduction-exchange" / "aau_reproduction.py"
MAX_BYTES = 2_000_000


def exchange_module():
    spec = importlib.util.spec_from_file_location("aau_reproduction", EXCHANGE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("independent reproduction module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_public(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError(f"invalid, oversized, or symbolic-link file: {path}")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected one JSON object in {path}")
    return value


def safe_user_path(value: str) -> Path:
    candidate = (ROOT / value).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("response and metadata paths must stay below the checkout") from exc
    current = ROOT
    for part in Path(value).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"input path contains a symbolic link: {value}")
    return candidate


def safe_campaign_path(value: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError("campaign artifact paths must be non-empty relative paths")
    candidate = (HERE / value).resolve()
    try:
        candidate.relative_to(HERE)
    except ValueError as exc:
        raise ValueError("campaign artifact paths must stay below reproduction-challenges") from exc
    current = HERE
    for part in Path(value).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"campaign artifact path contains a symbolic link: {value}")
    return candidate


def campaign_entry(challenge_id: str) -> dict:
    campaign = load_public(HERE / "campaign.json")
    matches = [item for item in campaign["challenges"] if item["challenge_id"] == challenge_id]
    if len(matches) != 1:
        raise ValueError(f"unknown challenge_id: {challenge_id}")
    return matches[0]


def verify_campaign() -> dict:
    module = exchange_module()
    campaign = load_public(HERE / "campaign.json")
    if set(campaign) != {
        "campaign_version",
        "campaign_id",
        "status",
        "independently_reproduced_count",
        "challenges",
        "boundary",
    }:
        raise ValueError("campaign fields differ from the 1.0 contract")
    if campaign["campaign_version"] != "aau-fork-to-reproduce-campaign/1.0":
        raise ValueError("unsupported campaign version")
    reproduced = campaign["independently_reproduced_count"]
    if campaign["status"] != "open":
        raise ValueError("the campaign must be open")
    if type(reproduced) is not int or reproduced < 0:
        raise ValueError("independently_reproduced_count must be a non-negative integer")
    if not isinstance(campaign["challenges"], list) or len(campaign["challenges"]) < 1:
        raise ValueError("the campaign must contain at least one challenge")
    ids = set()
    for entry in campaign["challenges"]:
        if set(entry) != {
            "challenge_id", "title", "path", "responses_template",
            "metadata_template", "task_count", "status",
        }:
            raise ValueError("campaign challenge fields differ from the 1.0 contract")
        if entry["status"] != "open" or type(entry["task_count"]) is not int or entry["task_count"] < 1:
            raise ValueError("campaign challenges must be open with a positive task count")
        if entry["challenge_id"] in ids:
            raise ValueError("challenge ids must be unique")
        ids.add(entry["challenge_id"])
        challenge = load_public(safe_campaign_path(entry["path"]))
        module.validate_challenge(challenge)
        if challenge["challenge_id"] != entry["challenge_id"]:
            raise ValueError("campaign challenge id does not match its artifact")
        if entry["task_count"] != len(challenge["tasks"]):
            raise ValueError("campaign task count does not match its challenge artifact")
        serialized = json.dumps(challenge)
        for forbidden in (
            "gold_outcome",
            "gold_actions",
            "human_escalation_required",
            "service_must_be_preserved",
        ):
            if forbidden in serialized:
                raise ValueError(f"public challenge leaks oracle field: {forbidden}")
        template = load_public(safe_campaign_path(entry["responses_template"]))
        template_ids = {row["task_id"] for row in template["responses"]}
        challenge_ids = {row["task_id"] for row in challenge["tasks"]}
        if template_ids != challenge_ids or len(template_ids) != entry["task_count"]:
            raise ValueError("response template does not cover the exact challenge task set")
        load_public(safe_campaign_path(entry["metadata_template"]))
    boundaries = campaign["boundary"]
    if not isinstance(boundaries, dict) or not boundaries or any(value is not True for value in boundaries.values()):
        raise ValueError("all campaign boundary declarations must be true")
    return campaign


def build_submission(challenge_id: str, responses_path: str, metadata_path: str, out: Path) -> dict:
    module = exchange_module()
    verify_campaign()
    entry = campaign_entry(challenge_id)
    challenge = load_public(HERE / entry["path"])
    responses = load_public(safe_user_path(responses_path))
    metadata = load_public(safe_user_path(metadata_path))
    submission = module.build_submission(challenge, responses, metadata)
    if out.exists() or out.is_symlink():
        raise ValueError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(submission, indent=2) + "\n")
    return submission


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Build an answer-free AAU reproduction submission")
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("verify-campaign")
    build = sub.add_parser("build")
    build.add_argument("--challenge-id", required=True)
    build.add_argument("--responses", required=True)
    build.add_argument("--metadata", required=True)
    build.add_argument("--out", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "verify-campaign":
            campaign = verify_campaign()
            print(f"OK: {len(campaign['challenges'])} answer-free challenges verified.")
        else:
            submission = build_submission(
                args.challenge_id, args.responses, args.metadata, args.out
            )
            print(f"OK: challenge-bound submission {submission['submission_sha256']} written to {args.out}.")
        return 0
    except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"aau reproduction challenge: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
