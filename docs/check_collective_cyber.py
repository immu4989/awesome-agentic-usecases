"""Fail CI when the Collective Cyber Defense public contract drifts."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def main() -> None:
    data = json.loads((DOCS / "collective-cyber-defense-data.json").read_text())
    assert data["data_version"] == "aau-collective-cyber-defense-site/0.1"
    assert len(data["fixes"]) == 3
    assert data["containment"]["event_count"] == 21
    assert data["containment"]["containment_breach_count"] == 0
    assert data["benchmark"]["summary"]["task_count"] == 20
    assert len(data["benchmark"]["families"]) == 5
    assert data["defender"]["decision_count"] == 3
    assert data["mesh"]["record_count"] == 6
    assert data["outcomes"]["summary"]["independent_reproduction_count"] == 0
    assert data["outcomes"]["claim_boundary"]["no_field_effectiveness_claim"] is True
    assert all(data["boundary"].values())
    index = json.loads((ROOT / "cyber-defense-evidence-mesh/examples/reference-mesh.json").read_text())
    assert len(index["artifacts"]) == 6
    html = (DOCS / "index.html").read_text()
    for marker in ("collective-cyber-defense", "ccd-defender-file", "ccd-outcome-gaps"):
        assert marker in html
    for path in (DOCS / "collective-cyber-defense.js", DOCS / "collective-cyber-defense.css", DOCS / "assets/collective-cyber-defense.svg"):
        assert path.is_file() and path.stat().st_size > 200
    print("Collective Cyber Defense data, boundaries, and site bindings are current.")


if __name__ == "__main__":
    main()
