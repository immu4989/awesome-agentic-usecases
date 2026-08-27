#!/usr/bin/env python3
"""Build the Community Evidence Loop launch GIF and its static poster.

The animation deliberately uses a small number of long-held, high-contrast
frames. That keeps every message readable in a fast social feed and keeps the
same file below the conservative 5 MB mobile upload ceiling.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets" / "community-evidence-social"
WIDTH, HEIGHT = 1200, 675

NAVY = (5, 13, 22)
PANEL = (13, 28, 43)
PANEL_2 = (19, 37, 56)
WHITE = (239, 248, 255)
MUTED = (154, 179, 199)
MINT = (88, 225, 186)
BLUE = (115, 168, 255)
AMBER = (255, 201, 107)
VIOLET = (220, 144, 255)
RED = (255, 116, 129)

FONT_REGULAR = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
FONT_BOLD = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
FONT_MONO = Path("/System/Library/Fonts/SFNSMono.ttf")


def font(size: int, *, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_MONO if mono else (FONT_BOLD if bold else FONT_REGULAR)
    return ImageFont.truetype(str(path), size=size)


def rounded_rectangle(
    image: Image.Image,
    box: tuple[int, int, int, int],
    *,
    radius: int,
    fill: tuple[int, int, int] | tuple[int, int, int, int],
    outline: tuple[int, int, int] | tuple[int, int, int, int] | None = None,
    width: int = 1,
) -> None:
    ImageDraw.Draw(image).rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def glow(base: Image.Image, center: tuple[int, int], color: tuple[int, int, int], radius: int, alpha: int) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x, y = center
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*color, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(radius // 2))
    base.alpha_composite(layer)


def background(accent: tuple[int, int, int], *, pulse: float = 0.5) -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), (*NAVY, 255))
    pixels = image.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            nx, ny = x / WIDTH, y / HEIGHT
            edge = max(0.0, 1.0 - math.hypot(nx - 0.78, ny - 0.18) / 0.92)
            lift = int(10 * edge)
            pixels[x, y] = (NAVY[0] + lift, NAVY[1] + lift, NAVY[2] + lift * 2, 255)

    grid = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(grid)
    for x in range(0, WIDTH, 48):
        draw.line((x, 0, x, HEIGHT), fill=(92, 139, 173, 14), width=1)
    for y in range(0, HEIGHT, 48):
        draw.line((0, y, WIDTH, y), fill=(92, 139, 173, 14), width=1)
    image.alpha_composite(grid)
    glow(image, (1020, 105), accent, 250, int(50 + 28 * pulse))
    glow(image, (140, 650), MINT, 190, 25)
    return image


def letterspaced(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, face: ImageFont.FreeTypeFont, fill, spacing: int) -> None:
    x, y = xy
    for character in text:
        draw.text((x, y), character, font=face, fill=fill)
        width = draw.textlength(character, font=face)
        x += int(width + spacing)


def header(image: Image.Image, scene: int, label: str, accent: tuple[int, int, int]) -> None:
    draw = ImageDraw.Draw(image)
    rounded_rectangle(image, (52, 42, 212, 78), radius=18, fill=(*accent, 28), outline=(*accent, 150), width=1)
    draw.ellipse((69, 55, 79, 65), fill=accent)
    letterspaced(draw, (91, 51), "NEW / OPEN", font(13, mono=True), WHITE, 1)
    letterspaced(draw, (244, 51), label, font(13, mono=True), accent, 2)
    draw.text((942, 50), "AAU / EVIDENCE", font=font(14, mono=True), fill=MUTED)

    for index in range(4):
        x = 524 + index * 42
        color = accent if index == scene else (70, 92, 110)
        draw.rounded_rectangle((x, 635, x + (28 if index == scene else 10), 641), radius=3, fill=color)


def footer(image: Image.Image, text: str = "github.com/immu4989/awesome-agentic-usecases") -> None:
    draw = ImageDraw.Draw(image)
    draw.text((52, 619), text, font=font(15, mono=True), fill=MUTED)


def scene_hook(*, pulse: float = 0.5) -> Image.Image:
    image = background(MINT, pulse=pulse)
    header(image, 0, "COMMUNITY EVIDENCE LOOP", MINT)
    draw = ImageDraw.Draw(image)
    draw.text((52, 135), "MOST AI REPOS", font=font(31, bold=True), fill=MUTED)
    draw.text((52, 176), "STOP AT THE DEMO.", font=font(62, bold=True), fill=WHITE)
    draw.text((52, 258), "THIS ONE GIVES", font=font(31, bold=True), fill=MUTED)
    draw.text((52, 299), "YOUR FORK A RECEIPT.", font=font(62, bold=True), fill=MINT)

    rounded_rectangle(image, (52, 411, 1148, 555), radius=24, fill=(*PANEL, 235), outline=(48, 78, 99, 220), width=2)
    facts = (("4", "EVIDENCE LEVELS", MINT), ("0", "UPLOADS / ACCOUNTS", AMBER), ("SHA-256", "VERIFIABLE PACK", BLUE))
    for index, (value, label, color) in enumerate(facts):
        x = 88 + index * 360
        draw.text((x, 443), value, font=font(34, bold=True), fill=color)
        draw.text((x, 495), label, font=font(14, mono=True), fill=WHITE)
        if index < 2:
            draw.line((x + 298, 443, x + 298, 523), fill=(54, 79, 99), width=1)
    footer(image)
    return image.convert("RGB")


def scene_loop(active: int, *, pulse: float = 0.5) -> Image.Image:
    colors = (MINT, BLUE, AMBER, VIOLET)
    image = background(colors[active], pulse=pulse)
    header(image, 1, "HOW PROOF MOVES", BLUE)
    draw = ImageDraw.Draw(image)
    draw.text((52, 121), "FROM A STARTER TO", font=font(27, bold=True), fill=MUTED)
    draw.text((52, 155), "REUSABLE PUBLIC PROOF", font=font(48, bold=True), fill=WHITE)

    y = 365
    centers = (150, 450, 750, 1050)
    labels = (("CONNECT", "your agent"), ("REVIEW", "the boundary"), ("REPEAT", "the runs"), ("PUBLISH", "the evidence"))
    draw.line((150, y, 1050, y), fill=(49, 76, 99), width=5)
    if active:
        draw.line((150, y, centers[active], y), fill=colors[active], width=5)
    for index, ((title, caption), x) in enumerate(zip(labels, centers)):
        selected = index <= active
        color = colors[index] if selected else (82, 104, 121)
        fill = (17, 46, 51) if selected else (14, 27, 39)
        draw.ellipse((x - 58, y - 58, x + 58, y + 58), fill=fill, outline=color, width=4 if index == active else 2)
        draw.text((x, y - 13), str(index + 1).zfill(2), font=font(24, bold=True, mono=True), fill=color, anchor="mm")
        draw.text((x, 448), title, font=font(18, bold=True), fill=WHITE if selected else MUTED, anchor="mm")
        draw.text((x, 478), caption, font=font(15), fill=MUTED, anchor="mm")

    rounded_rectangle(image, (315, 531, 885, 579), radius=24, fill=(13, 33, 43), outline=colors[active], width=1)
    draw.text((600, 555), "PRIVATE INPUTS STAY LOCAL. AGGREGATE RECEIPTS TRAVEL.", font=font(14, bold=True, mono=True), fill=colors[active], anchor="mm")
    footer(image)
    return image.convert("RGB")


def scene_levels(active: int, *, pulse: float = 0.5) -> Image.Image:
    colors = (MINT, BLUE, AMBER, VIOLET)
    image = background(colors[active], pulse=pulse)
    header(image, 2, "TRUST MUST BE EARNED", AMBER)
    draw = ImageDraw.Draw(image)
    draw.text((52, 121), "EVIDENCE LEVELS ARE", font=font(27, bold=True), fill=MUTED)
    draw.text((52, 155), "DERIVED, NEVER DECLARED.", font=font(48, bold=True), fill=WHITE)

    levels = (
        ("01", "GENERATED", "valid local artifacts"),
        ("02", "DOMAIN REVIEWED", "review scope recorded"),
        ("03", "REPRODUCED", "repeated runs agree"),
        ("04", "VERIFIED", "committed proof matches"),
    )
    for index, (number, title, caption) in enumerate(levels):
        x = 52 + index * 276
        selected = index <= active
        border = colors[index] if selected else (54, 76, 94)
        fill = (*PANEL_2, 235) if selected else (*PANEL, 210)
        rounded_rectangle(image, (x, 285, x + 252, 493), radius=22, fill=fill, outline=border, width=3 if index == active else 1)
        draw.text((x + 24, 312), number, font=font(18, bold=True, mono=True), fill=border)
        draw.ellipse((x + 195, 309, x + 220, 334), fill=border if selected else (43, 58, 72))
        if selected:
            draw.line((x + 202, 321, x + 208, 327, x + 219, 314), fill=NAVY, width=3, joint="curve")
        draw.text((x + 24, 367), title, font=font(19, bold=True), fill=WHITE if selected else MUTED)
        draw.line((x + 24, 404, x + 224, 404), fill=(51, 76, 95), width=1)
        draw.text((x + 24, 427), caption, font=font(15), fill=MUTED)

    rounded_rectangle(image, (52, 525, 1148, 576), radius=20, fill=(36, 31, 22, 230), outline=(*AMBER, 130), width=1)
    draw.text((600, 551), "NOT CERTIFICATION. A TAMPER-EVIDENT RECORD OF WHAT WAS ACTUALLY RUN.", font=font(14, bold=True, mono=True), fill=AMBER, anchor="mm")
    footer(image)
    return image.convert("RGB")


def scene_cta(*, pulse: float = 0.5) -> Image.Image:
    image = background(VIOLET, pulse=pulse)
    header(image, 3, "BUILD. TEST. PROVE.", VIOLET)
    draw = ImageDraw.Draw(image)
    letterspaced(draw, (52, 134), "STARTER", font(18, mono=True), MINT, 3)
    draw.line((208, 149, 302, 149), fill=(73, 103, 127), width=2)
    draw.polygon(((302, 149), (289, 142), (289, 156)), fill=MINT)
    letterspaced(draw, (330, 134), "VERIFIED", font(18, mono=True), VIOLET, 3)
    draw.text((52, 190), "MAKE YOUR FORK", font=font(59, bold=True), fill=WHITE)
    draw.text((52, 263), "WORTH TRUSTING.", font=font(59, bold=True), fill=VIOLET)

    rounded_rectangle(image, (52, 375, 1148, 512), radius=24, fill=(*PANEL, 240), outline=(*VIOLET, 145), width=2)
    checks = (("RUN LOCAL", MINT), ("PUBLISH EVIDENCE", BLUE), ("EARN TRUST", VIOLET))
    for index, (label, color) in enumerate(checks):
        x = 89 + index * 356
        draw.ellipse((x, 417, x + 26, 443), fill=color)
        draw.line((x + 7, 430, x + 12, 435, x + 21, 423), fill=NAVY, width=3, joint="curve")
        draw.text((x + 40, 414), label, font=font(18, bold=True), fill=WHITE)
        if index < 2:
            draw.line((x + 296, 409, x + 296, 460), fill=(54, 79, 99), width=1)

    rounded_rectangle(image, (52, 535, 551, 585), radius=25, fill=(12, 43, 42), outline=MINT, width=2)
    draw.text((301, 560), "TRY THE COMMUNITY EVIDENCE DESK", font=font(14, bold=True, mono=True), fill=MINT, anchor="mm")
    footer(image)
    return image.convert("RGB")


def transition(outgoing: Image.Image, incoming: Image.Image, frames: int = 4) -> list[Image.Image]:
    result: list[Image.Image] = []
    for index in range(1, frames + 1):
        progress = index / (frames + 1)
        edge = int(WIDTH * progress)
        frame = outgoing.copy()
        frame.paste(incoming.crop((0, 0, edge, HEIGHT)), (0, 0))
        draw = ImageDraw.Draw(frame, "RGBA")
        draw.rectangle((max(0, edge - 8), 0, min(WIDTH, edge + 8), HEIGHT), fill=(*MINT, 105))
        result.append(frame)
    return result


def shared_palette(images: list[Image.Image], colors: int = 160) -> Image.Image:
    sample = Image.new("RGB", (WIDTH, HEIGHT))
    tile_size = (WIDTH // 2, HEIGHT // 2)
    for index, image in enumerate(images[:4]):
        sample.paste(image.resize(tile_size, Image.Resampling.LANCZOS), ((index % 2) * tile_size[0], (index // 2) * tile_size[1]))
    # Reserve visible samples for brand accents. Without these swatches, the
    # large dark gradient can crowd small amber and violet UI details out of
    # the adaptive GIF palette.
    palette_draw = ImageDraw.Draw(sample)
    for index, color in enumerate((MINT, BLUE, AMBER, VIOLET, WHITE, MUTED)):
        palette_draw.rectangle((index * 200, 0, index * 200 + 199, 45), fill=color)
    return sample.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)


def save_gif(frames: list[Image.Image], durations: list[int]) -> Path:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSET_DIR / "community-evidence-loop.gif"
    # Sample the completed frame from each scene so all four accent colors
    # survive GIF quantization. Transition frames alone do not contain the
    # full evidence-level palette.
    palette = shared_palette([frames[0], frames[8], frames[16], frames[21]])
    ready = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    ready[0].save(
        path,
        save_all=True,
        append_images=ready[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=1,
    )
    return path


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    hook = scene_hook(pulse=0.8)
    loop_frames = [scene_loop(index, pulse=0.4 + 0.15 * index) for index in range(4)]
    level_frames = [scene_levels(index, pulse=0.4 + 0.15 * index) for index in range(4)]
    cta = scene_cta(pulse=0.9)

    frames: list[Image.Image] = [hook]
    durations: list[int] = [1800]

    for frame in transition(hook, loop_frames[0]):
        frames.append(frame)
        durations.append(70)
    for index, frame in enumerate(loop_frames):
        frames.append(frame)
        durations.append(420 if index < 3 else 1200)

    for frame in transition(loop_frames[-1], level_frames[0]):
        frames.append(frame)
        durations.append(70)
    for index, frame in enumerate(level_frames):
        frames.append(frame)
        durations.append(420 if index < 3 else 1400)

    for frame in transition(level_frames[-1], cta):
        frames.append(frame)
        durations.append(70)
    frames.append(cta)
    durations.append(2100)

    for frame in transition(cta, hook):
        frames.append(frame)
        durations.append(70)

    poster = ASSET_DIR / "community-evidence-loop-poster.png"
    hook.save(poster, optimize=True)
    gif = save_gif(frames, durations)
    total_ms = sum(durations)
    print(f"{gif.relative_to(ROOT)}: {len(frames)} frames, {total_ms / 1000:.1f}s, {gif.stat().st_size / 1_000_000:.2f} MB")
    print(f"{poster.relative_to(ROOT)}: {poster.stat().st_size / 1_000:.0f} KB")


if __name__ == "__main__":
    main()
