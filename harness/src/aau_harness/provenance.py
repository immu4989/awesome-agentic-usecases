"""What produced a number, recorded alongside the number.

A result that says `0.611` and nothing else is not reproducible, however carefully it was
measured. Three facts are needed to re-run it and get the same answer: when it ran, what
code ran it, and which model actually answered — and the third is the one that bites,
because several providers serve floating aliases. `mistral-small-latest` is whatever
Mistral shipped this morning, so an eval recorded under that name cannot be repeated even
by its author.

Providers echo the concrete model they served in every response. This module captures that
and stamps it onto every saved result, so a number carries its own provenance rather than
depending on someone remembering.
"""

from __future__ import annotations

import datetime
import platform

# Aliases that move under you. Results recorded against these are a snapshot of a moving
# target and are labelled as such rather than being quietly presented as reproducible.
_FLOATING_MARKERS = ("latest", "-plus", "-max", "preview", "experimental", ":free")

# The most recently constructed backend. A module-level handle is deliberate: it lets
# every use case record provenance without threading a backend argument through thirteen
# separate save_results signatures, and evals are single-threaded by construction.
_ACTIVE: object | None = None


def register_backend(backend: object) -> None:
    global _ACTIVE
    _ACTIVE = backend


def is_floating(model: str | None) -> bool:
    """True when the identifier can silently point at different weights over time."""
    return bool(model) and any(m in model.lower() for m in _FLOATING_MARKERS)


def harness_version() -> str:
    try:
        from importlib.metadata import version

        return version("aau-harness")
    except Exception:
        return "unknown"


def snapshot() -> dict:
    """Everything needed to reproduce a run, as far as it can be known."""
    requested = getattr(_ACTIVE, "model", None)
    served = getattr(_ACTIVE, "served_model", None)
    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "harness_version": harness_version(),
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.machine()}",
        "requested_model": requested,
        "served_model": served,
    }
    # The honest flag: if the identifier floats and the provider did not pin it for us,
    # this result is a point-in-time observation, not something a reader can reproduce.
    #
    # A name that carries no floating marker can still be an alias. `deepseek-chat` reads
    # as pinned and served `deepseek-v4-flash`, so the mismatch itself is the evidence --
    # whatever the identifier looks like, asking for one model and being given another
    # means the name tracks a moving target.
    redirected = bool(requested) and bool(served) and served != requested
    out["served_differs_from_requested"] = redirected
    out["model_pinned"] = bool(served) and not is_floating(served) and not redirected
    if redirected:
        out["reproducibility_note"] = (
            f"requested {requested!r} but the provider served {served!r}; the identifier "
            "is an alias, so re-running may exercise different weights."
        )
    elif requested and is_floating(requested) and not out["model_pinned"]:
        out["reproducibility_note"] = (
            f"{requested!r} is a floating alias; the provider did not report a pinned "
            "snapshot, so re-running may exercise different weights."
        )
    return out
