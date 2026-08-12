"""Turn an AAU Studio evaluation brief into a runnable adaptation lab.

Forge deliberately separates *working evaluation infrastructure* from *domain truth*.
The generated package is executable and tested, but it remains clearly marked as an
unvalidated adaptation until a qualified owner replaces the generic rules and sources.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scaffold import build, slugify


class BriefError(ValueError):
    """Raised when a Studio brief cannot safely drive generation."""


def load_brief(path: str | Path) -> dict[str, Any]:
    brief_path = Path(path)
    try:
        brief = json.loads(brief_path.read_text())
    except FileNotFoundError as exc:
        raise BriefError(f"evaluation brief not found: {brief_path}") from exc
    except json.JSONDecodeError as exc:
        raise BriefError(f"evaluation brief is not valid JSON: {exc}") from exc
    validate_brief(brief)
    return brief


def validate_brief(brief: Any) -> None:
    if not isinstance(brief, dict):
        raise BriefError("evaluation brief must be a JSON object")
    if brief.get("contract_version") != "aau-studio/1.0":
        raise BriefError("unsupported contract_version; expected 'aau-studio/1.0'")

    workflow = brief.get("workflow")
    recommended = brief.get("recommended_case")
    plan = brief.get("verification_plan")
    if not isinstance(workflow, dict):
        raise BriefError("workflow must be an object")
    if not isinstance(recommended, dict):
        raise BriefError("recommended_case must be an object")
    if not isinstance(plan, dict):
        raise BriefError("verification_plan must be an object")

    for field in ("description", "industry", "agent_shape"):
        if not isinstance(workflow.get(field), str) or not workflow[field].strip():
            raise BriefError(f"workflow.{field} must be a non-empty string")
    risks = workflow.get("risks")
    if not isinstance(risks, list) or any(not isinstance(item, str) for item in risks):
        raise BriefError("workflow.risks must be an array of strings")

    for field in ("path", "title", "cli", "contract"):
        if not isinstance(recommended.get(field), str) or not recommended[field].strip():
            raise BriefError(f"recommended_case.{field} must be a non-empty string")
    parts = recommended["path"].split("/")
    if len(parts) != 2 or any(slugify(part) != part for part in parts):
        raise BriefError("recommended_case.path must be a two-part repository path")

    minimum_scenarios = plan.get("minimum_scenarios")
    minimum_repeats = plan.get("minimum_repeats")
    proofs = plan.get("required_proofs")
    if not isinstance(minimum_scenarios, int) or minimum_scenarios < 20:
        raise BriefError("verification_plan.minimum_scenarios must be an integer of at least 20")
    if not isinstance(minimum_repeats, int) or minimum_repeats < 3:
        raise BriefError("verification_plan.minimum_repeats must be an integer of at least 3")
    if not isinstance(proofs, list) or len(proofs) < 4 or any(
        not isinstance(item, str) or not item.strip() for item in proofs
    ):
        raise BriefError("verification_plan.required_proofs must contain at least four strings")


def deterministic_seed(brief: dict[str, Any]) -> int:
    # A download timestamp must not make the same workflow generate a different world.
    stable = {
        key: brief[key]
        for key in (
            "contract_version",
            "workflow",
            "recommended_case",
            "verification_plan",
        )
    }
    canonical = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
    return 1000 + int(hashlib.sha256(canonical).hexdigest()[:8], 16) % 8999


def _git_commit(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _safe_markdown(value: str) -> str:
    return html.escape(" ".join(value.split())).replace("|", "&#124;")


def _origin_section(brief: dict[str, Any], seed: int) -> str:
    workflow = brief["workflow"]
    source = brief["recommended_case"]
    risks = workflow["risks"]
    risk_copy = "; ".join(risks) if risks else "Not selected in Studio"
    return f"""
> [!CAUTION]
> **Runnable does not mean domain-validated.** Forge generated a working synthetic lab,
> not an approved policy or production system. A qualified domain owner must replace and
> review every `TODO(domain)` rule, source, authority boundary, and consequence before any
> real-world claim is made.

## Forge origin

| Studio input | Value |
|---|---|
| Workflow | {_safe_markdown(workflow['description'])} |
| Industry | {_safe_markdown(workflow['industry'])} |
| Agent shape | {_safe_markdown(workflow['agent_shape'])} |
| Consequences | {_safe_markdown(risk_copy)} |
| Closest verified lab | [{_safe_markdown(source['title'])}](../../{source['path']}/) |
| Reusable contract | {_safe_markdown(source['contract'])} |
| Deterministic seed | `{seed}` |

