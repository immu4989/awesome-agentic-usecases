"""Fail CI when the interactive playground drifts from repository evidence."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    data = json.loads((ROOT / "docs" / "playground-data.json").read_text())
    cases = data["cases"]
    assert data["schema_version"] == "aau-playground/1.0"
    assert len(cases) == 5, "the starter playground must keep five focused cases"
    assert [item["order"] for item in cases] == list(range(1, 6)), "case order must be contiguous"
    assert len({item["id"] for item in cases}) == len(cases), "playground ids must be unique"
    assert len({item["industry"] for item in cases}) == 5, "starter cases must cover five industries"
    assert {item["verdict"] for item in cases} == {"trust", "verify", "block"}
    assert data["stats"]["cases"] == len(cases)
    assert data["stats"]["source_artifacts"] == len(cases) * 2

    for item in cases:
        provenance = item["provenance"]
        for key in ("scenario_path", "result_path"):
            assert (ROOT / provenance[key]).is_file(), f"{item['id']}: missing {key}"
        assert len(provenance["scenario_sha256"]) == 16
        assert len(provenance["result_sha256"]) == 16
        assert item["agent"]["backend"] != "mock", f"{item['id']}: real model evidence required"
        assert item["links"]["share"].endswith(f"?case={item['id']}#playground")
        assert item["links"]["challenge"].startswith(
            "https://github.com/immu4989/awesome-agentic-usecases/issues/"
        )
        if item["verdict"] == "trust":
            assert item["ground_truth"]["exact"] is True
            assert not item["scenario"]["evidence"]["missing"]
        elif item["verdict"] == "verify":
            assert item["scenario"]["evidence"]["missing"]
        else:
            assert item["ground_truth"]["exact"] is False

    serialized = json.dumps(data)
    assert "sk-live-" not in serialized, "synthetic secrets must be redacted from public data"

    html = (ROOT / "docs" / "index.html").read_text()
    css = (ROOT / "docs" / "playground.css").read_text()
    script = (ROOT / "docs" / "playground.js").read_text()
    for required in (
        'id="playground"',
        'id="playground-case-nav"',
        'id="playground-verdicts"',
        'id="playground-reveal"',
        'href="#playground"',
    ):
        assert required in html, f"landing page is missing {required}"
    assert "playground-data.json" in script
    assert "localStorage" in script, "progress must remain browser-local"
    assert 'params.get("case")' in script, "shareable case routes must resolve"
    assert "prefers-reduced-motion" in css, "playground must respect reduced motion"
    assert "@media (max-width: 640px)" in css, "playground needs a narrow-screen layout"
    for asset in ("social-card-playground.svg", "social-card-playground.png"):
        assert (ROOT / "docs" / "assets" / asset).is_file(), f"missing playground social asset: {asset}"
    assert "social-card-playground.png" in html, "playground social preview is not active"
    print("playground integrity OK: 5 real-model cases, local progress, stable share routes")


if __name__ == "__main__":
    main()
