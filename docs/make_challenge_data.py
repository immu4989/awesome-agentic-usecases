"""Publish the Reliability Challenge board from source missions and Gallery evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness" / "src"))

from aau_harness.challenge import build_challenge  # noqa: E402


def main() -> None:
    data = build_challenge(ROOT)
    (ROOT / "docs" / "challenge-data.json").write_text(json.dumps(data, indent=2) + "\n")
    stats = data["stats"]
    print(
        f"wrote challenge-data.json — {stats['live_challenges']} missions, "
        f"{stats['community_finishes']} community finishes, "
        f"{stats['reference_finishes']} reference finishes"
    )


if __name__ == "__main__":
    main()
