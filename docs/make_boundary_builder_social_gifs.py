#!/usr/bin/env python3
"""Create deterministic, feed-sized GIFs from the Boundary Builder social cards."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets" / "boundary-builder-social"
INK = (7, 11, 16)
MINT = (109, 245, 210)
PINK = (255, 122, 200)
YELLOW = (255, 222, 89)


def smooth(value: float) -> float:
    return value * value * (3 - 2 * value)


def load(stem: str, size: tuple[int, int]) -> Image.Image:
    return Image.open(ASSET_DIR / f"{stem}.png").convert("RGB").resize(size, Image.Resampling.LANCZOS)


def dim(image: Image.Image, amount: float = 0.68) -> Image.Image:
    return Image.blend(image, Image.new("RGB", image.size, INK), amount)


def paste_region(frame: Image.Image, source: Image.Image, box: tuple[int, int, int, int]) -> None:
    frame.paste(source.crop(box), box[:2])


def alpha_overlay(image: Image.Image, draw_fn) -> Image.Image:
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(overlay))
    return Image.alpha_composite(base, overlay).convert("RGB")


def quantize(frames: list[Image.Image], colors: int = 128) -> list[Image.Image]:
    palette = frames[-1].quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    return [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]


def save(stem: str, frames: list[Image.Image], durations: list[int], *, colors: int = 128) -> None:
    output = ASSET_DIR / f"{stem}.gif"
    ready = quantize(frames, colors=colors)
    ready[0].save(
        output,
        save_all=True,
        append_images=ready[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"{output.relative_to(ROOT)}: {len(ready)} frames, {output.stat().st_size / 1_000_000:.2f} MB")


def add_readable_intro(frames: list[Image.Image], durations: list[int], base: Image.Image, dark: Image.Image) -> None:
    frames.append(base.copy())
    durations.append(750)
    for index in range(1, 4):
        frames.append(Image.blend(base, dark, index / 3))
        durations.append(85)


def add_loop_reset(frames: list[Image.Image], durations: list[int], base: Image.Image, dark: Image.Image) -> None:
    for index in range(1, 5):
        frames.append(Image.blend(dark, base, index / 4))
        durations.append(85)


def launch_gif() -> None:
    base = load("launch-hero", (1200, 675))
    dark = dim(base, 0.76)
    frames: list[Image.Image] = []
    durations: list[int] = []
    add_readable_intro(frames, durations, base, dark)

    for index in range(14):
        progress = smooth(index / 13)
        edge = max(1, int(base.width * progress))
        frame = dark.copy()
        frame.paste(base.crop((0, 0, edge, base.height)), (0, 0))
        if edge < base.width:
            frame = alpha_overlay(
                frame,
                lambda draw, x=edge: draw.rectangle((max(0, x - 8), 0, min(base.width, x + 8), base.height), fill=(*MINT, 130)),
            )
        frames.append(frame)
        durations.append(75)

    release_box = (748, 450, 1137, 523)
    for index in range(8):
        pulse = (math.sin(index / 8 * math.tau - math.pi / 2) + 1) / 2
        frame = base.copy()
        inset = int(6 - pulse * 6)
        alpha = int(35 + pulse * 125)
        frame = alpha_overlay(
            frame,
            lambda draw, pad=inset, opacity=alpha: draw.rounded_rectangle(
                (release_box[0] - pad, release_box[1] - pad, release_box[2] + pad, release_box[3] + pad),
                radius=5,
                outline=(*MINT, opacity),
                width=4,
            ),
        )
        frames.append(frame)
        durations.append(95)

    frames.append(base.copy())
    durations.append(1450)
    for index in range(1, 5):
        frames.append(Image.blend(base, dark, index / 4))
        durations.append(95)
    add_loop_reset(frames, durations, base, dark)
    save("launch-hero", frames, durations, colors=144)


def boundary_gif() -> None:
    base = load("boundary-proof", (1200, 675))
    dark = dim(base, 0.72)
    title_box = (0, 0, 1200, 224)
    left_box = (54, 239, 512, 472)
    delta_box = (536, 291, 664, 421)
    right_box = (688, 239, 1147, 472)
    label_box = (430, 481, 770, 520)
    receipt_box = (54, 539, 1147, 622)
    frames: list[Image.Image] = []
    durations: list[int] = []
    add_readable_intro(frames, durations, base, dark)

    visible: list[tuple[int, int, int, int]] = [title_box]
    for box, accent in ((left_box, MINT), (delta_box, YELLOW), (right_box, PINK), (label_box, YELLOW), (receipt_box, MINT)):
        for index in range(4):
            progress = smooth((index + 1) / 4)
            frame = dark.copy()
            for prior in visible:
                paste_region(frame, base, prior)
            width = max(1, int((box[2] - box[0]) * progress))
            reveal = (box[0], box[1], box[0] + width, box[3])
            paste_region(frame, base, reveal)
            frame = alpha_overlay(
                frame,
                lambda draw, x=box[0] + width, y1=box[1], y2=box[3], color=accent: draw.line((x, y1, x, y2), fill=(*color, 180), width=5),
            )
            frames.append(frame)
            durations.append(85)
        visible.append(box)

    for index in range(7):
        pulse = (math.sin(index / 7 * math.tau - math.pi / 2) + 1) / 2
        radius = int(66 + pulse * 12)
        frame = base.copy()
        frame = alpha_overlay(
            frame,
            lambda draw, r=radius, opacity=int(45 + pulse * 115): draw.ellipse(
                (600 - r, 356 - r, 600 + r, 356 + r), outline=(*PINK, opacity), width=4
            ),
        )
        frames.append(frame)
        durations.append(100)
    frames.append(base.copy())
    durations.append(1450)
    for index in range(1, 5):
        frames.append(Image.blend(base, dark, index / 4))
        durations.append(95)
    add_loop_reset(frames, durations, base, dark)
    save("boundary-proof", frames, durations, colors=144)


def bundle_gif() -> None:
    base = load("export-bundle-square", (900, 900))
    dark = dim(base, 0.74)
    title_box = (0, 0, 900, 258)
    file_boxes = [
        (48, 273, 432, 339), (460, 273, 844, 339),
        (48, 349, 432, 414), (460, 349, 844, 414),
        (48, 424, 432, 489), (460, 424, 844, 489),
        (48, 500, 432, 565), (460, 500, 844, 565),
    ]
    stats_box = (48, 602, 844, 703)
    flow_box = (48, 725, 844, 767)
    action_box = (48, 786, 844, 846)
    footer_box = (48, 850, 844, 878)
    frames: list[Image.Image] = []
    durations: list[int] = []
    visible = [title_box]
    add_readable_intro(frames, durations, base, dark)

    for index, box in enumerate(file_boxes):
        frame = dark.copy()
        for prior in visible:
            paste_region(frame, base, prior)
        paste_region(frame, base, box)
        color = (YELLOW, MINT, PINK)[index % 3]
        frame = alpha_overlay(
            frame,
            lambda draw, region=box, accent=color: draw.rectangle(region, outline=(*accent, 150), width=3),
        )
        frames.append(frame)
        durations.append(175)
        visible.append(box)

    for box, accent in ((stats_box, MINT), (flow_box, PINK), (action_box, YELLOW), (footer_box, MINT)):
        frame = dark.copy()
        for prior in visible:
            paste_region(frame, base, prior)
        paste_region(frame, base, box)
        frame = alpha_overlay(
            frame,
            lambda draw, region=box, color=accent: draw.line(
                (region[0], region[1], region[2], region[1]), fill=(*color, 170), width=3
            ),
        )
        frames.append(frame)
        durations.append(210)
        visible.append(box)

    frames.append(base.copy())
    durations.append(1550)
    for index in range(1, 5):
        frames.append(Image.blend(base, dark, index / 4))
        durations.append(95)
    add_loop_reset(frames, durations, base, dark)
    save("export-bundle-square", frames, durations, colors=128)


def main() -> None:
    launch_gif()
    boundary_gif()
    bundle_gif()


if __name__ == "__main__":
    main()
