"""Reproduce the public corpus metric audit; never rewrite original evaluation files."""

import argparse
import json
from collections import Counter
from pathlib import Path

from aau_harness.agent_bom import AgentBomError, digest, load_json
from aau_harness.eval_audit import audit_evaluation


ROOT = Path(__file__).resolve().parents[2]


def audit_repository(root: Path) -> dict:
    records = []
    for path in sorted(root.glob("*/*/results/eval_*.json")):
        if path.relative_to(root).parts[0] in {"output", "social-assets", "tmp"}:
            continue
        payload = path.read_bytes()
        row = {"path": path.relative_to(root).as_posix(), "file_sha256": digest(payload)}
        try:
            audit = audit_evaluation(load_json(path))
            row.update(status=audit["status"], mismatches=audit["mismatches"])
        except (AgentBomError, OSError) as exc:
            row.update(status="invalid", error=type(exc).__name__)
        records.append(row)
    if not records:
        raise ValueError("no public evaluation files found")
    counts = Counter(row["status"] for row in records)
    return {"report_version": "aau-repository-metric-audit/1.0", "file_count": len(records),
            "counts": dict(sorted(counts.items())), "files": records,
            "boundary": "Current-harness recomputation of stored metric summaries only, with four-decimal comparison. Historical observations are unchanged. Inconsistency may reflect missing intervals or earlier scoring/aggregation conventions; it is not evidence of fabricated execution or a new model run. Source bytes are bound for reproducibility, not provenance attestation."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="require the committed audit to match recomputation")
    args = parser.parse_args()
    report = audit_repository(ROOT)
    target = ROOT / "evaluation-metric-audit.json"
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not target.is_file() or target.read_text() != rendered:
            raise SystemExit("corpus audit differs: review source changes and regenerate explicitly")
    else:
        target.write_text(rendered)
    print(json.dumps(report["counts"], sort_keys=True))
    # Historical differences are explicitly recorded, not silently waived or repaired.


if __name__ == "__main__":
    main()
