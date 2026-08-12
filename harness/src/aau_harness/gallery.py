"""Evidence-derived trust levels for AAU Forge Gallery adaptations.

Gallery contributors describe the adaptation; this module derives its public status from
committed artifacts. A label is therefore a reproducible claim, not a self-selected badge.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from .catalog_cli import find_root
from .forge import diagnose_forged_lab


GALLERY_VERSION = "aau-gallery/1.0"
LEVELS = ("Generated", "Domain reviewed", "Reproduced", "Verified")
DRAFT_LEVEL = "Draft"
LEVEL_RANK = {level: index for index, level in enumerate(LEVELS)}
ENTRY_REQUIRED = {
    "schema_version",
    "id",
    "origin",
    "lab_path",
    "contributor",
    "summary",
    "why_fork",
    "tags",
    "review",
}
ORIGINS = {"forge-adaptation", "maintainer-reference"}
MAINTAINER_REFERENCES = {
    ("batch-disposition-reference", "pharmaceutical-manufacturing/batch-disposition-gate"),
    ("medicaid-renewal-reference", "medicaid-chip/renewal-continuity-navigator"),
    ("pipeline-notification-reference", "pipeline-safety/incident-notification-coordinator"),
}


class GalleryError(ValueError):
    """Raised when a gallery entry cannot support a truthful public claim."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise GalleryError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GalleryError(f"invalid JSON in {path}: {exc}") from exc


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_entry_shape(entry: Any, source: str = "gallery entry") -> None:
    if not isinstance(entry, dict):
        raise GalleryError(f"{source} must be a JSON object")
    missing = ENTRY_REQUIRED - entry.keys()
    if missing:
        raise GalleryError(f"{source} is missing {', '.join(sorted(missing))}")
    unexpected = entry.keys() - ENTRY_REQUIRED
    if unexpected:
        raise GalleryError(f"{source} has unsupported fields: {', '.join(sorted(unexpected))}")
    if entry["schema_version"] != GALLERY_VERSION:
        raise GalleryError(f"{source} must use schema_version {GALLERY_VERSION!r}")
    if entry["origin"] not in ORIGINS:
        raise GalleryError(f"{source}.origin must be one of {sorted(ORIGINS)}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(entry["id"])):
        raise GalleryError(f"{source}.id must be a lowercase hyphenated slug")
    parts = str(entry["lab_path"]).split("/")
    if len(parts) != 2 or any(not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", part) for part in parts):
        raise GalleryError(f"{source}.lab_path must be '<industry>/<use-case>'")
    if entry["origin"] == "maintainer-reference" and (entry["id"], entry["lab_path"]) not in MAINTAINER_REFERENCES:
        raise GalleryError(
            f"{source}: new submissions must use origin 'forge-adaptation'"
        )
    for field in ("summary", "why_fork"):
        if not _nonempty(entry[field]):
            raise GalleryError(f"{source}.{field} must be a non-empty string")
    if len(entry["summary"]) > 240 or len(entry["why_fork"]) > 240:
        raise GalleryError(f"{source} summary and why_fork must each be at most 240 characters")
    if not isinstance(entry["tags"], list) or not 2 <= len(entry["tags"]) <= 6:
        raise GalleryError(f"{source}.tags must contain two to six labels")
    if any(not _nonempty(tag) for tag in entry["tags"]):
        raise GalleryError(f"{source}.tags must contain only non-empty strings")
    contributor = entry["contributor"]
    if not isinstance(contributor, dict) or not _nonempty(contributor.get("name")):
        raise GalleryError(f"{source}.contributor.name is required")
    if not _nonempty(contributor.get("github")):
        raise GalleryError(f"{source}.contributor.github is required")
    github = contributor["github"].lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", github):
        raise GalleryError(f"{source}.contributor.github must be a GitHub handle")
    review = entry["review"]
    if not isinstance(review, dict):
        raise GalleryError(f"{source}.review must be an object")
    for field in ("reviewer", "reviewer_role", "scope", "reviewed_at", "source_ledger"):
        if field in review and not isinstance(review[field], str):
            raise GalleryError(f"{source}.review.{field} must be a string when supplied")
    ledger = review.get("source_ledger", "")
    if ledger and (
        Path(ledger).is_absolute()
        or ".." in Path(ledger).parts
        or not re.fullmatch(r"[A-Za-z0-9_./-]+\.md", ledger)
    ):
        raise GalleryError(f"{source}.review.source_ledger must be a repository-relative Markdown path")


def load_entries(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    entries: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted((root / "gallery" / "entries").glob("*.json")):
        entry = _load_json(path)
        validate_entry_shape(entry, str(path.relative_to(root)))
        entries.append((path, entry))
    if not entries:
        raise GalleryError("gallery/entries contains no adaptations")
    ids = [entry["id"] for _, entry in entries]
    labs = [entry["lab_path"] for _, entry in entries]
    if len(ids) != len(set(ids)):
        raise GalleryError("gallery entry ids must be unique")
    if len(labs) != len(set(labs)):
        raise GalleryError("gallery lab paths must be unique")
    return entries


def _count_scenarios(lab: Path) -> int:
    path = lab / "evals" / "scenarios.jsonl"
    return sum(bool(line.strip()) for line in path.read_text().splitlines()) if path.is_file() else 0


def _result_evidence(lab: Path) -> dict[str, Any]:
    real_results: list[dict[str, Any]] = []
    mock_available = False
    for path in sorted((lab / "results").glob("eval_*.json")):
        try:
            result = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if result.get("backend") == "mock" or result.get("model") == "mock":
            mock_available = True
        else:
            real_results.append(result)
    models = sorted({str(result.get("model") or result.get("backend")) for result in real_results})
    repeats = [int(result.get("n_repeats", 0) or 0) for result in real_results]
    scenario_runs = sum(
        int(result.get("n_scenarios", 0) or 0) * int(result.get("n_repeats", 0) or 0)
        for result in real_results
    )
    return {
        "mock_available": mock_available,
        "real_result_artifacts": len(real_results),
        "models": models,
        "model_count": len(models),
        "minimum_repeats": min(repeats) if repeats else 0,
        "real_scenario_runs": scenario_runs,
    }


def _observed_failures(lab: Path) -> int:
    path = lab / "FAILURE_MODES.md"
    if not path.is_file():
        return 0
    text = path.read_text()
    if "generated hypotheses" in text.lower() or "TODO(domain)" in text:
        return 0
    return len(re.findall(r"^###\s+\d+\.", text, re.MULTILINE))


def _domain_placeholders(lab: Path) -> list[str]:
    hits: list[str] = []
    for path in sorted(lab.rglob("*")):
        if not path.is_file() or path.suffix not in {".py", ".md", ".json", ".toml"}:
            continue
        if any(part in {"results", "evals", "__pycache__"} for part in path.parts):
            continue
        text = path.read_text(errors="replace")
        if "TODO(domain)" in text or "TODO-DOMAIN" in text or "TODO_DOMAIN" in text:
            hits.append(str(path.relative_to(lab)))
    return hits


def _check_record(check: str, passed: bool, detail: str, stage: str) -> dict[str, Any]:
    return {"check": check, "passed": bool(passed), "detail": detail, "stage": stage}


def evaluate_entry(root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    """Compute one entry's trust level solely from committed evidence."""

    lab = root / entry["lab_path"]
    if not lab.is_dir():
        raise GalleryError(f"{entry['id']}: lab does not exist: {entry['lab_path']}")
    catalog = _load_json(root / "docs" / "use-cases.json")
    catalog_item = next((item for item in catalog if item["path"] == entry["lab_path"]), None)
    studio = _load_json(root / "docs" / "studio-data.json")
    public_item = next((item for item in studio["cases"] if item["path"] == entry["lab_path"]), None)

    ledger_value = entry["review"].get("source_ledger", "")
    source_ledger = root / ledger_value if _nonempty(ledger_value) else None
    ledger_text = source_ledger.read_text(errors="replace") if source_ledger and source_ledger.is_file() else ""
    source_links = len(re.findall(r"https?://", ledger_text))
    result_evidence = _result_evidence(lab)
    scenarios = _count_scenarios(lab)
    failures = _observed_failures(lab)
    placeholders = _domain_placeholders(lab)
    readme = (lab / "README.md").read_text(errors="replace") if (lab / "README.md").is_file() else ""

    required_package = all((lab / name).exists() for name in ("README.md", "pyproject.toml", "tests", "evals"))
    reference_origin = entry["origin"] == "maintainer-reference"
    forge_manifest = lab / "aau-forge.json"
    blueprint = lab / "contract-blueprint.json"
    forge_doctor: dict[str, Any] | None = None
    if reference_origin:
        if not public_item:
            raise GalleryError(f"{entry['id']}: maintainer reference must be in the verified catalog")
        provenance_ok = True
        provenance_detail = "maintainer reference predates Forge; canonical catalog provenance used"
        contract_ok = bool(public_item.get("contract", {}).get("name"))
        contract_detail = public_item.get("contract", {}).get("name", "contract missing")
    else:
        provenance_ok = forge_manifest.is_file()
        provenance_detail = "aau-forge.json committed" if provenance_ok else "aau-forge.json missing"
        contract_ok = blueprint.is_file()
        contract_detail = "contract-blueprint.json committed" if contract_ok else "contract-blueprint.json missing"
        if provenance_ok:
            forge_doctor = diagnose_forged_lab(lab)

    review = entry["review"]
    review_complete = all(_nonempty(review.get(field)) for field in (
        "reviewer", "reviewer_role", "scope", "reviewed_at", "source_ledger"
    ))
    boundary_terms = ("human", "authority", "may never", "must not")
    human_boundary = any(term in readme.lower() for term in boundary_terms)
    catalog_ci = bool(catalog_item) and entry["lab_path"] in (
        root / ".github" / "workflows" / "ci.yml"
    ).read_text()

    manifest = _load_json(forge_manifest) if forge_manifest.is_file() else {}
    blueprint_data = _load_json(blueprint) if blueprint.is_file() else {}
    brief_path = lab / "evaluation-brief.json"
    brief = _load_json(brief_path) if brief_path.is_file() else {}
    pyproject_text = (lab / "pyproject.toml").read_text(errors="replace") if (lab / "pyproject.toml").is_file() else ""
    script_names = re.findall(r'^([a-z0-9-]+)\s*=\s*"[^\n]+:main"', pyproject_text, re.MULTILINE)
    contract_name = (
        (public_item or {}).get("contract", {}).get("name")
        or blueprint_data.get("contract")
        or manifest.get("generator", {}).get("contract")
        or brief.get("recommended_case", {}).get("contract")
        or "Unclassified contract"
    )
    contract_paths = {
        "Decision Gate": "DECISION_GATE_CONTRACT.md",
        "Rights Continuity": "RIGHTS_CONTINUITY_CONTRACT.md",
        "Critical Event Fan-Out": "CRITICAL_EVENT_FANOUT_CONTRACT.md",
    }
    title_match = re.search(r"^#\s+(.+)$", readme, re.MULTILINE)
    title = (public_item or {}).get("title") or (title_match.group(1).strip() if title_match else entry["id"].replace("-", " ").title())
    industry = (
        (public_item or {}).get("industry")
        or brief.get("workflow", {}).get("industry")
        or entry["lab_path"].split("/")[0].replace("-", " ").title()
    )
    cli = (public_item or {}).get("cli") or (script_names[0] if script_names else entry["lab_path"].split("/")[-1])

    checks = [
        _check_record("runnable package", required_package, "README, package, tests, and eval directory committed", "Generated"),
        _check_record("Forge provenance", provenance_ok, provenance_detail, "Generated"),
        _check_record("contract blueprint", contract_ok, contract_detail, "Generated"),
        _check_record("domain placeholders", not placeholders, "none remain" if not placeholders else f"remaining: {', '.join(placeholders[:4])}", "Domain reviewed"),
        _check_record("named review", review_complete, f"{review.get('reviewer') or 'no reviewer'} · {review.get('scope') or 'no scope'}", "Domain reviewed"),
        _check_record("primary-source ledger", source_links >= 2, f"{source_links} linked sources in {ledger_value or 'no ledger supplied'}", "Domain reviewed"),
        _check_record("scenario volume", scenarios >= 20, f"{scenarios}/20 committed scenarios", "Reproduced"),
        _check_record("zero-cost reproduction", result_evidence["mock_available"], "committed mock result", "Reproduced"),
        _check_record("real-model evidence", result_evidence["model_count"] >= 1, f"{result_evidence['model_count']} measured model(s)", "Reproduced"),
        _check_record("repeated runs", result_evidence["minimum_repeats"] >= 3, f"minimum n={result_evidence['minimum_repeats']}", "Reproduced"),
        _check_record("observed failures", failures >= 3, f"{failures}/3 scenario-linked failure modes", "Reproduced"),
        _check_record("independent model evidence", result_evidence["model_count"] >= 2, f"{result_evidence['model_count']}/2 model IDs", "Verified"),
        _check_record("protected authority", human_boundary, "human boundary stated in README" if human_boundary else "human boundary not found", "Verified"),
        _check_record("catalog + CI", catalog_ci, "public catalog and CI coverage", "Verified"),
    ]

    level = DRAFT_LEVEL
    for candidate in LEVELS:
        required = [check for check in checks if LEVEL_RANK[check["stage"]] <= LEVEL_RANK[candidate]]
        if required and all(check["passed"] for check in required):
            level = candidate
        else:
            break
    passed = sum(check["passed"] for check in checks)
    github = entry["contributor"]["github"].lstrip("@")
    return {
        "id": entry["id"],
        "origin": entry["origin"],
        "lab_path": entry["lab_path"],
        "title": title,
        "icon": (public_item or {}).get("icon", "🧪"),
        "industry": industry,
        "contract": {
            "name": contract_name,
            "path": (public_item or {}).get("contract", {}).get("path") or contract_paths.get(contract_name, "AAU_FORGE.md"),
        },
        "failure_patterns": (public_item or {}).get("failure_patterns", []),
        "summary": entry["summary"],
        "why_fork": entry["why_fork"],
        "tags": entry["tags"],
        "contributor": {
            **entry["contributor"],
            "profile_url": f"https://github.com/{github}",
        },
        "review": entry["review"],
        "trust": {
            "level": level,
            "score": {"passed": passed, "total": len(checks)},
            "checks": checks,
            "next_level": LEVELS[0] if level == DRAFT_LEVEL else (
                LEVELS[LEVEL_RANK[level] + 1] if level != LEVELS[-1] else None
            ),
        },
        "evidence": {
            **result_evidence,
            "scenario_count": scenarios,
            "observed_failure_modes": failures,
            "source_links": source_links,
        },
        "forge_doctor": forge_doctor,
        "commands": {
            "validate": f"aau gallery validate {entry['id']}",
            "run": cli + " eval --backend mock --repeats 3",
        },
    }


def build_gallery(root: Path) -> dict[str, Any]:
    evaluated = [evaluate_entry(root, entry) for _, entry in load_entries(root)]
    drafts = [item["id"] for item in evaluated if item["trust"]["level"] == DRAFT_LEVEL]
    if drafts:
        raise GalleryError(
            "committed Gallery entries must clear Generated; incomplete: " + ", ".join(drafts)
        )
    evaluated.sort(key=lambda item: (-LEVEL_RANK[item["trust"]["level"]], item["title"]))
    levels = {level: sum(item["trust"]["level"] == level for item in evaluated) for level in LEVELS}
    return {
        "version": GALLERY_VERSION,
        "trust_model": {
            "levels": list(LEVELS),
            "note": "Statuses are derived from committed evidence. Domain reviewed records review scope; it does not imply regulator or production approval.",
        },
        "stats": {
            "adaptations": len(evaluated),
            "contributors": len({item["contributor"]["github"].lower() for item in evaluated}),
            "contracts": len({item["contract"]["name"] for item in evaluated}),
            "levels": levels,
        },
        "entries": evaluated,
    }


def render_entry(item: dict[str, Any]) -> str:
    score = item["trust"]["score"]
    lines = [
        f"{item['icon']}  {item['title']}",
        f"Trust:       {item['trust']['level']} ({score['passed']}/{score['total']} checks)",
        f"Contract:    {item['contract']['name']}",
        f"Contributor: @{item['contributor']['github']}",
        f"Lab:         {item['lab_path']}",
        "",
    ]
    for check in item["trust"]["checks"]:
        lines.append(f"[{'PASS' if check['passed'] else 'NEXT'}] {check['check']}: {check['detail']}")
    if item["trust"]["next_level"]:
        lines.extend(["", f"Next evidence level: {item['trust']['next_level']}"])
    return "\n".join(lines)


def _resolve(entries: list[dict[str, Any]], target: str) -> dict[str, Any]:
    needle = target.strip().rstrip("/")
    matches = [item for item in entries if needle in {item["id"], item["lab_path"]}]
    if len(matches) != 1:
        raise GalleryError(f"gallery target must match one id or lab path: {target!r}")
    return matches[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aau-gallery",
        description="Inspect evidence-derived trust levels in the AAU Forge Gallery.",
    )
    parser.add_argument("command", nargs="?", choices=("list", "validate"), default="list")
    parser.add_argument("target", nargs="?", help="entry id or <industry>/<use-case>")
    parser.add_argument("--root", type=Path, help="repository checkout")
    parser.add_argument("--trust", choices=LEVELS, help="filter list by exact trust level")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)
    root = find_root(args.root) if args.root else find_root()
    try:
        gallery = build_gallery(root)
        entries = gallery["entries"]
        if args.command == "validate":
            if not args.target:
                raise GalleryError("validate requires an entry id or lab path")
            item = _resolve(entries, args.target)
            print(json.dumps(item, indent=2) if args.json else render_entry(item))
            return 0
        if args.trust:
            entries = [item for item in entries if item["trust"]["level"] == args.trust]
        if args.json:
            print(json.dumps({**gallery, "entries": entries}, indent=2))
        else:
            for index, item in enumerate(entries):
                if index:
                    print()
                score = item["trust"]["score"]
                print(f"{item['icon']} {item['title']} · {item['trust']['level']} · {score['passed']}/{score['total']}")
                print(f"   {item['industry']} · @{item['contributor']['github']} · {item['lab_path']}")
        return 0
    except (GalleryError, OSError) as exc:
        print(f"AAU Gallery stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
