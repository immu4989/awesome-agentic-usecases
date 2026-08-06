"""Repository navigator for finding, running, and adapting verified use cases.

The catalog deliberately stays stdlib-only. It is useful immediately after
``pip install -e harness`` and never needs an API key or a network connection.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]


def find_root(start: Path | None = None) -> Path:
    """Find a checkout by its public catalog, starting at cwd and then this package."""
    candidates = [Path(start or Path.cwd()).resolve(), Path(__file__).resolve()]
    for candidate in candidates:
        for parent in (candidate, *candidate.parents):
            if (parent / "docs" / "use-cases.json").is_file():
                return parent
    raise SystemExit(
        "Could not find docs/use-cases.json. Run this command inside an "
        "awesome-agentic-usecases checkout, or pass --root PATH."
    )


def load_catalog(root: Path) -> list[dict]:
    return json.loads((root / "docs" / "use-cases.json").read_text())


def matches(item: dict, query: str) -> bool:
    terms = query.lower().split()
    haystack = " ".join(
        [
            item["title"],
            item["path"],
            item["industry"],
            item["kind"],
            item["question"],
            *item["capabilities"],
        ]
    ).lower()
    return all(term in haystack for term in terms)


def filter_cases(
    cases: list[dict], query: str = "", industry: str = "", capability: str = ""
) -> list[dict]:
    out = cases
    if query:
        out = [item for item in out if matches(item, query)]
    if industry:
        needle = industry.lower()
        out = [item for item in out if needle in item["industry"].lower()]
    if capability:
        needle = capability.lower()
        out = [
            item
            for item in out
            if any(needle in tag.lower() for tag in item["capabilities"])
        ]
    return out


def resolve_case(cases: list[dict], name: str) -> dict:
    needle = name.lower().strip().rstrip("/")
    exact = [
        item
        for item in cases
        if needle
        in {
            item["title"].lower(),
            item["path"].lower(),
            item["path"].split("/")[-1].lower(),
            item["cli"].lower(),
            re.sub(r"[^a-z0-9]+", "-", item["title"].lower()).strip("-"),
        }
    ]
    if len(exact) == 1:
        return exact[0]
    fuzzy = [item for item in cases if matches(item, needle)]
    if len(fuzzy) == 1:
        return fuzzy[0]
    if not fuzzy:
        raise SystemExit(f"No use case matches {name!r}. Try: aau find {shlex.quote(name)}")
    choices = ", ".join(item["cli"] for item in fuzzy[:8])
    raise SystemExit(f"{name!r} matches several use cases: {choices}")


def project_index(root: Path) -> dict[str, Path]:
    projects: dict[str, Path] = {}
    for path in root.glob("*/*/pyproject.toml"):
        project = tomllib.loads(path.read_text()).get("project", {})
        if project.get("name"):
            projects[project["name"]] = path.parent
    return projects


def local_install_paths(root: Path, case: dict) -> list[Path]:
    """Return local dependencies before the selected package, in install order."""
    projects = project_index(root)
    selected = root / case["path"]
    ordered: list[Path] = []
    visiting: set[Path] = set()

    def visit(directory: Path) -> None:
        if directory in visiting:
            return
        visiting.add(directory)
        project = tomllib.loads((directory / "pyproject.toml").read_text()).get("project", {})
        for requirement in project.get("dependencies", []):
            package = requirement.split("[", 1)[0].split(" ", 1)[0]
            if package in projects:
                visit(projects[package])
        ordered.append(directory)

    visit(selected)
    return ordered


def install_command(root: Path, case: dict) -> str:
    paths = [root / "harness", *local_install_paths(root, case)]
    relative = [path.relative_to(root).as_posix() for path in paths]
    return "python -m pip install " + " ".join(f"-e {shlex.quote(path)}" for path in relative)


def render_list(cases: list[dict]) -> str:
    if not cases:
        return "No verified use cases matched. Try aau list to see everything."
    width = max(len(item["title"]) for item in cases)
    lines = []
    for item in cases:
        tags = " · ".join(item["capabilities"])
        lines.append(
            f"{item['icon']}  {item['title']:<{width}}  {item['industry']}\n"
            f"    {tags}  |  {item['cli']}"
        )
    return "\n".join(lines)


def render_show(root: Path, item: dict) -> str:
    tags = " · ".join(item["capabilities"])
    return "\n".join(
        [
            f"{item['icon']}  {item['title']}",
            f"Industry: {item['industry']}",
            f"Shape:    {item['kind']} | {tags}",
            "",
            item["question"],
            "",
            f"README:   {item['path']}/README.md",
            f"Failures: {item['path']}/FAILURE_MODES.md",
        ]
    )


def render_start(root: Path, item: dict) -> str:
    return "\n".join(
        [
            render_show(root, item),
            "",
            "Run the deterministic eval (no API key, no cost):",
            f"  {install_command(root, item)}",
            f"  {item['cli']} eval --backend mock",
            "",
            "Then open the README and replace --backend mock with a real provider.",
        ]
    )


def doctor(root: Path, cases: list[dict]) -> list[str]:
    problems: list[str] = []
    for item in cases:
        directory = root / item["path"]
        for name in ("README.md", "FAILURE_MODES.md", "pyproject.toml", "tests"):
            if not (directory / name).exists():
                problems.append(f"{item['path']}: missing {name}")
        pyproject = directory / "pyproject.toml"
        if pyproject.exists():
            scripts = tomllib.loads(pyproject.read_text()).get("project", {}).get("scripts", {})
            if item["cli"] not in scripts:
                problems.append(f"{item['path']}: CLI {item['cli']!r} is not declared")
    return problems


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aau", description="Find, run, and adapt verified agentic AI use cases."
    )
    parser.add_argument("--root", type=Path, help="repository checkout (normally auto-detected)")
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list", help="list verified use cases")
    listing.add_argument("--industry", default="", help="filter by industry")
    listing.add_argument("--capability", default="", help="filter by capability")
    listing.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    finding = sub.add_parser("find", help="search titles, questions, industries, and capabilities")
    finding.add_argument("query", nargs="+", help="search terms, e.g. security or 'act guardrails'")
    finding.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    showing = sub.add_parser("show", help="explain one use case")
    showing.add_argument("name", help="title, path, or CLI name")

    starting = sub.add_parser("start", help="print exact install and mock-eval commands")
    starting.add_argument("name", help="title, path, or CLI name")

    sub.add_parser("doctor", help="check that every catalog entry is runnable and documented")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = find_root(args.root) if args.root else find_root()
    cases = load_catalog(root)

    if args.command == "list":
        selected = filter_cases(cases, industry=args.industry, capability=args.capability)
        print(json.dumps(selected, indent=2) if args.json else render_list(selected))
        return 0
    if args.command == "find":
        selected = filter_cases(cases, query=" ".join(args.query))
        print(json.dumps(selected, indent=2) if args.json else render_list(selected))
        return 0 if selected else 1
    if args.command == "show":
        print(render_show(root, resolve_case(cases, args.name)))
        return 0
    if args.command == "start":
        print(render_start(root, resolve_case(cases, args.name)))
        return 0

    problems = doctor(root, cases)
    if problems:
        print("Catalog doctor found problems:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print(f"OK: {len(cases)} verified use cases are runnable, documented, and indexed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
