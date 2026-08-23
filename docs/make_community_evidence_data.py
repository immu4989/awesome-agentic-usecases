#!/usr/bin/env python3
"""Build the browser showcase from validated Community Evidence packs."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness" / "src"))

from aau_harness.submission import LEVELS, validate_pack  # noqa: E402


def build_data() -> dict:
    entries = []
    for pack in sorted((ROOT / "community-evidence" / "entries").iterdir()):
        if not pack.is_dir():
            continue
        report = validate_pack(pack)
        metadata = json.loads((pack / "submission.json").read_text())
        checks = json.loads((pack / "checks.json").read_text())
        suite = json.loads((pack / "suite.json").read_text())
        receipt = json.loads((pack / metadata["receipt_files"][-1]).read_text())
        relative = str(pack.relative_to(ROOT))
        entries.append(
            {
                "id": metadata["id"],
                "origin": metadata["origin"],
                "contributor": metadata["contributor"],
                "summary": metadata["summary"],
                "why_fork": metadata["why_fork"],
                "beneficiaries": metadata["beneficiaries"],
                "industry": metadata["industry"],
                "failure_shape": metadata["failure_shape"],
                "tags": metadata["tags"],
                "evidence": {
                    "level": report["level"],
                    "score": report["score"],
                    "receipt_count": report["receipt_count"],
                    "checks": checks["checks"],
                },
                "metrics": receipt["metrics"],
                "human_authority": suite["human_authority"],
                "pack_path": relative,
                "card_path": f"{relative}/assets/evidence-card.svg",
            }
        )
    stats = {
        "submissions": len(entries),
        "contributors": len({item["contributor"]["github"].lower() for item in entries}),
        "industries": len({item["industry"] for item in entries}),
        "receipts": sum(item["evidence"]["receipt_count"] for item in entries),
    }
    return {
        "schema_version": "aau-community-evidence-showcase/1.0",
        "stats": stats,
        "levels": list(LEVELS),
        "entries": entries,
        "boundary": "Artifact-derived evidence levels are not identity verification, certification, endorsement, production validation, or authority to deploy.",
    }


def launch_svg(data: dict) -> str:
    stats = data["stats"]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-labelledby="title desc">
  <title id="title">AAU community evidence loop</title>
  <desc id="desc">Connect an agent, earn artifact-derived evidence, and publish a reusable privacy-bounded pack.</desc>
  <defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#07131f"/><stop offset=".55" stop-color="#10263c"/><stop offset="1" stop-color="#2b1532"/></linearGradient><filter id="glow"><feGaussianBlur stdDeviation="7" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
  <rect width="1200" height="630" rx="40" fill="url(#bg)"/><path d="M155 342H1045" stroke="#31526e" stroke-width="4" stroke-dasharray="8 12"/>
  <g font-family="ui-monospace,SFMono-Regular,Menlo,monospace" fill="#eef8ff">
    <text x="70" y="72" fill="#58e1ba" font-size="17" letter-spacing="4">AAU / COMMUNITY EVIDENCE LOOP</text>
    <text x="70" y="137" font-size="38" font-weight="800">Your fork deserves a receipt.</text>
    <text x="70" y="177" fill="#a8bacb" font-size="19">Private-by-default intake · deterministic levels · reusable public proof</text>
    <g filter="url(#glow)"><circle cx="155" cy="342" r="62" fill="#113d47" stroke="#58e1ba" stroke-width="3"/><circle cx="452" cy="342" r="62" fill="#172f53" stroke="#73a8ff" stroke-width="3"/><circle cx="748" cy="342" r="62" fill="#3b2d18" stroke="#ffc96b" stroke-width="3"/><circle cx="1045" cy="342" r="62" fill="#361f42" stroke="#dc90ff" stroke-width="3"/></g>
    <g text-anchor="middle" font-size="15" font-weight="800"><text x="155" y="338">CONNECT</text><text x="155" y="360">AGENT</text><text x="452" y="338">REVIEW</text><text x="452" y="360">BOUNDARY</text><text x="748" y="338">REPEAT</text><text x="748" y="360">RUNS</text><text x="1045" y="338">PUBLISH</text><text x="1045" y="360">EVIDENCE</text></g>
    <text x="70" y="500" fill="#9fb4c9" font-size="14">LIVE REFERENCE PACKS</text><text x="70" y="548" font-size="34" font-weight="800">{stats['submissions']}</text>
    <text x="310" y="500" fill="#9fb4c9" font-size="14">PUBLIC RECEIPTS</text><text x="310" y="548" font-size="34" font-weight="800">{stats['receipts']}</text>
    <text x="570" y="500" fill="#9fb4c9" font-size="14">EVIDENCE LEVELS</text><text x="570" y="548" font-size="34" font-weight="800">4</text>
    <text x="825" y="500" fill="#ffc96b" font-size="14">UPLOADS OR ACCOUNTS</text><text x="825" y="548" font-size="34" font-weight="800">0</text>
    <text x="70" y="600" fill="#58e1ba" font-size="14">SHA-256 MANIFEST · AGGREGATE RECEIPTS · PROTECTED HUMAN AUTHORITY</text>
  </g>
</svg>'''


def main() -> None:
    data = build_data()
    (ROOT / "docs" / "community-evidence-data.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n"
    )
    (ROOT / "docs" / "assets" / "community-evidence-loop.svg").write_text(
        launch_svg(data)
    )
    print(
        f"wrote community evidence showcase — {data['stats']['submissions']} packs, "
        f"{data['stats']['receipts']} receipts"
    )


if __name__ == "__main__":
    main()