The complete machine-readable handoff is committed as
[`evaluation-brief.json`](evaluation-brief.json). Work through
[`ADAPTATION_CHECKLIST.md`](ADAPTATION_CHECKLIST.md) before requesting review.
"""


def _adaptation_checklist(brief: dict[str, Any]) -> str:
    source = brief["recommended_case"]
    proofs = "\n".join(f"- [ ] {item}" for item in brief["verification_plan"]["required_proofs"])
    return f"""# Forge Adaptation Checklist

This lab inherits evaluation structure from
[`{source['path']}`](../../{source['path']}/), not its domain rules or production validity.

## 1. Domain truth

- [ ] Name the accountable policy owner and domain reviewer.
- [ ] Replace every `TODO(domain)` in the generated package.
- [ ] Cite dated primary sources for each deciding rule and threshold.
- [ ] Define effective dates, jurisdictions, exclusions, and conflict handling.
- [ ] Record the protected human decision or action the agent may never claim.

## 2. Measurement

{proofs}
- [ ] Add a clean twin where the risky capability is legitimately required.
- [ ] Add a deceptive or transfer case whose answer cannot be inferred from wording.
- [ ] Regenerate scenarios byte-for-byte from the committed seed.

## 3. Evidence

- [ ] Run at least two real models with at least three repeats.
- [ ] Commit JSON and rendered Markdown results with provenance, cost, and latency.
- [ ] Replace all placeholder failure modes with observed, scenario-linked failures.
- [ ] Ask the domain reviewer to sign off on rules—not model performance.

## 4. Publication gate

- [ ] Remove the README caution only after the domain review is documented.
- [ ] Add the package to the catalog and main CI matrix.
- [ ] Generate the standard visual case file and verify accessible alt text.
- [ ] State synthetic-world limitations prominently.
"""


def _workflow_yaml(title: str, rel: str, cli: str, seed: int, scenarios: int, repeats: int) -> str:
    quoted_title = json.dumps(title)
    return f"""name: {quoted_title}

on:
  push:
    paths:
      - {json.dumps(rel + '/**')}
      - "harness/**"
      - {json.dumps('.github/workflows/forge-' + cli + '.yml')}
  pull_request:
    paths:
      - {json.dumps(rel + '/**')}
      - "harness/**"

jobs:
  verify-forged-lab:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - name: Install Forge lab
        run: python -m pip install -e harness[dev] -e {rel}[dev]
      - name: Regenerate committed scenarios
        run: |
          {cli} generate --n {scenarios} --seed {seed}
          git diff --exit-code {rel}/evals/scenarios.jsonl
      - name: Run exact tests and zero-cost evaluation
        run: |
          pytest harness/tests {rel}/tests -q
          {cli} eval --backend mock --repeats {repeats}
      - name: Lint Forge lab
        run: ruff check harness {rel}
