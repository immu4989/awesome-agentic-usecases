"""Offline, script-free presentation of verified authority report objects."""

from html import escape
from pathlib import Path

from .agent_bom import AgentBomError, write_json


STYLE = """
:root{color-scheme:light;font-family:system-ui,sans-serif;color:#182630;background:#f4f6f7}
body{max-width:1100px;margin:0 auto;padding:36px 24px;line-height:1.6}
h1,h2{line-height:1.2}h1{font-size:2rem}h2{margin-top:2rem}
.eyebrow{letter-spacing:.1em;text-transform:uppercase;font-size:.8rem;color:#455a64}
.notice{border-left:4px solid #536c79;padding:12px 18px;background:white}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;background:white}
caption{text-align:left;padding:12px 0;font-weight:600}
th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #ccd5db}
th{background:#e6ecef}code{overflow-wrap:anywhere}dt{font-weight:600;margin-top:12px}
dd{margin-left:0;overflow-wrap:anywhere}.muted{color:#455a64}
@media print{body{padding:0;background:white}table{font-size:10pt}.scroll{overflow:visible}}
"""


def _text(value) -> str:
    return escape(str(value), quote=True)


def _failure(row) -> str:
    if row is None:
        return "Exact match"
    missing = ", ".join(row["missing_reason_codes"]) or "None"
    unexpected = ", ".join(row["unexpected_reason_codes"]) or "None"
    return (f"<strong>{_text(row['category'])}</strong><br>"
            f"Expected: {_text(row['expected_decision'])}; observed: {_text(row['actual_decision'])}<br>"
            f"Missing reasons: {_text(missing)}<br>Unexpected reasons: {_text(unexpected)}")


def render_html(report: dict) -> str:
    """Render a report already constructed by the verified report functions."""
    comparison = report["report_version"] == "aau-authority-comparison/1.0"
    title = "Authority regression comparison" if comparison else "Authority failure report"
    digests = {"Inventory SHA-256": report["bom_sha256"], "Suite SHA-256": report["suite_sha256"]}
    if comparison:
        headers = ("Case", "Change", "Baseline", "Candidate")
        rows = [(f"<code>{_text(row['case_id'])}</code>", _text(row["change"]),
                 _failure(row["before"]), _failure(row["after"])) for row in report["transitions"]]
        summaries = [("Baseline", report["before"]), ("Candidate", report["after"])]
        counts = "; ".join(f"{name}: {count}" for name, count in report["counts"].items())
    else:
        headers = ("Case", "Failure shape", "Observed mismatch")
        rows = [(f"<code>{_text(row['case_id'])}</code>", _text(row["shape"]), _failure(row))
                for row in report["mismatches"]]
        summaries = [("Evaluation", report)]
        counts = "; ".join(f"{name}: {count}" for name, count in report["categories"].items())
    summary = ""
    for name, evidence in summaries:
        digests[f"{name} receipt SHA-256"] = evidence["receipt_sha256"]
        checked = "checked" if evidence["adapter_bytes_checked"] else "not checked"
        summary += (f"<li><strong>{name}</strong>: {_text(evidence['exact_count'])}/"
                    f"{_text(evidence['case_count'])} exact; {_text(evidence['status'])}; "
                    f"adapter: {_text(evidence['adapter_kind'])}; artifact bytes {checked}.</li>")
    table = "<tr>" + "".join(f'<th scope="col">{item}</th>' for item in headers) + "</tr>"
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    if not rows:
        body = f'<tr><td colspan="{len(headers)}">No mismatches in the recorded synthetic cases.</td></tr>'
    identities = "".join(f"<dt>{name}</dt><dd><code>{_text(value)}</code></dd>"
                         for name, value in digests.items())
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
            'style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
            f"<title>{title}</title><style>{STYLE}</style></head><body><main>"
            '<p class="eyebrow">Agent authority · offline evidence review</p>'
            f"<h1>{title}</h1><p class=\"notice\">{_text(report['boundary'])}</p>"
            f"<h2>Recorded results</h2><ul>{summary}</ul><p>{_text(counts)}</p>"
            '<p class="muted">Passing cases are omitted. This page is a presentation, not an independently '
            'verifiable receipt. Retain original evidence and use the CLI to verify it.</p>'
            f'<div class="scroll"><table><caption>Case-level findings</caption><thead>{table}</thead>'
            f"<tbody>{body}</tbody></table></div><h2>Evidence identity</h2><dl>{identities}</dl>"
            "</main></body></html>\n")


def write_report(report: dict, out: Path, format: str) -> None:
    if format == "json":
        write_json(report, out)
        return
    if format != "html":
        raise AgentBomError("unsupported report format")
    if out.exists() or out.is_symlink():
        raise AgentBomError(f"refusing to overwrite: {out}")
    payload = render_html(report)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as stream:
        stream.write(payload)
