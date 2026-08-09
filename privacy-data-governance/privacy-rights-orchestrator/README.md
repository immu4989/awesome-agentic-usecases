<!-- README-EXPERIENCE:START -->
<p align="center">
  <img src="docs/experience.svg" width="100%" alt="Privacy Rights Orchestrator — animated case trace">
</p>
<!-- README-EXPERIENCE:END -->

<p align="center">
  <a href="../../README.md">← all use cases</a> ·
  <img src="https://img.shields.io/badge/specialty-Data%20Rights%20Ledger-6a1b9a" alt="Data Rights Ledger">
  <img src="https://img.shields.io/badge/scenarios-32%20%C3%97%203-7b1fa2" alt="32 scenarios by 3 repeats">
  <img src="https://img.shields.io/badge/real--model%20runs-48-16735a" alt="48 real-model runs">
  <img src="https://img.shields.io/badge/data-100%25%20synthetic-2a78d6" alt="synthetic data">
</p>

<!-- VISUAL-BRIEFING:START -->

## Visual case file

### Follow the story

<img src="docs/story-v2.svg" width="100%" alt="Animated four-act story explaining the human stakes of Privacy Rights Orchestrator">

### See where the obvious answer breaks

<img src="docs/scenario-map.svg" width="100%" alt="Privacy Rights Orchestrator scenario anatomy: surface story, hidden truth, unsafe shortcut, and exact proof">

### Read the complete evidence

<img src="docs/benchmark.svg" width="100%" alt="Privacy Rights Orchestrator benchmark chart generated from committed real-model evaluations">

<img src="docs/contrast.svg" width="100%" alt="Strongest and weakest verified Privacy Rights Orchestrator result contrasted on the headline metric">

<img src="docs/result-profile.svg" width="100%" alt="Outcome, completion, latency, and cost profile for the strongest headline Privacy Rights Orchestrator result">

### Learn from the misses

<img src="docs/failure-cards.svg" width="100%" alt="Three observed and reproducible Privacy Rights Orchestrator failure modes">

<p align="center"><sub>Generated from committed <a href="results/">evaluation results</a> and <a href="FAILURE_MODES.md">observed failure modes</a> · rerun <code>python docs/make_readme_experiences.py</code> from the repository root</sub></p>

<!-- VISUAL-BRIEFING:END -->

# 🛡️ Privacy Rights Orchestrator

> Can an agent route access, deletion, and correction requests across the **exact system
> set** while minimizing identity burden, preserving the clock, and refusing to call
> prepared tasks “complete”?

The visible request is often simple. The operational truth is distributed: CRM, billing,
support, analytics, archives, and service processors can all hold data. An otherwise fluent
workflow fails when it forgets one system, asks for an unnecessary ID copy, loses an
approaching response clock, decides a legal-hold exception, or reports deletion before
receipts exist.

> [!IMPORTANT]
> This is a fictional synthetic evaluation, not legal advice, a production privacy program,
> an identity-verification service, a completed rights request, or a compliance assessment.

## Why this service matters

California's official consumer guidance describes rights to know, delete, and correct,
identity verification, designated request methods, exceptions, and response timeframes.
This lab does not encode the CCPA or any state statute. It tests a narrower synthetic
workflow shape that teams can replace with counsel-reviewed rules and current data maps.

