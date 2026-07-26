"""Named dark palettes for launch assets, so each wave can have its own flavour.

Three waves in a row on the same violet started reading as one long post. Rotating the
palette per wave keeps the feed varied while the layout, type and structure stay constant —
which is what actually carries brand recognition. Better still when the colour *means*
something: the drift wave is about stale data, so it runs warm (amber and rust for aged,
mint for fresh) rather than reusing the security violet.

Pick one by name in a carousel generator:

    from palettes import PALETTES
    P = PALETTES["ember"]
"""

from __future__ import annotations

PALETTES: dict[str, dict[str, str]] = {
    # Waves 10-11 (security). Cool, clinical, "terminal".
    "violet": {
        "surface": "#161615", "panel": "#262521",
        "ink": "#f3f2ec", "ink2": "#c3c2b7", "muted": "#8a887f", "panel_muted": "#95938b",
        "accent": "#9085e9", "good": "#22c55e", "bad": "#f0524d", "warn": "#f0a500",
    },
    # Wave 12 (drift / stale data). Warm, aged, oxidised — amber and rust against a brown
    # near-black, with mint reserved for "fresh" so the semantic pair is temperature.
    "ember": {
        "surface": "#151210", "panel": "#241d17",
        "ink": "#f6efe4", "ink2": "#cbc0b0", "muted": "#8d8274", "panel_muted": "#9a8f80",
        "accent": "#f0a93c", "good": "#45cf95", "bad": "#e8613c", "warn": "#c9a227",
    },
    # Spare: cool telemetry blue, for a monitoring or watch-shaped wave.
    "signal": {
        "surface": "#0e1620", "panel": "#182432",
        "ink": "#eaf2fa", "ink2": "#b6c6d6", "muted": "#7d8fa1", "panel_muted": "#8b9cad",
        "accent": "#38bdf8", "good": "#34d399", "bad": "#fb7185", "warn": "#fbbf24",
    },
    # Spare: deep green, for a cost or efficiency wave.
    "moss": {
        "surface": "#101613", "panel": "#1b241e",
        "ink": "#eef4ef", "ink2": "#bccbc1", "muted": "#7f8f85", "panel_muted": "#8d9c92",
        "accent": "#7dd88f", "good": "#4ade80", "bad": "#f87171", "warn": "#facc15",
    },
}


def palette(name: str) -> dict[str, str]:
    if name not in PALETTES:
        raise KeyError(f"unknown palette {name!r}; known: {sorted(PALETTES)}")
    return PALETTES[name]
