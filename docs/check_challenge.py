"""Fail CI when the Challenge catalog, scoreboard, or contribution route drifts."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness" / "src"))

from aau_harness.challenge import CHALLENGE_VERSION, TRACKS, build_challenge  # noqa: E402


def main() -> None:
    built = build_challenge(ROOT)
    published = json.loads((ROOT / "docs" / "challenge-data.json").read_text())
    assert built == published, "docs/challenge-data.json is stale; run docs/make_challenge_data.py"
    assert built["version"] == CHALLENGE_VERSION
    assert {item["id"] for item in built["tracks"]} == set(TRACKS)
    assert built["stats"]["live_challenges"] >= 5
    assert built["stats"]["achievements"] >= 6
    assert built["stats"]["reference_finishes"] >= 3
    assert all((ROOT / item["starter_lab"]).is_dir() for item in built["challenges"])

    html = (ROOT / "docs" / "index.html").read_text()
    script = (ROOT / "docs" / "explorer.js").read_text()
    for element_id in ("challenge", "challenge-grid", "challenge-track", "challenge-scoreboard", "challenge-builder"):
        assert f'id="{element_id}"' in html, f"Challenge is missing #{element_id}"
    for behavior in ("loadChallenge", "renderChallenges", "renderChallengeScoreboard", "downloadChallengeSubmission"):
        assert behavior in script, f"Challenge script is missing {behavior}"
    assert "challenge-data.json" in script
    assert "Bring the receipt" in html
    assert "social-card-playground.png" in html
    assert (ROOT / "docs" / "assets" / "social-card-challenge.png").is_file()
    assert (ROOT / ".github" / "PULL_REQUEST_TEMPLATE" / "reliability-challenge.md").is_file()
    assert (ROOT / "challenge" / "challenge-entry.schema.json").is_file()
    assert (ROOT / "challenge" / "challenge-entry.example.json").is_file()
    assert "aau-challenge = \"aau_harness.challenge:main\"" in (ROOT / "harness" / "pyproject.toml").read_text()
    print(
        f"Challenge integrity OK: {built['stats']['live_challenges']} missions, "
        f"{built['stats']['community_finishes']} community finishes"
    )


if __name__ == "__main__":
    main()
