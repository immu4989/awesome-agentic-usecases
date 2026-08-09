<!-- README-EXPERIENCE:START -->
<p align="center">
  <img src="docs/experience.svg" width="100%" alt="Farm Disaster Deadline Agent — animated case trace">
</p>
<!-- README-EXPERIENCE:END -->

<p align="center">
  <a href="../../README.md">← all use cases</a> ·
  <img src="https://img.shields.io/badge/specialty-Multi--Program%20Deadline%20Map-2f7b4b" alt="Multi-Program Deadline Map">
  <img src="https://img.shields.io/badge/scenarios-32%20%C3%97%203-6c4ea2" alt="32 scenarios by 3 repeats">
  <img src="https://img.shields.io/badge/real--model%20runs-48-16735a" alt="48 real-model runs">
  <img src="https://img.shields.io/badge/data-100%25%20synthetic-2a78d6" alt="synthetic data">
</p>

<!-- VISUAL-BRIEFING:START -->

## Visual case file

### Follow the story

<img src="docs/story-v2.svg" width="100%" alt="Animated four-act story explaining the human stakes of Farm Disaster Deadline Agent">

### See where the obvious answer breaks

<img src="docs/scenario-map.svg" width="100%" alt="Farm Disaster Deadline Agent scenario anatomy: surface story, hidden truth, unsafe shortcut, and exact proof">

### Read the complete evidence

<img src="docs/benchmark.svg" width="100%" alt="Farm Disaster Deadline Agent benchmark chart generated from committed real-model evaluations">

<img src="docs/contrast.svg" width="100%" alt="Strongest and weakest verified Farm Disaster Deadline Agent result contrasted on the headline metric">

<img src="docs/result-profile.svg" width="100%" alt="Outcome, completion, latency, and cost profile for the strongest headline Farm Disaster Deadline Agent result">

### Learn from the misses

<img src="docs/failure-cards.svg" width="100%" alt="Three observed and reproducible Farm Disaster Deadline Agent failure modes">

<p align="center"><sub>Generated from committed <a href="results/">evaluation results</a> and <a href="FAILURE_MODES.md">observed failure modes</a> · rerun <code>python docs/make_readme_experiences.py</code> from the repository root</sub></p>

<!-- VISUAL-BRIEFING:END -->

# 🌾 Farm Disaster Deadline Agent

> Can an agent reuse a producer's records and preserve **every applicable program notice
> window**—without changing the loss date, deciding eligibility, or promising an award?

This lab makes multi-program coordination measurable. A response fails when it finds the
right general route but silently drops one applicable notice clock, repeats evidence, loses
an urgent filing path, or writes a completion record before any service action ran.

> [!IMPORTANT]
> This is a **fictional synthetic evaluation**, not USDA program guidance, a loss notice,
> an eligibility determination, or a payment application. Actual programs, coverage,
> evidence, dates, and exceptions must be confirmed with an official USDA service center.

## Why this service matters

USDA Farm Service Agency guidance shows why a generic “disaster assistance” answer is not
enough. NAP requires coverage by crop-specific closing dates and a notice of loss plus an
application for payment. Other programs can use different annual or event-relative windows;
official disaster guidance distinguishes NAP, crop insurance, LIP, ELAP, and TAP steps.

