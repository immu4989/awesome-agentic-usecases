"""Catch editorial defects that a dictionary-based spelling pass cannot detect."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DUPLICATE_WORD = re.compile(r"\b([A-Za-z]{3,})\s+\1\b", re.IGNORECASE)
FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`]*`")
HTML_TAG = re.compile(r"<[^>]+>")


def prose(text: str) -> str:
    text = FENCED_CODE.sub(lambda match: "\n" * match.group(0).count("\n"), text)
    text = INLINE_CODE.sub("", text)
    return HTML_TAG.sub("", text)


def main() -> None:
    problems = []
    for path in ROOT.rglob("*.md"):
        if any(part in {".git", ".venv", "results", "evals", "output", "tmp"} for part in path.parts):
            continue
        text = prose(path.read_text(errors="replace"))
        for match in DUPLICATE_WORD.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            problems.append(
                f"{path.relative_to(ROOT)}:{line}: repeated word {match.group(0)!r}"
            )
    if problems:
        raise SystemExit("editorial integrity failed:\n" + "\n".join(problems))
    print("editorial integrity OK")


if __name__ == "__main__":
    main()
