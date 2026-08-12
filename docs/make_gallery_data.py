"""Build the browser-ready Community Forge Gallery from evidence-derived entries."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness" / "src"))

from aau_harness.gallery import build_gallery  # noqa: E402


def main() -> None:
    gallery = build_gallery(ROOT)
    output = ROOT / "docs" / "gallery-data.json"
    output.write_text(json.dumps(gallery, indent=2) + "\n")
    stats = gallery["stats"]
    print(
        f"wrote gallery-data.json — {stats['adaptations']} adaptations, "
        f"{stats['contributors']} contributors, {stats['contracts']} contracts"
    )


if __name__ == "__main__":
    main()