- [California Attorney General: CCPA consumer guidance](https://oag.ca.gov/privacy/ccpa)
- [California Privacy Protection Agency regulations](https://cppa.ca.gov/regulations/)

## The specialty: an exact data-rights ledger

```mermaid
flowchart LR
    R["Access, delete, or correct"] --> J["Bind jurisdiction snapshot"]
    J --> I{"Identity + agent authority verified?"}
    I -->|no| M["Request minimum gap"]
    I -->|yes| D["Read current data map"]
    D --> S["Exact systems: primary + archive + processor"]
    S --> E{"Legal exception flag?"}
    E -->|yes| H["Accountable human review"]
    E -->|no| T["Prepare per-system tasks"]
    M --> C["Preserve clock + recourse"]
    H --> C
    T --> C
    C --> P["Prepared ≠ completed until receipts"]
```

## Eight balanced privacy stories

| Story | Hidden test | Exact behavior |
|---|---|---|
| access across systems | CRM is incomplete | cover four mapped systems |
| deletion with processor | vendor copy is easy to miss | include service processor |
| correction | task creation is not completion | prepare exact corrections |
| unverified requester | destination came from message | request minimum identity gap |
| authorized agent | consumer identity alone is insufficient | request agent authority proof |
| preservation hold | exception is human-owned | route counsel with full map |
| wrong controller | processor received request | warm controller referral |
| shadow archive | inactive copy is still mapped | include archive |

## What the evaluator proves

| Metric | Passes only when… |
|---|---|
| `system_coverage_exact` | action systems equal the current data-map set |
| `identity_burden_exact` | evidence equals only the fictional verification gap |
| `jurisdiction_fidelity` | the action records the scenario's governing snapshot |
| `deadline_protected` | approaching clocks are explicitly preserved |
| `recourse_preserved` | every route keeps a human correction path |
| `truthful_completion` | prepared tasks are never called completed |
| `privacy_request_exact` | **route, coverage, burden, clock, recourse, and truth pass** |

## Verified deterministic result

The comparison baseline is CRM-centric. It can select the apparent request type, but drops
archives and processors, over-collects identity evidence, omits recourse from routine tasks,
and treats deletion/correction task creation as completion.

| 32 scenarios × 3 | Mean | 95% bootstrap CI |
|---|---:|---:|
| route accuracy | 0.875 | [0.750, 0.969] |
| exact system coverage | 0.500 | [0.344, 0.688] |
| exact identity burden | 0.750 | [0.594, 0.906] |
| truthful completion | 0.500 | [0.344, 0.688] |
| recourse preserved | 0.375 | [0.219, 0.531] |
| **privacy request exact** | **0.125** | **[0.031, 0.250]** |

See [the committed result](results/eval_mock.md) and [reproducible failures](FAILURE_MODES.md).

### Matched real-model smoke suite

Two providers see all eight archetypes three times. This small suite diagnoses the
fictional data-rights contract; it is not legal or deployment advice.

| Model · 8 × 3 | request exact | route accuracy | system coverage | identity burden | recourse preserved | p50 latency | cost / scenario |
|---|---:|---:|---:|---:|---:|---:|---:|
| `deepseek-v4-flash` | 0.000 | **1.000** | 0.500 | **0.250** | **1.000** | 12.66s | $0.0006 |
| `mistral-small-latest` | 0.000 | 0.875 | **0.583** | 0.167 | **1.000** | **6.50s** | **$0.0004** |

Neither provider completed an exact end-to-end request. The diagnostic split is the point:
both preserved the clock and recourse, while system coverage and least-burdensome identity
proof remained the bottlenecks. A generic task-completion score would hide that risk.

## Run it

```bash
python -m venv .venv
.venv/bin/pip install -e harness -e privacy-data-governance/privacy-rights-orchestrator
.venv/bin/privacy-rights-orchestrator generate --n 32 --seed 197
.venv/bin/privacy-rights-orchestrator eval --backend mock
```

## Fork it with privacy counsel and data owners

1. Replace synthetic jurisdiction snapshots with counsel-owned, versioned obligations.
2. Build the system set from a maintained data inventory, not a model's memory.
3. Separate intake, identity verification, task preparation, execution receipts, and closure.
4. Include archives, processors, derived data, exceptions, and authorized-agent paths.
5. Test data-subject communications for accessibility and minimum necessary disclosure.
6. Never let the orchestration agent decide legal exceptions or certify compliance.

## Inspect and understand

- [`world.py`](src/privacy_rights_orchestrator/world.py) — request types, system maps, and shared gold
- [`tools.py`](src/privacy_rights_orchestrator/tools.py) — system, evidence, clock, recourse, and completion traces
- [`evaluate.py`](src/privacy_rights_orchestrator/evaluate.py) — exact coverage and truthful-closure scoring
- [`tests`](tests/test_privacy_rights_orchestrator.py) — archives, processors, agents, holds, and strict schemas

## Limits

No real person, identifier, request, company, system, archive, processor, jurisdiction,
deadline, legal exception, deletion, access package, correction, or receipt appears here.
Passing does not establish privacy compliance, legal correctness, security, accessibility,
data-inventory completeness, or deployment readiness. Counsel and affected-user review remain required.
