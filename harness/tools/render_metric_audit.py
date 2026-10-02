"""Generate a script-free public view of the committed metric audit."""

import argparse
import html
import json
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[2]
REPO = "https://github.com/immu4989/awesome-agentic-usecases/blob/main/"


def render(report: dict) -> str:
    esc = html.escape
    entries = []
    for row in report["files"]:
        path = row["path"]
        link = esc(REPO + quote(path, safe="/"), quote=True)
        differences = ""
        if row.get("mismatches"):
            items = []
            for mismatch in row["mismatches"]:
                items.append("<tr><th scope='row'>" + esc(str(mismatch.get("metric", "coverage"))) +
                             "<br><small>" + esc(mismatch["field"]) + "</small></th><td><code>" +
                             esc(json.dumps(mismatch["recorded"])) + "</code></td><td><code>" +
                             esc(json.dumps(mismatch["recomputed"])) + "</code></td></tr>")
            differences = ("<div class='scroll'><table><caption>Stored and current-harness summaries</caption>"
                           "<thead><tr><th>Metric</th><th>Recorded</th><th>Recomputed</th></tr></thead><tbody>" +
                           "".join(items) + "</tbody></table></div>")
        if row.get("error"):
            differences += "<p>Input could not be audited: " + esc(row["error"]) + "</p>"
        entries.append("<details><summary><span>" + esc(row["status"]) + "</span> " + esc(path) +
                       "</summary><p><a href='" + link + "'>Inspect original evaluation</a></p>" +
                       "<p class='digest'>Source file SHA-256: <code>" + esc(row["file_sha256"]) +
                       "</code></p>" + differences + "</details>")
    counts = report["counts"]
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Recorded evaluation audit · Awesome Agentic Use Cases</title>
<style>
:root{color-scheme:light dark;font-family:system-ui,sans-serif;line-height:1.6}body{margin:auto;max-width:72rem;padding:2rem 1rem;background:#f8f9fa;color:#17212b}a{color:#215579}h1{font-size:clamp(2rem,5vw,3.2rem);line-height:1.1}header{max-width:52rem}.stats{display:flex;flex-wrap:wrap;gap:1rem;margin:2rem 0}.stats p{padding:1rem 1.5rem;border:1px solid #bcc6cc;border-radius:.5rem;margin:0}.stats b{display:block;font-size:2rem}.notice{padding:1rem;border-left:4px solid #6d7780;background:#eef1f3}details{border-bottom:1px solid #bcc6cc;padding:1rem 0}summary{cursor:pointer;overflow-wrap:anywhere}summary span{font-weight:700;display:inline-block;min-width:7rem}.digest{overflow-wrap:anywhere;font-size:.85rem}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;text-align:left}th,td{padding:.7rem;border-bottom:1px solid #bcc6cc;vertical-align:top}caption{text-align:left;font-weight:600}small{font-weight:400}code{overflow-wrap:anywhere}footer{margin-top:3rem}a:focus-visible,summary:focus-visible{outline:3px solid #2779a8;outline-offset:4px}@media(prefers-color-scheme:dark){body{background:#171c22;color:#e6ebef}a{color:#9ecbe9}.notice{background:#222a33}}@media print{body{background:white;color:black}a{color:black}}
</style></head><body><header>
<a href="index.html">← Use-case explorer</a><h1>What the saved evidence supports.</h1>
<p>This audit recomputes recorded metric summaries without model calls. Historical observations remain unchanged.</p>
</header><section class="stats" aria-label="Audit coverage">""" + (
        f"<p><b>{report['file_count']}</b>evaluation files</p>"
        f"<p><b>{counts.get('consistent', 0)}</b>internally consistent</p>"
        f"<p><b>{counts.get('inconsistent', 0)}</b>summary differences</p>"
        f"<p><b>{counts.get('invalid', 0)}</b>invalid inputs</p></section>"
    ) + """<section class="notice" aria-label="Interpretation limits">
<h2>Consistency is not effectiveness.</h2><p>A consistent file can contain poor scores. A historical difference can reflect missing intervals or earlier scoring conventions; it is not proof of fabricated execution. Neither status authenticates observations or establishes production safety.</p>
<p>Comparison uses the current harness's scenario-bootstrap method and four-decimal precision. <code>null</code> denotes an absent or null summary value; inspect the original file to distinguish them.</p>
</section><h2>Inspect the files</h2><p>Open a row to inspect its source digest and any recorded/recomputed differences. Use your browser's Find command to locate a lab or metric.</p>
""" + "\n".join(entries) + "<footer><p>" + esc(report["boundary"]) + "</p><p><a href='" + REPO + "EVALUATION_METRIC_AUDIT.md'>Method and reproduction instructions</a> · <a href='" + REPO + "evaluation-metric-audit.json'>Machine-readable audit</a></p></footer></body></html>\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    page = render(json.loads((ROOT / "evaluation-metric-audit.json").read_text()))
    target = ROOT / "docs/evaluation-audit.html"
    if args.check:
        if not target.is_file() or target.read_text() != page:
            raise SystemExit("public audit page is stale; regenerate from the reviewed corpus audit")
    else:
        target.write_text(page)


if __name__ == "__main__":
    main()
