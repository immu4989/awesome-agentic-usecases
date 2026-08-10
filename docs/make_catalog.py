"""Generate the README use-case table from the public JSON catalog."""

from __future__ import annotations

import json
import re
from pathlib import Path

from make_hero import main as make_hero

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- USE_CASES:START -->"
END = "<!-- USE_CASES:END -->"
COUNT_COPY = re.compile(r"(Search and filter all )\d+( verified use cases)")


def table(cases: list[dict]) -> str:
    rows = [
        "| Use case | Industry | Capability | The question it answers |",
        "|---|---|---|---|",
    ]
    for item in cases:
        tags = " ".join(f"`{tag}`" for tag in item["capabilities"])
        rows.append(
            f"| [{item['icon']} {item['title']}]({item['path']}/) | "
            f"{item['industry']} | {tags} | {item['question']} |"
        )
    return "\n".join(rows)


def main() -> None:
    cases = json.loads((ROOT / "docs" / "use-cases.json").read_text())
    readme_path = ROOT / "README.md"
    readme = readme_path.read_text()
    readme, replacements = COUNT_COPY.subn(
        rf"\g<1>{len(cases)}\g<2>",
        readme,
    )
    if replacements != 1:
        raise ValueError("README must contain exactly one explorer use-case count")
    before, rest = readme.split(START, 1)
    _old, after = rest.split(END, 1)
    readme_path.write_text(f"{before}{START}\n\n{table(cases)}\n\n{END}{after}")
    make_hero()
    print(f"updated README with {len(cases)} catalog entries")


if __name__ == "__main__":
    main()