"""


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def _run_verification(
    source_root: Path, dest: Path, cli: str, seed: int, scenarios: int, repeats: int
) -> tuple[bool, list[dict[str, Any]]]:
    package = cli.replace("-", "_")
    environment = os.environ.copy()
    python_paths = [str(source_root / "harness" / "src"), str(dest / "src")]
    if environment.get("PYTHONPATH"):
        python_paths.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(python_paths)
    steps = [
        (
            "import",
            [
                sys.executable,
                "-c",
                f"import aau_harness; import {package}",
            ],
        ),
        (
            "generate",
            [
                sys.executable,
                "-m",
                f"{package}.cli",
                "generate",
                "--n",
                str(scenarios),
                "--seed",
                str(seed),
            ],
        ),
        ("tests", [sys.executable, "-m", "pytest", str(dest / "tests"), "-q"]),
        (
            "mock_eval",
            [
                sys.executable,
                "-m",
                f"{package}.cli",
                "eval",
                "--backend",
                "mock",
                "--repeats",
                str(repeats),
            ],
        ),
    ]
    records: list[dict[str, Any]] = []
    for label, command in steps:
        result = subprocess.run(
            command, capture_output=True, text=True, check=False, env=environment
        )
        records.append({"step": label, "status": "passed" if result.returncode == 0 else "failed"})
        if result.returncode != 0:
            print(f"  {label}: FAILED\n{result.stdout[-1500:]}{result.stderr[-1500:]}")
            return False, records
        print(f"  {label}: ok")
    return True, records


def forge(
    brief_path: str | Path,
    name: str,
    output_root: str | Path,
    source_root: str | Path,
    *,
    seed: int | None = None,
    title: str | None = None,
    verify: bool = True,
) -> Path:
    brief = load_brief(brief_path)
    output_root = Path(output_root).resolve()
    source_root = Path(source_root).resolve()
    source = brief["recommended_case"]
    source_dir = source_root / source["path"]
    if not source_dir.is_dir() or not (source_dir / "pyproject.toml").is_file():
        raise BriefError(
            f"closest verified lab is unavailable: {source['path']}; run Forge from a repository fork"
        )
    if not (source_root / "harness").is_dir():
        raise BriefError("source repository does not contain the AAU harness")

    resolved_seed = seed if seed is not None else deterministic_seed(brief)
    if resolved_seed < 0:
        raise BriefError("seed must be zero or greater")
    slug = slugify(name)
    if not slug:
        raise BriefError("name must contain at least one letter or number")
    industry = brief["workflow"]["industry"]
    if industry == "unspecified":
        industry = source["path"].split("/")[0]
    nice_title = title or slug.replace("-", " ").title()
    rel = f"{slugify(industry)}/{slug}"
    workflow_path = output_root / ".github" / "workflows" / f"forge-{slug}.yml"
    dest_candidate = output_root / slugify(industry) / slug
    if dest_candidate.exists():
        raise BriefError(f"refusing to overwrite existing {dest_candidate}")
    if workflow_path.exists():
        raise BriefError(f"refusing to overwrite existing {workflow_path}")

    dest = Path(build(industry, slug, resolved_seed, str(output_root), nice_title))
    readme = dest / "README.md"
    body = readme.read_text()
    marker = f"# {nice_title}\n"
    readme.write_text(body.replace(marker, marker + _origin_section(brief, resolved_seed), 1))
    (dest / "ADAPTATION_CHECKLIST.md").write_text(_adaptation_checklist(brief))
    shutil.copyfile(brief_path, dest / "evaluation-brief.json")
    schema = source_root / "docs" / "studio-spec.schema.json"
    if schema.is_file():
        shutil.copyfile(schema, dest / "evaluation-brief.schema.json")

    scenarios = brief["verification_plan"]["minimum_scenarios"]
    repeats = brief["verification_plan"]["minimum_repeats"]
    manifest = {
        "forge_version": "aau-forge/1.0",
        "status": "adaptation_required",
        "forged_at": datetime.now(timezone.utc).isoformat(),
        "generated_path": rel,
        "seed": resolved_seed,
        "source": {
            "repository": "immu4989/awesome-agentic-usecases",
            "commit": _git_commit(source_root),
            "case": source,
        },
        "workflow": brief["workflow"],
        "verification": {
            "status": "pending" if verify else "not_run",
            "minimum_scenarios": scenarios,
            "minimum_repeats": repeats,
            "steps": [],
        },
    }
    manifest_path = dest / "aau-forge.json"
    _write_json(manifest_path, manifest)
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(
        _workflow_yaml(
            f"AAU Forge · {nice_title}", rel, slug, resolved_seed, scenarios, repeats
        )
    )

    if verify:
        print("\nverifying the forged lab before handoff...")
        passed, records = _run_verification(
            source_root, dest, slug, resolved_seed, scenarios, repeats
        )
        manifest["verification"]["status"] = "passed" if passed else "failed"
        manifest["verification"]["steps"] = records
        _write_json(manifest_path, manifest)
        if not passed:
            raise BriefError("forged lab failed verification; generated files were retained for inspection")

    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aau-forge",
        description="Turn an AAU Studio evaluation brief into a runnable adaptation lab.",
    )
    parser.add_argument("brief", help="evaluation brief downloaded from AAU Studio")
    parser.add_argument("--name", required=True, help="new package and CLI name")
    parser.add_argument("--title", help="human-readable lab title")
    parser.add_argument("--seed", type=int, help="override the deterministic brief-derived seed")
    parser.add_argument("--root", default=".", help="output repository root")
    parser.add_argument(
        "--source-root",
        help="AAU repository root containing the closest lab (defaults to --root)",
    )
    parser.add_argument("--no-verify", action="store_true", help="skip install, tests, and mock run")
    args = parser.parse_args(argv)
    try:
        dest = forge(
            args.brief,
            args.name,
            args.root,
            args.source_root or args.root,
            seed=args.seed,
            title=args.title,
            verify=not args.no_verify,
        )
    except (BriefError, OSError) as exc:
        print(f"AAU Forge stopped: {exc}", file=sys.stderr)
        return 2
    print(f"\nforged {os.path.relpath(dest, Path(args.root).resolve())}")
    print("next: replace TODO(domain), complete ADAPTATION_CHECKLIST.md, then open a pull request")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
