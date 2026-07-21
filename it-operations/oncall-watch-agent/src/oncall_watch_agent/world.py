"""Synthetic world: service telemetry that arrives one tick at a time.

This is the repo's first `watch` use case, and the first where **time** is part of the
problem. Every other agent here receives a complete case file and answers it. This one
advances a clock: it sees one minute of telemetry, decides whether that is enough, and
either waits or commits. It cannot see the future, and waiting has a cost.

That makes patience measurable, which is the whole point. Two of the archetypes are
indistinguishable at the moment the metrics first go bad:

- A deploy regression and an upstream blip both open with a sharp error spike. The blip
  recovers on its own within a couple of ticks and has no deploy behind it. An agent
  that pages on the first bad sample is the on-call pager that everyone learns to
  ignore.
- The slow burn never produces a dramatic sample at all. Latency creeps past the SLO
  over twenty minutes. An agent watching for spikes watches right past it.

So the eval scores three things a single-shot use case cannot: did it reach the right
severity, did it avoid crying wolf, and **how many ticks after onset did it act**.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field

SEVERITIES = ["page", "ticket", "none"]

WINDOW_TICKS = 20            # one tick = one minute of telemetry
SLO_ERROR_RATE = 0.02        # 2% of requests
SLO_P99_MS = 800
SATURATION_WARN = 0.85

RUNBOOK_KB = [
    {
        "id": "OC-PAGE-00",
        "title": "What warrants waking someone up",
        "text": (
            "Page the on-call engineer for sustained user-facing harm: an error rate or "
            f"p99 latency past the SLO ({int(SLO_ERROR_RATE * 100)}% errors, "
            f"{SLO_P99_MS}ms p99) that persists rather than recovering on its own. "
            "Trends that will breach but have not yet, such as rising saturation with "
            "healthy errors and latency, are a ticket rather than a page. Everything "
            "else is silence."
        ),
    },
    {
        "id": "OC-BLIP-01",
        "title": "Transients and alert fatigue",
        "text": (
            "A single bad sample is not an incident. Upstream dependencies blip, and "
            "most blips recover within two or three minutes without intervention. "
            "Paging on a transient trains the team to ignore the pager, which is worse "
            "than the blip. Wait for a sustained signal before paging. If the metrics "
            "return to normal on their own, the correct action is silence."
        ),
    },
    {
        "id": "OC-DEPLOY-02",
        "title": "Deploys change the interpretation",
        "text": (
            "A degradation that begins shortly after a deploy is a regression until "
            "proven otherwise. It will not self-heal, and there is a rollback available, "
            "so page rather than waiting it out. The same metric pattern with no recent "
            "deploy is more likely an upstream transient. Always check the deploy history "
            "before deciding."
        ),
    },
    {
        "id": "OC-SLOW-03",
        "title": "Slow burns",
        "text": (
            "Not every incident announces itself with a spike. A metric drifting "
            "steadily worse across the window and crossing the SLO by the end is an "
            "incident even though no single sample looks alarming. Compare the end of "
            "the window against the start, not each sample against a threshold."
        ),
    },
    {
        "id": "OC-MAINT-04",
        "title": "Planned maintenance",
        "text": (
            "During an approved maintenance window, degraded metrics on the affected "
            "service are expected and must not page. Check the service context for an "
            "active window before acting on bad numbers."
        ),
    },
]

SERVICES = ["checkout-api", "payments-gateway", "search-index", "media-transcoder",
            "auth-service", "cart-service"]

ARCHETYPES = {
    "DEPLOY_REGRESSION": "page",     # sharp, sustained, deploy behind it
    "UPSTREAM_BLIP": "none",         # sharp, recovers, no deploy  <- fatigue trap
    "SLOW_BURN": "page",             # never spikes, crosses SLO by the end
    "MAINTENANCE_WINDOW": "none",    # terrible metrics, suppressed
    "CAPACITY_TREND": "ticket",      # saturation rising, SLOs still healthy
    "HEALTHY": "none",               # noise only
}


@dataclass
class Scenario:
    scenario_id: str
    alert_text: str
    service_id: str
    context: dict
    ticks: list
    archetype: str
    gold_severity: str
    onset_tick: int | None       # first tick at which the truth is knowable
    detectable_tick: int | None  # earliest tick a correct agent could commit
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _sample(rng: random.Random, err: float, p99: float, sat: float) -> dict:
    """One minute of telemetry with a little noise on every channel."""
    return {
        "error_rate": round(max(0.0, err + rng.gauss(0, 0.0012)), 5),
        "p99_ms": int(max(40, p99 + rng.gauss(0, 22))),
        "saturation": round(min(0.99, max(0.05, sat + rng.gauss(0, 0.02))), 3),
        "rps": int(max(10, rng.gauss(900, 90))),
    }


def build_series(archetype: str, rng: random.Random) -> tuple[list, int | None, int | None]:
    """Return (ticks, onset_tick, detectable_tick).

    onset_tick is when the underlying condition starts. detectable_tick is the first
    tick at which a *correct* agent could commit: for a sustained incident that is
    onset + 2, because before then it is indistinguishable from a transient.
    """
    ticks: list[dict] = []
    onset = detectable = None

    if archetype == "DEPLOY_REGRESSION":
        onset = rng.randrange(5, 11)
        for t in range(WINDOW_TICKS):
            if t < onset:
                ticks.append(_sample(rng, 0.004, 240, 0.42))
            else:
                ramp = min(1.0, (t - onset + 1) / 3)
                ticks.append(_sample(rng, 0.004 + 0.055 * ramp, 240 + 900 * ramp, 0.5))
        detectable = min(onset + 2, WINDOW_TICKS - 1)

    elif archetype == "UPSTREAM_BLIP":
        onset = rng.randrange(5, 13)
        for t in range(WINDOW_TICKS):
            d = t - onset
            if d < 0 or d > 2:
                ticks.append(_sample(rng, 0.004, 250, 0.44))
            else:  # spike that decays back to baseline
                mag = (0.06, 0.03, 0.008)[d]
                ticks.append(_sample(rng, 0.004 + mag, 250 + 1100 * (mag / 0.06), 0.5))
        detectable = min(onset + 3, WINDOW_TICKS - 1)  # recovery visible

    elif archetype == "SLOW_BURN":
        onset = 0
        for t in range(WINDOW_TICKS):
            frac = t / (WINDOW_TICKS - 1)
            ticks.append(_sample(rng, 0.003 + 0.024 * frac, 260 + 640 * frac, 0.5 + 0.2 * frac))
        detectable = WINDOW_TICKS - 4  # trend is unambiguous near the end

    elif archetype == "MAINTENANCE_WINDOW":
        onset = rng.randrange(3, 9)
        for t in range(WINDOW_TICKS):
            if t < onset:
                ticks.append(_sample(rng, 0.004, 250, 0.45))
            else:
                ticks.append(_sample(rng, 0.09, 1600, 0.8))
        detectable = 0  # context alone settles it, no waiting required

    elif archetype == "CAPACITY_TREND":
        onset = 0
        for t in range(WINDOW_TICKS):
            frac = t / (WINDOW_TICKS - 1)
            # saturation climbs into warning; errors and latency stay healthy
            ticks.append(_sample(rng, 0.004, 300, 0.62 + 0.28 * frac))
        detectable = WINDOW_TICKS - 5

    else:  # HEALTHY
        for t in range(WINDOW_TICKS):
            ticks.append(_sample(rng, 0.004, 260, 0.5))
        detectable = WINDOW_TICKS - 1

    for i, tk in enumerate(ticks):
        tk["tick"] = i
        tk["clock"] = f"14:{i:02d}"
    return ticks, onset, detectable


def generate_scenarios(n: int = 30, seed: int = 29) -> list[Scenario]:
    rng = random.Random(seed)
    types = list(ARCHETYPES)
    scenarios = []
    for i in range(n):
        archetype = types[i % len(types)]
        service = rng.choice(SERVICES)
        ticks, onset, detectable = build_series(archetype, rng)

        deploy_tick = onset if archetype == "DEPLOY_REGRESSION" else None
        context = {
            "service_id": service,
            "tier": rng.choice(["tier-1", "tier-1", "tier-2"]),
            "slo_error_rate": SLO_ERROR_RATE,
            "slo_p99_ms": SLO_P99_MS,
            "saturation_warn": SATURATION_WARN,
            "recent_deploys": (
                [{"clock": f"14:{deploy_tick:02d}", "version": f"v{rng.randrange(200, 999)}",
                  "note": "rolling deploy completed"}]
                if deploy_tick is not None else []
            ),
            "maintenance_window_active": archetype == "MAINTENANCE_WINDOW",
            "maintenance_note": (
                "approved storage migration, degraded latency expected"
                if archetype == "MAINTENANCE_WINDOW" else None
            ),
        }
        scenarios.append(
            Scenario(
                scenario_id=f"sc-{i:03d}",
                alert_text=(
                    f"You are on watch for {service}. Telemetry is streaming one minute "
                    f"at a time from 14:00. Decide whether this window needs a page, a "
                    f"ticket, or nothing."
                ),
                service_id=service,
                context=context,
                ticks=ticks,
                archetype=archetype,
                gold_severity=ARCHETYPES[archetype],
                onset_tick=onset,
                detectable_tick=detectable,
            )
        )
    return scenarios


def save_scenarios(scenarios: list[Scenario], path: str) -> None:
    with open(path, "w") as f:
        for sc in scenarios:
            f.write(json.dumps(sc.as_dict()) + "\n")


def load_scenarios(path: str) -> list[Scenario]:
    with open(path) as f:
        return [Scenario(**json.loads(line)) for line in f]


def search_runbook(query: str, top_k: int = 2) -> list[dict]:
    terms = {w.strip(".,?!").lower() for w in query.split() if len(w) > 3}
    scored = []
    for doc in RUNBOOK_KB:
        text = (doc["title"] + " " + doc["text"]).lower()
        score = sum(1 for t in terms if t in text)
        scored.append((score, doc))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    return [doc for score, doc in scored[:top_k] if score > 0] or [scored[0][1]]
