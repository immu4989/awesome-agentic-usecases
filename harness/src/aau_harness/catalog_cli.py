"""Repository navigator for finding, running, and adapting verified use cases.

The catalog deliberately stays stdlib-only. It is useful immediately after
``pip install aau-harness`` and never needs an API key or a network connection.
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

    initializing = sub.add_parser(
        "init",
        help="generate a five-minute Agent Evidence Starter",
    )
    initializing.add_argument("name", help="project directory name")
    initializing.add_argument("--output", type=Path, help="output directory; defaults to NAME")
    initializing.add_argument(
        "--template",
        choices=("public-service-routing", "customer-escalation", "incident-triage"),
        default="public-service-routing",
    )
    initializing.add_argument("--title")
    initializing.add_argument("--mission")
    initializing.add_argument("--adapter", choices=("command", "http"), default="command")
    initializing.add_argument("--human-role")
    initializing.add_argument("--protected-action")
    initializing.add_argument("--routine-outcome")
    initializing.add_argument("--human-outcome")
    initializing.add_argument("--stop-outcome")
    initializing.add_argument("--json", action="store_true")

    sub.add_parser(
        "submit",
        add_help=False,
        help="build or validate a privacy-bounded community evidence bundle",
    )

    sub.add_parser(
        "baseline",
        add_help=False,
        help="prepare and summarize a blinded human baseline",
    )

    forging = sub.add_parser("forge", help="turn a Studio brief into a runnable adaptation lab")
    forging.add_argument("brief", help="evaluation brief downloaded from AAU Studio")
    forging.add_argument("doctor_path", nargs="?", help="lab path when brief is 'doctor'")
    forging.add_argument("--name", help="new package and CLI name (required unless running doctor)")
    forging.add_argument("--title", help="human-readable lab title")
    forging.add_argument("--seed", type=int, help="override the brief-derived seed")
    forging.add_argument("--no-verify", action="store_true", help="skip install, tests, and mock run")
    forging.add_argument("--json", action="store_true", help="with 'doctor PATH', emit JSON")

    gallery = sub.add_parser("gallery", help="inspect community adaptations and evidence levels")
    gallery.add_argument("action", nargs="?", choices=("list", "validate"), default="list")
    gallery.add_argument("target", nargs="?", help="entry id or lab path to validate")
    gallery.add_argument(
        "--trust",
        choices=("Generated", "Domain reviewed", "Reproduced", "Verified"),
        help="filter the list by exact evidence level",
    )
    gallery.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    challenge = sub.add_parser("challenge", help="run and validate Reliability Challenge missions")
    challenge.add_argument("action", nargs="?", choices=("list", "show", "validate"), default="list")
    challenge.add_argument("target", nargs="?", help="challenge id/number, or Gallery id for validate")
    challenge.add_argument("--track", choices=("Reproduce", "Break", "Adapt"), help="filter the mission list")
    challenge.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    evaluating = sub.add_parser(
        "evaluate",
        help="evaluate an existing agent through a command or HTTP endpoint",
    )
    evaluating.add_argument("suite", help="AAU BYO-agent suite JSON")
    adapter = evaluating.add_mutually_exclusive_group(required=True)
    adapter.add_argument(
        "--command",
        dest="adapter_command",
        help="adapter argv; JSON stdin/stdout protocol",
    )
    adapter.add_argument("--endpoint", help="adapter HTTP endpoint")
    adapter.add_argument("--mock", action="store_true", help="protocol self-test")
    evaluating.add_argument("--timeout", type=float, default=30.0)
    evaluating.add_argument("--out", help="aggregate public receipt path")
    evaluating.add_argument("--private-out", help="unredacted local detail path")

    checking = sub.add_parser(
        "doctor",
        help="check an Agent Evidence Starter or the repository catalog",
    )
    checking.add_argument("path", nargs="?", type=Path, help="starter directory; defaults to cwd")
    checking.add_argument(
        "--run-adapter",
        action="store_true",
        help="execute the starter adapter during doctor (only for code you trust)",
    )
    checking.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args and raw_args[0] == "submit":
        from .submission import main as submission_main

        return submission_main(raw_args[1:])
    if raw_args and raw_args[0] == "baseline":
        from .human_baseline import main as baseline_main

        return baseline_main(raw_args[1:])
    args = build_parser().parse_args(raw_args)
    if args.command == "init":
        from .starter import main as starter_main

        starter_args = [args.name]
        if args.output:
            starter_args.extend(["--output", str(args.output)])
        starter_args.extend(["--template", args.template, "--adapter", args.adapter])
        if args.title:
            starter_args.extend(["--title", args.title])
        if args.mission:
            starter_args.extend(["--mission", args.mission])
        if args.human_role:
            starter_args.extend(["--human-role", args.human_role])
        if args.protected_action:
            starter_args.extend(["--protected-action", args.protected_action])
        if args.routine_outcome:
            starter_args.extend(["--routine-outcome", args.routine_outcome])
        if args.human_outcome:
            starter_args.extend(["--human-outcome", args.human_outcome])
        if args.stop_outcome:
            starter_args.extend(["--stop-outcome", args.stop_outcome])
        if args.json:
            starter_args.append("--json")
        return starter_main(starter_args)
    if args.command == "evaluate":
        from .evaluate import main as evaluate_main

        evaluate_args = [args.suite]
        if args.adapter_command:
            evaluate_args.extend(["--command", args.adapter_command])
        elif args.endpoint:
            evaluate_args.extend(["--endpoint", args.endpoint])
        else:
            evaluate_args.append("--mock")
        evaluate_args.extend(["--timeout", str(args.timeout)])
        if args.out:
            evaluate_args.extend(["--out", args.out])
        if args.private_out:
            evaluate_args.extend(["--private-out", args.private_out])
        return evaluate_main(evaluate_args)
    if args.command == "doctor":
        from .starter import doctor_project, render_report

        target = (args.path or Path.cwd()).resolve()
        if args.path is not None or (target / "aau-starter.json").is_file():
            report = doctor_project(target, run_adapter=args.run_adapter)
            print(json.dumps(report.to_dict(), indent=2) if args.json else render_report(report))
            return 0 if report.ready else 1
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
    if args.command == "forge":
        from .forge import main as forge_main

        if args.brief == "doctor":
            forge_args = ["doctor", args.doctor_path or "."]
            if args.json:
                forge_args.append("--json")
            return forge_main(forge_args)
        if not args.name:
            print("aau forge: --name is required when generating a lab", file=sys.stderr)
            return 2
        forge_args = [args.brief, "--name", args.name, "--root", str(root)]
        if args.title:
            forge_args.extend(["--title", args.title])
        if args.seed is not None:
            forge_args.extend(["--seed", str(args.seed)])
        if args.no_verify:
            forge_args.append("--no-verify")
        return forge_main(forge_args)
    if args.command == "gallery":
        from .gallery import main as gallery_main

        gallery_args = [args.action, "--root", str(root)]
        if args.target:
            gallery_args.append(args.target)
        if args.trust:
            gallery_args.extend(["--trust", args.trust])
        if args.json:
            gallery_args.append("--json")
        return gallery_main(gallery_args)
    if args.command == "challenge":
        from .challenge import main as challenge_main

        challenge_args = [args.action, "--root", str(root)]
        if args.target:
            challenge_args.append(args.target)
        if args.track:
            challenge_args.extend(["--track", args.track])
        if args.json:
            challenge_args.append("--json")
        return challenge_main(challenge_args)

    problems = doctor(root, cases)
    if args.json:
        print(
            json.dumps(
                {
                    "doctor_version": "aau-catalog-doctor/1.0",
                    "ready": not problems,
                    "case_count": len(cases),
                    "problems": problems,
                },
                indent=2,
            )
        )
        return 1 if problems else 0
    if problems:
        print("Catalog doctor found problems:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print(f"OK: {len(cases)} verified use cases are runnable, documented, and indexed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
