"""Validate the public challenge campaign and build one fork submission."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
EXCHANGE_PATH = ROOT / "independent-reproduction-exchange" / "aau_reproduction.py"
MAX_BYTES = 2_000_000
REGISTRY_VERSION = "aau-accepted-reproductions/1.0"
REGISTRY_BOUNDARIES = {
    "verified_exchange_pack_required",
    "independence_reviewed_status_required",
    "relationship_evidence_human_reviewed",
    "independence_not_cryptographic",
    "not_certification_or_field_effectiveness",
}
ENTRY_ID = re.compile(r"[a-z0-9][a-z0-9-]{2,79}")


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


def safe_accepted_path(value: str) -> Path:
    candidate = safe_campaign_path(value)
    accepted = (HERE / "accepted").resolve()
    try:
        candidate.relative_to(accepted)
    except ValueError as exc:
        raise ValueError("accepted reproduction packs must stay below accepted/") from exc
    return candidate


def campaign_entry(challenge_id: str) -> dict:
    campaign = load_public(HERE / "campaign.json")
    matches = [item for item in campaign["challenges"] if item["challenge_id"] == challenge_id]
    if len(matches) != 1:
        raise ValueError(f"unknown challenge_id: {challenge_id}")
    return matches[0]


def open_challenges() -> list[dict]:
    campaign = verify_campaign()
    return [
        {
            "challenge_id": entry["challenge_id"],
            "title": entry["title"],
            "task_count": entry["task_count"],
            "path": entry["path"],
        }
        for entry in campaign["challenges"]
        if entry["status"] == "open"
    ]


def validate_challenge_sources(entry: dict, challenge: dict) -> None:
    if entry["status"] != "open":
        return
    mutable_markers = ("/blob/main/", "/raw/main/", "/refs/heads/", "/main/")
    for source in challenge["official_sources"]:
        url = source["url"]
        if (
            ("github.com" in url or "raw.githubusercontent.com" in url)
            and any(marker in url for marker in mutable_markers)
        ):
            raise ValueError("open challenges cannot cite a mutable GitHub branch URL")


def verify_reproduction_registry(
    campaign: dict,
    registry: dict | None = None,
    pack_overrides: dict[str, Path] | None = None,
) -> dict:
    module = exchange_module()
    value = registry if registry is not None else load_public(HERE / "accepted-reproductions.json")
    if set(value) != {"registry_version", "entries", "boundary"}:
        raise ValueError("accepted-reproduction registry fields differ from the 1.0 contract")
    if value["registry_version"] != REGISTRY_VERSION:
        raise ValueError("unsupported accepted-reproduction registry version")
    boundaries = value["boundary"]
    if (
        not isinstance(boundaries, dict)
        or set(boundaries) != REGISTRY_BOUNDARIES
        or any(boundaries[key] is not True for key in REGISTRY_BOUNDARIES)
    ):
        raise ValueError("accepted-reproduction boundaries must be explicit and true")
    entries = value["entries"]
    if not isinstance(entries, list) or len(entries) > 200:
        raise ValueError("accepted-reproduction entries must be a bounded list")
    if campaign["independently_reproduced_count"] != len(entries):
        raise ValueError("campaign independent count must equal verified registry entries")

    challenge_entries = {entry["challenge_id"]: entry for entry in campaign["challenges"]}
    challenges = {
        challenge_id: load_public(safe_campaign_path(entry["path"]))
        for challenge_id, entry in challenge_entries.items()
    }
    seen_ids: set[str] = set()
    seen_packs: set[str] = set()
    seen_submissions: set[str] = set()
    seen_producers: set[str] = set()
    seen_challenges: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "entry_id", "challenge_id", "pack_path", "accepted_on",
            "adjudication_sha256", "subject_sha256",
        }:
            raise ValueError("accepted-reproduction entry fields differ from the 1.0 contract")
        if (
            not isinstance(entry["entry_id"], str)
            or not entry["entry_id"]
            or entry["entry_id"] in seen_ids
        ):
            raise ValueError("accepted-reproduction entry ids must be non-empty and unique")
        seen_ids.add(entry["entry_id"])
        if not isinstance(entry["challenge_id"], str) or entry["challenge_id"] not in challenges:
            raise ValueError("accepted reproduction names an unknown challenge")
        if entry["challenge_id"] in seen_challenges:
            raise ValueError("a revealed challenge can have only one accepted blind reproduction")
        seen_challenges.add(entry["challenge_id"])
        if challenge_entries[entry["challenge_id"]]["status"] != "closed":
            raise ValueError("a challenge must close when its accepted pack reveals the oracle")
        if not isinstance(entry["pack_path"], str):
            raise ValueError("accepted reproduction pack paths must be text")
        registered_pack = safe_accepted_path(entry["pack_path"])
        if entry["pack_path"] in seen_packs:
            raise ValueError("accepted reproduction pack paths must be unique")
        seen_packs.add(entry["pack_path"])
        for field in ("adjudication_sha256", "subject_sha256"):
            digest = entry[field]
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
            ):
                raise ValueError(f"accepted reproduction {field} must be a lowercase SHA-256")
        try:
            date.fromisoformat(entry["accepted_on"])
        except (TypeError, ValueError) as exc:
            raise ValueError("accepted_on must be an ISO calendar date") from exc

        pack = (pack_overrides or {}).get(entry["pack_path"], registered_pack)
        adjudication = module.verify_pack(pack)
        challenge = challenges[entry["challenge_id"]]
        if (
            adjudication["status"] != "independence_reviewed"
            or adjudication["evidence_level"] != "independently_reproduced"
            or adjudication["challenge_id"] != entry["challenge_id"]
            or adjudication["challenge_sha256"] != challenge["challenge_sha256"]
            or adjudication["adjudication_sha256"] != entry["adjudication_sha256"]
            or adjudication["subject"]["sha256"] != entry["subject_sha256"]
        ):
            raise ValueError("accepted reproduction does not match its reviewed pack or challenge")
        submission = adjudication["submission_sha256"]
        producer = adjudication["role_commitments"]["producer"]
        if submission in seen_submissions or producer in seen_producers:
            raise ValueError("accepted reproductions must have unique submissions and producers")
        seen_submissions.add(submission)
        seen_producers.add(producer)
    if [entry["entry_id"] for entry in entries] != sorted(seen_ids):
        raise ValueError("accepted reproductions must be sorted by entry_id")
    return value


def plan_acceptance(
    challenge_id: str,
    pack: Path,
    entry_id: str,
    accepted_on: str,
    out: Path,
) -> dict:
    module = exchange_module()
    campaign = verify_campaign()
    registry = load_public(HERE / "accepted-reproductions.json")
    entry = campaign_entry(challenge_id)
    if entry["status"] != "open":
        raise ValueError("the selected challenge is already closed")
    if not ENTRY_ID.fullmatch(entry_id):
        raise ValueError("entry_id must be a 3-80 character lowercase slug")
    try:
        date.fromisoformat(accepted_on)
    except ValueError as exc:
        raise ValueError("accepted_on must be an ISO calendar date") from exc
    source_pack = pack.absolute()
    adjudication = module.verify_pack(source_pack)
    challenge = load_public(safe_campaign_path(entry["path"]))
    if (
        adjudication["status"] != "independence_reviewed"
        or adjudication["evidence_level"] != "independently_reproduced"
        or adjudication["challenge_id"] != challenge_id
        or adjudication["challenge_sha256"] != challenge["challenge_sha256"]
    ):
        raise ValueError("only an independence-reviewed pack for the current challenge can be planned")

    pack_path = f"accepted/{entry_id}"
    proposed_campaign = json.loads(json.dumps(campaign))
    proposed_entry = next(
        item for item in proposed_campaign["challenges"]
        if item["challenge_id"] == challenge_id
    )
    proposed_entry["status"] = "closed"
    proposed_campaign["independently_reproduced_count"] += 1
    accepted_entry = {
        "entry_id": entry_id,
        "challenge_id": challenge_id,
        "pack_path": pack_path,
        "accepted_on": accepted_on,
        "adjudication_sha256": adjudication["adjudication_sha256"],
        "subject_sha256": adjudication["subject"]["sha256"],
    }
    proposed_registry = json.loads(json.dumps(registry))
    proposed_registry["entries"].append(accepted_entry)
    proposed_registry["entries"].sort(key=lambda item: item["entry_id"])
    verify_reproduction_registry(
        proposed_campaign,
        proposed_registry,
        pack_overrides={pack_path: source_pack},
    )

    if out.exists() or out.is_symlink():
        raise ValueError(f"refusing to overwrite acceptance plan: {out}")
    campaign_bytes = (json.dumps(proposed_campaign, indent=2) + "\n").encode()
    registry_bytes = (json.dumps(proposed_registry, indent=2) + "\n").encode()
    plan = {
        "plan_version": "aau-reproduction-acceptance-plan/1.0",
        "entry": accepted_entry,
        "source_pack": {
            "challenge_sha256": adjudication["challenge_sha256"],
            "submission_sha256": adjudication["submission_sha256"],
            "adjudication_sha256": adjudication["adjudication_sha256"],
            "subject_sha256": adjudication["subject"]["sha256"],
        },
        "proposed_campaign_sha256": hashlib.sha256(campaign_bytes).hexdigest(),
        "proposed_registry_sha256": hashlib.sha256(registry_bytes).hexdigest(),
        "boundary": {
            "source_pack_not_copied": True,
            "repository_not_modified": True,
            "human_review_before_publication_required": True,
            "oracle_reveal_closes_challenge": True,
            "not_certification_or_field_effectiveness": True,
        },
    }
    plan_bytes = (json.dumps(plan, indent=2) + "\n").encode()
    readme = (
        "# Reproduction acceptance plan\n\n"
        "This non-mutating plan was built only after the source Exchange pack recomputed as "
        "`independence_reviewed`. Review the relationship evidence and disclosed limitations, copy "
        f"the exact verified pack to `reproduction-challenges/{pack_path}/`, then replace campaign.json "
        "and accepted-reproductions.json with the proposed files. Run `python3 "
        "reproduction-challenges/submit.py verify-campaign` before commit. Oracle reveal closes the "
        "challenge. This is not certification or field-effectiveness evidence.\n"
    ).encode()
    payloads = {
        "README.md": readme,
        "acceptance-plan.json": plan_bytes,
        "campaign.proposed.json": campaign_bytes,
        "accepted-reproductions.proposed.json": registry_bytes,
    }
    sums = "".join(
        f"{hashlib.sha256(payload).hexdigest()}  {name}\n"
        for name, payload in sorted(payloads.items())
    ).encode()
    out.mkdir(parents=True)
    for name, payload in {**payloads, "SHA256SUMS": sums}.items():
        (out / name).write_bytes(payload)
    return plan


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
        if entry["status"] not in {"open", "closed"} or type(entry["task_count"]) is not int or entry["task_count"] < 1:
            raise ValueError("campaign challenges must have a valid status and positive task count")
        if entry["challenge_id"] in ids:
            raise ValueError("challenge ids must be unique")
        ids.add(entry["challenge_id"])
        challenge = load_public(safe_campaign_path(entry["path"]))
        module.validate_challenge(challenge)
        if challenge["challenge_id"] != entry["challenge_id"]:
            raise ValueError("campaign challenge id does not match its artifact")
        if entry["task_count"] != len(challenge["tasks"]):
            raise ValueError("campaign task count does not match its challenge artifact")
        validate_challenge_sources(entry, challenge)
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
    verify_reproduction_registry(campaign)
    return campaign


def build_submission(challenge_id: str, responses_path: str, metadata_path: str, out: Path) -> dict:
    module = exchange_module()
    verify_campaign()
    entry = campaign_entry(challenge_id)
    if entry["status"] != "open":
        raise ValueError("the selected challenge is closed after oracle reveal")
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
    listing = sub.add_parser("list-open")
    listing.add_argument("--json", action="store_true")
    build = sub.add_parser("build")
    build.add_argument("--challenge-id", required=True)
    build.add_argument("--responses", required=True)
    build.add_argument("--metadata", required=True)
    build.add_argument("--out", type=Path, required=True)
    accepting = sub.add_parser("plan-accept")
    accepting.add_argument("--challenge-id", required=True)
    accepting.add_argument("--pack", type=Path, required=True)
    accepting.add_argument("--entry-id", required=True)
    accepting.add_argument("--accepted-on", required=True)
    accepting.add_argument("--out", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "verify-campaign":
            campaign = verify_campaign()
            accepted = campaign["independently_reproduced_count"]
            open_count = sum(entry["status"] == "open" for entry in campaign["challenges"])
            print(
                f"OK: {open_count} open answer-free challenges, "
                f"{len(campaign['challenges'])} total artifacts, and "
                f"{accepted} accepted independent reproductions verified."
            )
        elif args.command == "list-open":
            challenges = open_challenges()
            if args.json:
                print(json.dumps(challenges, indent=2))
            else:
                for challenge in challenges:
                    print(
                        f"{challenge['challenge_id']}\t{challenge['task_count']} tasks\t"
                        f"{challenge['title']}"
                    )
        elif args.command == "build":
            submission = build_submission(
                args.challenge_id, args.responses, args.metadata, args.out
            )
            print(f"OK: challenge-bound submission {submission['submission_sha256']} written to {args.out}.")
        else:
            plan = plan_acceptance(
                args.challenge_id, args.pack, args.entry_id, args.accepted_on, args.out
            )
            print(
                f"OK: non-mutating acceptance plan for {plan['entry']['entry_id']} "
                f"written to {args.out}."
            )
        return 0
    except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"aau reproduction challenge: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
