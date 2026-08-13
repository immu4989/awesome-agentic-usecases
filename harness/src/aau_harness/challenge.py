"""Machine-validated missions and evidence-derived Challenge achievements."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from .catalog_cli import find_root
from .gallery import LEVEL_RANK, build_gallery


CHALLENGE_VERSION = "aau-challenge/1.0"
ENTRY_VERSION = "aau-challenge-entry/1.0"
TRACKS = ("Reproduce", "Break", "Adapt")


class ChallengeError(ValueError):
    """Raised when a challenge or submission makes an unsupported claim."""


def load_challenges(root: Path) -> dict[str, Any]:
    path = root / "challenge" / "challenges.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ChallengeError(f"cannot read {path}: {exc}") from exc
    if data.get("version") != CHALLENGE_VERSION:
        raise ChallengeError(f"challenge catalog must use {CHALLENGE_VERSION}")
    challenges = data.get("challenges")
    if not isinstance(challenges, list) or len(challenges) < 5:
        raise ChallengeError("challenge catalog must contain at least five missions")
    ids = [item.get("id") for item in challenges]
    if len(ids) != len(set(ids)):
        raise ChallengeError("challenge ids must be unique")
    numbers = [item.get("number") for item in challenges]
    if len(numbers) != len(set(numbers)):
        raise ChallengeError("challenge numbers must be unique")
    for item in challenges:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(item.get("id", ""))):
            raise ChallengeError("challenge id must be a lowercase hyphenated slug")
        if item.get("track") not in TRACKS:
            raise ChallengeError(f"{item.get('id')}: unsupported track")
        if not (root / str(item.get("starter_lab", ""))).is_dir():
            raise ChallengeError(f"{item.get('id')}: starter lab does not exist")
        for field in ("title", "beneficiary", "mission", "trap", "command", "success", "artifact"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ChallengeError(f"{item.get('id')}: {field} is required")
    return data


def achievements_for(item: dict[str, Any]) -> list[str]:
    """Return achievement ids derived only from evaluated Gallery evidence."""
    earned = ["receipt-ready"]
    evidence = item["evidence"]
    checks = {check["check"]: check["passed"] for check in item["trust"]["checks"]}
    if evidence["observed_failure_modes"] >= 3:
        earned.append("failure-hunter")
    if evidence["real_result_artifacts"] >= 1 and evidence["minimum_repeats"] >= 3:
        earned.append("repeat-runner")
    if evidence["model_count"] >= 2:
        earned.append("cross-model-witness")
    if evidence["source_links"] >= 2 and checks.get("named review", False):
        earned.append("domain-grounder")
    if checks.get("protected authority", False):
        earned.append("boundary-keeper")
    return earned


def _safe_repo_path(root: Path, value: Any, field: str, suffix: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise ChallengeError(f"{field} must be a repository-relative path")
    path = root / value
    if path.suffix != suffix:
        raise ChallengeError(f"{field} must end in {suffix}")
    if not path.is_file():
        raise ChallengeError(f"{field} does not exist: {value}")
    return path


def _validate_receipt(root: Path, receipt: dict[str, Any], challenge_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {"schema_version", "id", "challenge_id", "track", "contributor", "lab_path", "claim", "evidence"}
    if not isinstance(receipt, dict) or set(receipt) != required:
        raise ChallengeError("Challenge receipt fields must exactly match the published schema")
    if receipt["schema_version"] != ENTRY_VERSION:
        raise ChallengeError(f"Challenge receipts must use {ENTRY_VERSION}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(receipt["id"])):
        raise ChallengeError("Challenge receipt id must be a lowercase hyphenated slug")
    challenge = challenge_by_id.get(receipt["challenge_id"])
    if not challenge:
        raise ChallengeError(f"{receipt['id']}: unknown challenge id {receipt['challenge_id']!r}")
    if challenge["track"] not in {"Reproduce", "Break"} or receipt["track"] != challenge["track"]:
        raise ChallengeError(f"{receipt['id']}: receipt track must match a Reproduce or Break mission")
    if receipt["lab_path"] != challenge["starter_lab"]:
        raise ChallengeError(f"{receipt['id']}: receipt lab must match the mission starter lab")
    contributor = receipt["contributor"]
    if not isinstance(contributor, dict) or set(contributor) != {"name", "github"}:
        raise ChallengeError(f"{receipt['id']}: contributor needs exactly name and github")
    if not all(isinstance(contributor[field], str) and contributor[field].strip() for field in ("name", "github")):
        raise ChallengeError(f"{receipt['id']}: contributor name and github are required")
    github = contributor["github"].lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", github):
        raise ChallengeError(f"{receipt['id']}: invalid GitHub handle")
    if not isinstance(receipt["claim"], str) or not 1 <= len(receipt["claim"].strip()) <= 240:
        raise ChallengeError(f"{receipt['id']}: claim must contain 1 to 240 characters")
    evidence = receipt["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != {"result_path", "note_path", "scenario_ids"}:
        raise ChallengeError(f"{receipt['id']}: evidence needs exactly result_path, note_path, and scenario_ids")
    result_path = _safe_repo_path(root, evidence["result_path"], "evidence.result_path", ".json")
    note_path = _safe_repo_path(root, evidence["note_path"], "evidence.note_path", ".md")
    if result_path.parent != root / receipt["lab_path"] / "results":
        raise ChallengeError(f"{receipt['id']}: result must be committed in the starter lab results directory")
    if note_path.parent != root / "challenge" / "receipts":
        raise ChallengeError(f"{receipt['id']}: note must be committed directly under challenge/receipts")
    scenario_ids = evidence["scenario_ids"]
    if not isinstance(scenario_ids, list) or not 1 <= len(scenario_ids) <= 10 or len(set(scenario_ids)) != len(scenario_ids):
        raise ChallengeError(f"{receipt['id']}: one to ten unique scenario ids are required")
    scenarios_path = root / receipt["lab_path"] / "evals" / "scenarios.jsonl"
    available = {
        json.loads(line)["scenario_id"]
        for line in scenarios_path.read_text().splitlines()
        if line.strip()
    }
    missing = [scenario_id for scenario_id in scenario_ids if scenario_id not in available]
    if missing:
        raise ChallengeError(f"{receipt['id']}: scenario ids not found in starter lab: {', '.join(missing)}")
    result = json.loads(result_path.read_text())
    repeats = int(result.get("n_repeats", 0) or 0)
    if repeats < 3 or int(result.get("n_scenarios", 0) or 0) < 1:
        raise ChallengeError(f"{receipt['id']}: result needs at least one scenario and three repeats")
    if not all(scenario_id in note_path.read_text() for scenario_id in scenario_ids):
        raise ChallengeError(f"{receipt['id']}: note must name every declared scenario id")
    return {
        "entry_id": receipt["id"],
        "type": "community",
        "track": receipt["track"],
        "challenge_id": receipt["challenge_id"],
        "title": challenge["title"],
        "lab_path": receipt["lab_path"],
        "contributor": {**contributor, "github": github, "profile_url": f"https://github.com/{github}"},
        "trust": {"level": "Receipt verified", "score": {"passed": 5, "total": 5}},
        "evidence": {"scenario_count": len(scenario_ids), "minimum_repeats": repeats},
        "achievements": ["receipt-ready"] + (["failure-hunter"] if receipt["track"] == "Break" else []) + (["repeat-runner"] if result.get("model") != "mock" and result.get("backend") != "mock" else []),
        "finish": True,
        "finish_detail": f"valid {receipt['track']} receipt; {len(scenario_ids)} traced scenario(s), n={repeats}",
        "record_path": f"challenge/entries/{receipt['id']}.json",
    }


def load_receipts(root: Path, challenge_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for path in sorted((root / "challenge" / "entries").glob("*.json")):
        try:
            receipt = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ChallengeError(f"invalid JSON in {path.relative_to(root)}: {exc}") from exc
        evaluated = _validate_receipt(root, receipt, challenge_by_id)
        if path.stem != evaluated["entry_id"]:
            raise ChallengeError(f"{path.relative_to(root)}: filename must match receipt id")
        receipts.append(evaluated)
    return receipts


def _finish_status(item: dict[str, Any], challenge: dict[str, Any]) -> tuple[bool, str]:
    track = challenge["track"]
    minimum = "Generated" if track == "Adapt" else "Reproduced"
    level = item["trust"]["level"]
    passed = level in LEVEL_RANK and LEVEL_RANK[level] >= LEVEL_RANK[minimum]
    if track == "Break":
        passed = passed and item["evidence"]["observed_failure_modes"] >= 3
    detail = f"{level}; minimum for {track} is {minimum}"
    return passed, detail


def build_challenge(root: Path) -> dict[str, Any]:
    catalog = load_challenges(root)
    challenge_by_id = {item["id"]: item for item in catalog["challenges"]}
    gallery = build_gallery(root)
    scoreboard: list[dict[str, Any]] = []
    community_finishes = 0
    community_participants: set[str] = set()
    for receipt in load_receipts(root, challenge_by_id):
        scoreboard.append(receipt)
        community_participants.add(receipt["contributor"]["github"].lower())
        community_finishes += 1
    for entry in gallery["entries"]:
        metadata = entry.get("challenge")
        entry_type = "reference"
        track = "Reference"
        challenge_id = None
        finish = True
        finish_detail = "Maintainer reference; shown as a benchmark, not a community finish"
        if metadata:
            challenge_id = metadata["id"]
            challenge = challenge_by_id.get(challenge_id)
            if not challenge:
                raise ChallengeError(f"{entry['id']}: unknown challenge id {challenge_id!r}")
            if metadata["track"] != challenge["track"]:
                raise ChallengeError(f"{entry['id']}: declared track does not match challenge catalog")
            entry_type = "community"
            track = metadata["track"]
            finish, finish_detail = _finish_status(entry, challenge)
            community_participants.add(entry["contributor"]["github"].lower())
            community_finishes += int(finish)
        scoreboard.append({
            "entry_id": entry["id"],
            "type": entry_type,
            "track": track,
            "challenge_id": challenge_id,
            "title": entry["title"],
            "lab_path": entry["lab_path"],
            "contributor": entry["contributor"],
            "trust": entry["trust"],
            "evidence": entry["evidence"],
            "achievements": achievements_for(entry),
            "finish": finish,
            "finish_detail": finish_detail,
            "record_path": f"gallery/entries/{entry['id']}.json",
        })
    scoreboard.sort(key=lambda item: (item["type"] != "community", not item["finish"], item["title"]))
    return {
        **catalog,
        "stats": {
            "live_challenges": len(catalog["challenges"]),
            "community_participants": len(community_participants),
            "community_finishes": community_finishes,
            "reference_finishes": sum(item["type"] == "reference" for item in scoreboard),
            "achievements": len(catalog["achievements"]),
        },
        "scoreboard": scoreboard,
        "boundary": "Challenge status is derived from repository evidence. It is not production certification, regulatory approval, or permission to automate protected authority.",
    }


def _resolve_challenge(data: dict[str, Any], target: str) -> dict[str, Any]:
    matches = [item for item in data["challenges"] if target in {item["id"], item["number"]}]
    if len(matches) != 1:
        raise ChallengeError(f"challenge target must match one id or number: {target!r}")
    return matches[0]


def _render_challenge(item: dict[str, Any]) -> str:
    return "\n".join([
        f"{item['number']} · {item['track']} · {item['title']}",
        f"For:      {item['beneficiary']}",
        f"Time:     about {item['minutes']} minutes",
        f"Mission:  {item['mission']}",
        f"Trap:     {item['trap']}",
        f"Evidence: {item['artifact']}",
        "",
        "Run for $0:",
        f"  {item['command']}",
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau-challenge", description="Run and validate AAU Reliability Challenge missions.")
    parser.add_argument("command", nargs="?", choices=("list", "show", "validate"), default="list")
    parser.add_argument("target", nargs="?", help="challenge id/number, or Gallery id for validate")
    parser.add_argument("--root", type=Path, help="repository checkout")
    parser.add_argument("--track", choices=TRACKS, help="filter challenge list")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)
    root = find_root(args.root) if args.root else find_root()
    try:
        data = build_challenge(root)
        if args.command == "show":
            if not args.target:
                raise ChallengeError("show requires a challenge id or number")
            item = _resolve_challenge(data, args.target)
            print(json.dumps(item, indent=2) if args.json else _render_challenge(item))
            return 0
        if args.command == "validate":
            if not args.target:
                raise ChallengeError("validate requires a Challenge receipt or Gallery entry id")
            matches = [item for item in data["scoreboard"] if item["entry_id"] == args.target]
            if len(matches) != 1 or matches[0]["type"] != "community":
                raise ChallengeError(f"no community Challenge entry matches {args.target!r}")
            item = matches[0]
            print(json.dumps(item, indent=2) if args.json else "\n".join([
                f"{'PASS' if item['finish'] else 'NEXT'} · {item['entry_id']} · {item['track']}",
                item["finish_detail"],
                "Achievements: " + ", ".join(item["achievements"]),
            ]))
            return 0 if item["finish"] else 1
        challenges = data["challenges"]
        if args.track:
            challenges = [item for item in challenges if item["track"] == args.track]
        if args.json:
            print(json.dumps({**data, "challenges": challenges}, indent=2))
        else:
            for item in challenges:
                print(f"{item['number']}  {item['track']:<9} {item['title']} · ~{item['minutes']} min")
                print(f"     {item['id']}")
        return 0
    except (ChallengeError, OSError) as exc:
        print(f"AAU Challenge stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
