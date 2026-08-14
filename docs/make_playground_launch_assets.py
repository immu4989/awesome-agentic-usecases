#!/usr/bin/env python3
"""Generate deterministic campaign SVGs and optional PNG/GIF launch assets."""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_PATH = ROOT / "playground" / "campaign.json"
PLAYGROUND_PATH = ROOT / "docs" / "playground-data.json"
ASSET_DIR = ROOT / "docs" / "assets" / "playground-launch"
GIF_PATH = ROOT / "docs" / "assets" / "playground-review-walkthrough.gif"
LIVE_URL = "https://immu4989.github.io/awesome-agentic-usecases/"
ACCENTS = ["#65e7ff", "#ffc857", "#ff6e7f", "#b9a6ff", "#9df8bd"]


def load_inputs() -> tuple[dict, dict]:
    campaign = json.loads(CAMPAIGN_PATH.read_text(encoding="utf-8"))
    playground = json.loads(PLAYGROUND_PATH.read_text(encoding="utf-8"))
    source_ids = [item["id"] for item in playground["cases"]]
    campaign_ids = [item["id"] for item in campaign["cases"]]
    if campaign_ids != source_ids:
        raise SystemExit("campaign case order must exactly match playground-data.json")
    if len(f'{campaign["main_x"]} {campaign["launch_url"]}') > 280:
        raise SystemExit("main X launch copy exceeds 280 raw characters")
    for item in campaign["cases"]:
        url = f'{LIVE_URL}?case={item["id"]}#playground'
        if len(f'{item["hook"]} {url}') > 280:
            raise SystemExit(f'X copy exceeds 280 raw characters: {item["id"]}')
    return campaign, playground


def svg_lines(text: str, width: int, max_lines: int) -> list[str]:
    lines = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .") + "…"
    return lines


def make_svg(item: dict, source: dict, index: int) -> str:
    accent = ACCENTS[index]
    headline = svg_lines(item["headline"], 26, 3)
    hook = svg_lines(item["hook"].rsplit(":", 1)[0], 60, 3)
    headline_spans = "".join(
        f'<tspan x="104" dy="{0 if line_index == 0 else 68}">{escape(line)}</tspan>'
        for line_index, line in enumerate(headline)
    )
    hook_spans = "".join(
        f'<tspan x="104" dy="{0 if line_index == 0 else 29}">{escape(line)}</tspan>'
        for line_index, line in enumerate(hook)
    )
    number = str(index + 1).zfill(2)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-labelledby="title desc">
  <title id="title">{escape(item["headline"])}</title>
  <desc id="desc">Campaign card for the {escape(source["industry"])} evidence-review case.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#061216"/><stop offset=".62" stop-color="#0a1b20"/><stop offset="1" stop-color="#071114"/></linearGradient>
    <pattern id="grid" width="44" height="44" patternUnits="userSpaceOnUse"><path d="M44 0H0V44" fill="none" stroke="{accent}" stroke-opacity=".07"/></pattern>
    <radialGradient id="glow"><stop stop-color="{accent}" stop-opacity=".18"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/><rect width="1200" height="630" fill="url(#grid)"/><circle cx="1040" cy="78" r="340" fill="url(#glow)"/>
  <rect x="34" y="34" width="1132" height="562" fill="none" stroke="{accent}" stroke-width="2"/>
  <path d="M34 116H1166M840 116V596" stroke="#29434a"/>
  <text x="70" y="83" fill="{accent}" font-family="ui-monospace,monospace" font-size="18" font-weight="800" letter-spacing="2">CAN YOU TRUST THIS AGENT? / CASE {number}</text>
  <text x="1130" y="83" fill="#91abb1" font-family="ui-monospace,monospace" font-size="14" font-weight="700" text-anchor="end">TRUST · VERIFY · BLOCK</text>
  <text x="104" y="166" fill="{accent}" font-family="ui-monospace,monospace" font-size="15" font-weight="800" letter-spacing="1.5">{escape(item["eyebrow"])}</text>
  <text x="104" y="240" fill="#eefcff" font-family="system-ui,sans-serif" font-size="62" font-weight="800" letter-spacing="-2.5">{headline_spans}</text>
  <text x="104" y="454" fill="#a7bdc1" font-family="system-ui,sans-serif" font-size="22" font-weight="500">{hook_spans}</text>
  <text x="104" y="551" fill="{accent}" font-family="ui-monospace,monospace" font-size="16" font-weight="800">OPEN THE TRACE → ?case={escape(item["id"])}</text>
  <text x="875" y="205" fill="#eefcff" font-family="ui-monospace,monospace" font-size="104" font-weight="900">{number}</text>
  <text x="875" y="262" fill="{accent}" font-family="ui-monospace,monospace" font-size="14" font-weight="800" letter-spacing="1.4">REAL MODEL TRACE</text>
  <rect x="875" y="305" width="240" height="46" fill="none" stroke="#40616a"/><text x="995" y="334" fill="#dff8fc" font-family="ui-monospace,monospace" font-size="14" font-weight="800" text-anchor="middle">CHOOSE BEFORE REVEAL</text>
  <text x="875" y="409" fill="#91abb1" font-family="ui-monospace,monospace" font-size="13" font-weight="700">FAILURE SHAPE</text>
  <text x="875" y="443" fill="#eefcff" font-family="system-ui,sans-serif" font-size="20" font-weight="700">{escape(source["failure_shape"])}</text>
  <text x="875" y="526" fill="#91abb1" font-family="ui-monospace,monospace" font-size="12" font-weight="700">$0 · ZERO INSTALL · SOURCE-LINKED</text>