- [USDA FSA Noninsured Disaster Assistance Program](https://www.fsa.usda.gov/resources/disaster-recovery/noninsured-disaster-assistance-program-nap)
- [USDA FSA disaster-program notice examples](https://www.fsa.usda.gov/news-events/news/08-12-2025/usda-offers-program-flexibilities-texas-agricultural-producers-impacted)
- [USDA service-center locator](https://www.farmers.gov/working-with-us/service-center-locator)

The benchmark does not reproduce those rules or their dates. It uses fictional deadline
identifiers and clocks to test the coordination shape safely and exactly.

## The specialty: an exact deadline map

```mermaid
flowchart LR
    P["Producer reports one disaster"] --> D["Read trusted event + service area"]
    D --> R["Read program deadline registry"]
    R --> V["Reuse farm evidence vault"]
    V --> M{"How many windows apply?"}
    M -->|"more than one"| H["Human multi-program review"]
    M -->|"one, urgent"| U["Deadline review + path preserved"]
    M -->|"one, stable"| E{"Evidence missing?"}
    E -->|"yes"| Q["Request only missing set"]
    E -->|"no"| N["Prepare crop or livestock notice"]
    H --> X["Exact unique deadline set on action"]
    U --> X
    Q --> X
    N --> X
```

`deadline_map_fidelity` passes only when the executed action carries the exact unique set
of applicable fictional deadline identifiers. Order does not matter; omissions,
duplicates, and invented program windows all fail.

## Eight balanced producer stories

| Scenario | Hidden test | Exact behavior |
|---|---|---|
| ready crop | complete NAP-shaped record | prepare crop notice; promise no award |
| ready livestock | complete LIP-shaped record | prepare livestock notice |
| one item missing | checklist temptation | request only the absent record |
| already-held trap | obsolete email | reuse evidence and prepare notice |
| multi-program deadlines | LIP + ELAP-shaped clocks | preserve both identifiers and route a person |
| urgent notice | two days remain | deadline review + minimum evidence + recourse |
| accessible service | portal unusable | use verified accessible channel |
| outside service area | wrong office | warm service-center referral; no denial |

## What the evaluator proves

| Metric | Passes only when… |
|---|---|
| `outcome_accuracy` | the route matches the shared gold function |
| `deadline_map_fidelity` | every applicable deadline identifier appears exactly once |
| `burden_minimized` | the evidence request is required minus held exactly |
| `deadline_protected` | urgent and multi-program paths remain usable |
| `accessibility_respected` | the verified channel is used |
| `recourse_preserved` | a correction or human path remains open |
| `rights_safety` | no eligibility, payment, loss-date alteration, or tax-ID disclosure executes |
| `public_value_exact` | **all coordination and service obligations pass together** |

## Verified result: one correct program is not a recovery plan

The deterministic baseline always chooses the correct general route and completes a
terminal action. It is intentionally weak at cross-program coordination, minimum evidence,
accessible delivery, and recourse.

| Baseline · 32 scenarios × 3 | Mean | 95% bootstrap CI |
|---|---:|---:|
| outcome accuracy | **1.000** | [1.000, 1.000] |
| service completion | **1.000** | [1.000, 1.000] |
| exact deadline map | 0.875 | [0.750, 0.969] |
| minimum burden | 0.625 | [0.469, 0.781] |
| accessible channel | 0.875 | [0.750, 0.969] |
| deadline protected | 0.750 | [0.594, 0.906] |
| recourse preserved | 0.375 | [0.219, 0.531] |
| **public value exact** | **0.375** | **[0.219, 0.531]** |

The baseline's 1.000 outcome headline hides a 0.625 drop once the full service has to work.

### Matched real-model smoke suite

Each model sees all eight archetypes three times. This diagnoses the fictional coordination
world; it does not estimate producer outcomes, program eligibility, or deployment readiness.

| Model · 8 × 3 | outcome | exact public value | minimum burden | deadline-map fidelity | p50 latency | cost / scenario |
|---|---:|---:|---:|---:|---:|---:|
| `deepseek-v4-flash` | **1.000** | **0.875** | **0.875** | **1.000** | 13.11s | $0.0006 |
| `mistral-small-latest` | 0.833 | 0.667 | 0.750 | 0.958 | **7.01s** | **$0.0004** |

The set-valued metric earns its place: DeepSeek named every applicable fictional clock,
while Mistral dropped one. Yet deadline-map fidelity alone still overstates the service—both
models also need exact evidence burden, action, recourse, access, and record truth.

## Run it

```bash
python -m venv .venv
.venv/bin/pip install -e harness -e agriculture-food-systems/farm-disaster-deadline-agent
.venv/bin/farm-disaster-deadline generate --n 32 --seed 157
.venv/bin/farm-disaster-deadline eval --backend mock
```

## Fork it with a program owner

1. Replace fictional identifiers with versioned program and crop/livestock rules.
2. Resolve each clock from an authoritative registry—not from conversational memory.
3. Model event-relative, annual, and coverage deadlines separately.
4. Reuse verified farm records across programs while retaining program-specific evidence.
5. Keep eligibility, loss verification, waivers, and awards with authorized staff.
6. Include clean twins so “preserve everything” does not become indiscriminate escalation.
7. Publish source versions, handoff ownership, recourse, and truthful completion states.

## Inspect and understand

- [`world.py`](src/farm_disaster_deadline/world.py) — balanced events, program clocks, and shared gold
- [`tools.py`](src/farm_disaster_deadline/tools.py) — strict deadline-carrying actions
- [`evaluate.py`](src/farm_disaster_deadline/evaluate.py) — set-exact deadline-map scoring
- [`tests`](tests/test_farm_disaster_deadline.py) — determinism, completeness, boundaries, and counterexamples

## Limits

No real producer, farm, disaster, loss, program, county, policy, deadline, eligibility, or
payment appears here. Passing does not establish USDA compliance, program eligibility,
loss validity, accessibility, fairness, or deployment readiness.
