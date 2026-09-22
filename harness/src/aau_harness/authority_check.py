"""One local staging evaluation with machine-readable and reviewer outputs."""

from pathlib import Path

from .agent_bom import AgentBomError, generate_conformance_suite, load_json, rendered, run_conformance, write_json
from .authority_html import render_html, write_report
from .authority_junit import export_junit, render_junit
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
    write_json(completion(report), out / "completion.json")
    return report


def completion(report: dict) -> dict:
    return {
        "version": "aau-authority-check/1.0", "status": report["status"],
        "case_count": report["case_count"], "exact_count": report["exact_count"],
        "receipt_sha256": report["receipt_sha256"],
        "boundary": "Local synthetic evaluation; not a signed pack or deployment approval. Retain the original adapter for verification.",
    }


def verify_check(directory: Path, adapter: Path, workspace: Path) -> dict:
    names = {"inventory.json", "suite.json", "receipt.json", "report.json",
             "review.html", "results.xml", "completion.json"}
    if directory.is_symlink() or not directory.is_dir():
        raise AgentBomError("check directory must be a real directory")
    if {p.name for p in directory.iterdir()} != names:
        raise AgentBomError("check directory file set is incomplete or unexpected")
    for name in names:
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
            raise AgentBomError(f"invalid check file: {name}")
    bom = load_json(directory / "inventory.json")
    suite = load_json(directory / "suite.json")
    receipt = load_json(directory / "receipt.json")
    if receipt.get("adapter_kind") != "command":
        raise AgentBomError("staging checks require command adapter evidence")
    report = explain_conformance(receipt, bom, suite, adapter, workspace)
    expected = {
        "report.json": report, "completion.json": completion(report),
    }
    for name, value in expected.items():
        if rendered(load_json(directory / name)) != rendered(value):
            raise AgentBomError(f"check output does not recompute: {name}")
    for name, payload in (("review.html", render_html(report).encode("utf-8")),
                          ("results.xml", render_junit(report, suite))):
        if (directory / name).read_bytes() != payload:
            raise AgentBomError(f"check output does not recompute: {name}")
    return report
