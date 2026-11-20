"""Shared script-free table presentation for recorded-evidence reviewers."""

from html import escape

from .authority_html import STYLE as BASE_STYLE


STYLE = BASE_STYLE + """
body{overflow-wrap:anywhere}main,section{min-width:0}
.scroll{max-width:100%;margin:1rem 0;scroll-behavior:auto}
.scroll:focus-visible,a:focus-visible,summary:focus-visible,[tabindex="-1"]:focus-visible{outline:3px solid #355c70;outline-offset:3px}
th,td{min-width:10ch}thead th{overflow-wrap:normal}caption{max-width:min(100%,calc(100vw - 96px))}
tbody th{background:#f8fafb;font-weight:600;white-space:pre-line;overflow-wrap:anywhere}
nav.report-nav{display:flex;flex-wrap:wrap;gap:.5rem 1.2rem;margin:1rem 0;padding:1rem;background:white;border:1px solid #ccd5db}
nav.report-nav a{padding:.25rem 0}
@media(forced-colors:active){.scroll:focus-visible,a:focus-visible,summary:focus-visible,[tabindex="-1"]:focus-visible{outline-color:Highlight}}
@media print{nav.report-nav{display:none}.scroll{overflow:visible;max-width:none}table{min-width:0!important}}
"""


def table(caption, headers, rows, *, compact_numbers=False, missing_text='None'):
    """Escape every supplied value; label scroll groups without creating dozens of landmarks."""
    def text(value):
        if value is None:
            value = missing_text
        elif compact_numbers and type(value) is float:
            value = format(value, '.6g')
        return escape(str(value), quote=True)

    heading = ''.join(f'<th scope="col">{text(value)}</th>' for value in headers)
    body = []
    for row in rows:
        cells = ''.join((f'<th scope="row">{text(value)}</th>' if index == 0 else f'<td>{text(value)}</td>')
                        for index, value in enumerate(row))
        body.append(f'<tr>{cells}</tr>')
    if not body:
        body.append(f'<tr><td colspan="{len(headers)}">None recorded.</td></tr>')
    return (f'<div class="scroll" tabindex="0" role="group" aria-label="Scrollable table: {text(caption)}">'
            f'<table><caption>{text(caption)}</caption><thead><tr>{heading}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')
