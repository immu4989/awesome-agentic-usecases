"""JUnit presentation of verified synthetic authority evidence, without rerunning code."""

import json
from pathlib import Path
from xml.etree import ElementTree as ET

from .agent_bom import AgentBomError
from .authority_report import explain_conformance


def _xml_text(value: str) -> str:
    # XML 1.0 cannot represent all characters accepted by JSON. Preserve their
    # visible escaped spelling rather than emit a malformed CI report.
    return "".join(char if (char in "\t\n\r" or 0x20 <= ord(char) <= 0xD7FF
                            or 0xE000 <= ord(char) <= 0xFFFD
                            or 0x10000 <= ord(char) <= 0x10FFFF)
                   else f"\\u{ord(char):04x}" for char in value)


def render_junit(report: dict, suite: dict) -> bytes:
    failures = {row["case_id"]: row for row in report["mismatches"]}
    root = ET.Element("testsuites", tests=str(report["case_count"]),
                      failures=str(report["mismatch_count"]), errors="0", skipped="0")
    tests = ET.SubElement(root, "testsuite", name="AAU synthetic authority conformance",
                          tests=str(report["case_count"]), failures=str(report["mismatch_count"]),
                          errors="0", skipped="0")
    properties = ET.SubElement(tests, "properties")
    for name in ("receipt_sha256", "bom_sha256", "suite_sha256", "adapter_kind",
                 "adapter_bytes_checked", "boundary"):
        ET.SubElement(properties, "property", name=name, value=_xml_text(str(report[name])))
    for case in sorted(suite["cases"], key=lambda row: row["case_id"]):
        test = ET.SubElement(tests, "testcase", name=_xml_text(case["case_id"]),
                             classname="aau.authority." + _xml_text(case["shape"]))
        mismatch = failures.get(case["case_id"])
        if mismatch:
            failure = ET.SubElement(test, "failure", type=mismatch["category"],
                                    message=mismatch["category"])
            failure.text = json.dumps(mismatch, sort_keys=True, ensure_ascii=True)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def export_junit(receipt: dict, bom: dict, suite: dict, out: Path,
                 adapter_artifact: Path | None = None, workspace: Path | None = None) -> dict:
    report = explain_conformance(receipt, bom, suite, adapter_artifact, workspace)
    payload = render_junit(report, suite)
    if out.exists() or out.is_symlink():
        raise AgentBomError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("xb") as stream:
        stream.write(payload)
    return report
