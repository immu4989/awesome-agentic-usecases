"""Fail CI when a local Markdown or explorer link points to a missing target."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HTML_LINK = re.compile(r'<(?:a|img)\b[^>]+(?:href|src)=["\']([^"\']+)', re.IGNORECASE)
REMOTE_SCHEMES = ("http://", "https://", "mailto:", "data:", "javascript:")


def local_target(source: Path, raw: str) -> Path | None:
    ref = raw.strip().split()[0].strip("<>")
    if not ref or ref.startswith(("#", *REMOTE_SCHEMES)):
        return None
    target = unquote(ref.split("#", 1)[0].split("?", 1)[0])
    return source.parent / target if target else None


def markdown_problems() -> list[str]:
    problems = []
    for path in ROOT.rglob("*.md"):
        if any(part in {".git", ".venv"} for part in path.parts):
            continue
        text = path.read_text(errors="replace")
        matches = [*MARKDOWN_LINK.finditer(text), *HTML_LINK.finditer(text)]
        for match in matches:
            target = local_target(path, match.group(1))
            if target is not None and not target.exists():
                line = text.count("\n", 0, match.start()) + 1
                problems.append(f"{path.relative_to(ROOT)}:{line}: missing {match.group(1)!r}")
    return problems


class ExplorerParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.refs: list[tuple[int, str]] = []

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(attributes["id"] or "")
        for key in ("href", "src"):
            if attributes.get(key):
                self.refs.append((self.getpos()[0], attributes[key] or ""))


def explorer_problems() -> list[str]:
    path = ROOT / "docs" / "index.html"
    parser = ExplorerParser()
    parser.feed(path.read_text())
    problems = []
    for line, ref in parser.refs:
        if ref.startswith("#") and ref[1:] not in parser.ids:
            problems.append(f"docs/index.html:{line}: missing anchor {ref!r}")
            continue
        target = local_target(path, ref)
        if target is not None and not target.exists():
            problems.append(f"docs/index.html:{line}: missing {ref!r}")
    return problems


def main() -> None:
    problems = markdown_problems() + explorer_problems()
    if problems:
        raise SystemExit("broken local links:\n" + "\n".join(problems))
    print("local link integrity OK")


if __name__ == "__main__":
    main()
