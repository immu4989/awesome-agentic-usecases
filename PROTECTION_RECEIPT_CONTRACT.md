# Protection Receipt Contract

Most safety and rights workflows fail twice: first when the wrong action is chosen, and
again when a draft, attempt, or handoff is recorded as a completed remedy. The
**Protection Receipt Contract** makes both failures measurable.

It is a public-protection profile of the repository's
[Decision Gate Contract](DECISION_GATE_CONTRACT.md), not a new scoring island. Every run
uses the same strict tool trace and exact metrics, with six domain facts that must remain
joined:

```text
subject identity
  ∧ current applicable rule
  ∧ every required gate
  ∧ live clock and delivery channel
  ∧ protected human owner
  ∧ truthful executed receipt
  = protection that can be proved
```

## The six-part receipt

| Part | The agent must prove | Typical false shortcut |
|---|---|---|
| **Subject** | the exact VIN, product code, billed party, manifest, debt, network event, or worker outcome | a similar case is treated as the same case |
| **Rule** | the current, versioned rule and the specific path it activates | a proposal, old rule, or neighboring rule is transferred |
| **Gates** | every conjunctive prerequisite supported by held evidence | four of five becomes “close enough” |
| **Clock + channel** | the right deadline, recipient, delivery route, and notice | a correct answer arrives too late or to the wrong owner |
| **Authority** | the accountable person remains the final decision-maker or certifier | preparation becomes approval, filing, payment, or safety certification |
| **Receipt** | what actually happened, at its exact stage | draft → filed, appointment → repaired, dispute → won |

The logical AND matters. An agent gets no exact credit for a correct remedy with a false
receipt, a timely report with the wrong subject, or a complete packet that crosses the
human authority boundary.

## Why it is different

Ordinary agent evaluations stop at recommendation quality. This profile follows the
workflow through the tool boundary and then checks whether the durable record agrees with
the executed event. It therefore tests two kinds of public harm at once:

- **protection failure** — the right person, business, worker, or public-safety owner never
  receives the action in time;
- **ledger fiction** — downstream systems believe a remedy, filing, repair, payment,
  correction, or notification occurred when it did not.

## The matched proving ground

The first wave applies one contract to seven different public and economic protections:

| Lab | Transfer trap | Receipt trap |
|---|---|---|
| [Vehicle recall remedy](automotive-safety/vehicle-recall-remedy-coordinator/) | neighboring model year → exact VIN | appointment → repaired |
| [Consumer product recall](consumer-product-safety/product-recall-remedy-coordinator/) | same brand/appearance → recalled unit | intake form → remedy complete |
| [Detention & demurrage invoice](maritime-ports/detention-demurrage-invoice-verifier/) | late container → collectible day-31 invoice | dispute receipt → waiver |
| [Hazardous-waste manifest](environmental-hazardous-materials/hazardous-waste-manifest-coordinator/) | proposed rule → present law | correction → erased history |
| [Debt validation & dispute](consumer-finance-debt/debt-validation-dispute-navigator/) | prior silence → no current dispute right | delivery → debt verified |
| [911/988 outage reporting](telecommunications-emergency/communications-outage-reporting-gate/) | low user-minutes → no special-facility path | draft → certified filing |
| [Workplace severe incident](workplace-safety/severe-incident-reporting-navigator/) | hospital visit → inpatient admission | attempt → accepted report |

Each lab commits 32 balanced synthetic scenarios across eight archetypes, a deterministic
$0 baseline, real-provider smoke evidence, strict tool schemas, exact scorecards, and
reproducible failure cards. The [matched report](PUBLIC_PROTECTION_REPORT.md) compares the
same contract across every industry.

## Fork requirements

Before adapting this contract to production:

1. Name an accountable domain owner and date every policy snapshot.
2. Replace synthetic facts with approved, privacy-minimized records.
3. Remove protected actions from the model's capability surface.
4. Define the exact stages your receipts can prove; never infer a later stage.
5. Add a clean twin and transfer trap for each high-impact exception.
6. Replay the same committed scenarios after every model, prompt, rule, or tool change.

This repository provides a benchmark architecture, not legal, safety, compliance,
financial, medical, or emergency advice.
