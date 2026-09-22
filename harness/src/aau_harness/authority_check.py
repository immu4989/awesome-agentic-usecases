"""One local staging evaluation with machine-readable and reviewer outputs."""

from pathlib import Path

from .agent_bom import AgentBomError, generate_conformance_suite, run_conformance, write_json
from .authority_html import write_report
from .authority_junit import export_junit
from .authority_report import explain_conformance


def check_authority(bom: dict, command: str, adapter: Path, workspace: Path,
                    out: Path, timeout: float = 10.0) -> dict:
    # Reject an occupied destination before running any user-supplied code.
    if out.exists() or out.is_symlink():
        raise AgentBomError(f"refusing to overwrite: {out}")
    suite = generate_conformance_suite(bom)
    receipt = run_conformance(bom, suite, "command", command, timeout, adapter, workspace)
    report = explain_conformance(receipt, bom, suite, adapter, workspace)
    out.mkdir(parents=True, exist_ok=False)
    write_json(bom, out / "inventory.json")
    write_json(suite, out / "suite.json")
    write_json(receipt, out / "receipt.json")
    write_report(report, out / "report.json", "json")
    write_report(report, out / "review.html", "html")
    export_junit(receipt, bom, suite, out / "results.xml", adapter, workspace)
    # Written last: absence means the multi-file output did not finish.
    write_json({
        "version": "aau-authority-check/1.0", "status": report["status"],
        "case_count": report["case_count"], "exact_count": report["exact_count"],
        "receipt_sha256": report["receipt_sha256"],
        "boundary": "Local synthetic evaluation; not a signed pack or deployment approval. Retain the original adapter for verification.",
    }, out / "completion.json")
    return report