</svg>
'''


def font(size: int, bold: bool = False):
    from PIL import ImageFont

    names = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size=size)
    return ImageFont.load_default()


def draw_wrapped(draw, text: str, xy: tuple[int, int], *, max_width: int, font_obj, fill: str, spacing: int = 8, max_lines: int = 3) -> None:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textbbox((0, 0), trial, font=font_obj)[2] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    lines = lines[:max_lines]
    draw.multiline_text(xy, "\n".join(lines), font=font_obj, fill=fill, spacing=spacing)


def render_png(item: dict, source: dict, index: int, path: Path) -> None:
    from PIL import Image, ImageDraw

    accent = ACCENTS[index]
    image = Image.new("RGB", (1200, 630), "#061216")
    draw = ImageDraw.Draw(image)
    for y in range(630):
        shade = int(18 + (10 * y / 630))
        draw.line((0, y, 1200, y), fill=(5, shade, shade + 4))
    for x in range(0, 1200, 44):
        draw.line((x, 0, x, 630), fill="#10282d")
    for y in range(0, 630, 44):
        draw.line((0, y, 1200, y), fill="#10282d")
    draw.rectangle((34, 34, 1166, 596), outline=accent, width=2)
    draw.line((34, 116, 1166, 116), fill="#29434a", width=1)
    draw.line((840, 116, 840, 596), fill="#29434a", width=1)
    draw.text((70, 65), f'CAN YOU TRUST THIS AGENT? / CASE {index + 1:02d}', font=font(18, True), fill=accent)
    draw.text((104, 146), item["eyebrow"], font=font(15, True), fill=accent)
    draw_wrapped(draw, item["headline"], (104, 205), max_width=660, font_obj=font(58, True), fill="#eefcff", spacing=2, max_lines=3)
    draw_wrapped(draw, item["hook"].rsplit(":", 1)[0], (104, 438), max_width=660, font_obj=font(21), fill="#a7bdc1", spacing=7, max_lines=3)
    draw.text((104, 548), f'OPEN THE TRACE  >  ?case={item["id"]}', font=font(15, True), fill=accent)
    draw.text((875, 155), f'{index + 1:02d}', font=font(100, True), fill="#eefcff")
    draw.text((875, 265), "REAL MODEL TRACE", font=font(14, True), fill=accent)
    draw.rectangle((875, 305, 1115, 351), outline="#40616a", width=1)
    draw.text((900, 320), "CHOOSE BEFORE REVEAL", font=font(13, True), fill="#dff8fc")
    draw.text((875, 405), "FAILURE SHAPE", font=font(13, True), fill="#91abb1")
    draw_wrapped(draw, source["failure_shape"], (875, 435), max_width=235, font_obj=font(20, True), fill="#eefcff", spacing=4, max_lines=3)
    draw.text((875, 526), "$0 · ZERO INSTALL", font=font(13, True), fill="#91abb1")
    image.save(path, format="PNG", optimize=True)


def render_walkthrough(path: Path) -> None:
    from PIL import Image, ImageDraw

    steps = [
        ("01", "READ", "Inspect the deciding facts and evidence ledger."),
        ("02", "TRACE", "Read the model action, reasoning, and provenance."),
        ("03", "JUDGE", "Choose Trust, Verify, or Block before reveal."),
        ("04", "REVEAL", "Compare your call with the committed contract."),
        ("05", "SHARE", "Download a local receipt and invite a reviewer."),
    ]
    frames = []
    for active, (number, label, copy) in enumerate(steps):
        image = Image.new("RGB", (960, 540), "#061216")
        draw = ImageDraw.Draw(image)
        for x in range(0, 960, 40):
            draw.line((x, 0, x, 540), fill="#10282d")
        for y in range(0, 540, 40):
            draw.line((0, y, 960, y), fill="#10282d")
        draw.rectangle((24, 24, 936, 516), outline="#65e7ff", width=2)
        draw.text((56, 52), "CAN YOU TRUST THIS AGENT?", font=font(19, True), fill="#65e7ff")
        draw.text((56, 94), "A FIVE-STEP EVIDENCE REVIEW", font=font(40, True), fill="#eefcff")
        for index, (step_number, step_label, _) in enumerate(steps):
            x = 56 + index * 170
            color = "#9df8bd" if index < active else "#65e7ff" if index == active else "#47636a"
            draw.rectangle((x, 178, x + 142, 276), outline=color, width=3 if index == active else 1)
            draw.text((x + 14, 194), step_number, font=font(15, True), fill=color)
            draw.text((x + 14, 235), step_label, font=font(21, True), fill="#eefcff" if index <= active else "#78949a")
        draw.text((56, 332), f'{number} / {label}', font=font(18, True), fill="#65e7ff")
        draw_wrapped(draw, copy, (56, 376), max_width=775, font_obj=font(30, True), fill="#eefcff", spacing=5, max_lines=2)
        draw.text((56, 474), "$0 · ZERO INSTALL · ANSWERS STAY LOCAL", font=font(14, True), fill="#91abb1")
        frames.append(image)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=[900, 900, 900, 900, 1450], loop=0, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raster", action="store_true", help="also generate PNG cards and the animated GIF (requires Pillow)")
    args = parser.parse_args()
    campaign, playground = load_inputs()
    source_by_id = {item["id"]: item for item in playground["cases"]}
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(campaign["cases"]):
        stem = f'case-{index + 1:02d}-{item["id"]}'
        source = source_by_id[item["id"]]
        (ASSET_DIR / f"{stem}.svg").write_text(make_svg(item, source, index), encoding="utf-8")
        if args.raster:
            render_png(item, source, index, ASSET_DIR / f"{stem}.png")
    if args.raster:
        render_walkthrough(GIF_PATH)
    print(f"generated {len(campaign['cases'])} campaign SVGs" + (" + PNG/GIF assets" if args.raster else ""))


if __name__ == "__main__":
    main()
