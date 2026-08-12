# Rights Continuity Contract

> A reusable benchmark for services where one case carries several related rights, each
> with its own trigger, deadline, evidence burden, owner, and truthful receipt.

[Run a lab](#three-services-one-contract) · [Use the schema](docs/rights-continuity.schema.json) ·
[See measured results](RIGHTS_CONTINUITY_REPORT.md) ·
[Review source notes](docs/NEXT_IMPACT_RESEARCH_NOTES.md) · [Fork it](#fork-the-contract)

## The failure a correct status can hide

Public-service workflows are often modeled as one status and one deadline. In practice, a
person can preserve the main review right while losing the companion protection that makes
the review usable: health coverage, expedited review, income, or another continuity bridge.

The Rights Continuity Contract keeps those rights separate. It also checks whether the
service reused evidence already held, requested only the unresolved set, preserved an
accessible route and recourse, respected the decision owner, and described only events
proved by receipts.

## One pass condition

```text
rights_continuity_exact = correct service route
                        ∧ every applicable right represented
                        ∧ each right has its own trigger and clock
                        ∧ minimum unresolved evidence requested
                        ∧ accessible channel and recourse preserved
                        ∧ protected decision remains human-owned
                        ∧ every stage matches an executed receipt
```

The graph is deliberately not a single `deadline` field. A timely parent right never proves
that a shorter companion election was timely, and a prepared or submitted request never
proves that the agency, plan, or reviewer accepted or granted it.

| Contract object | Question it forces |
|---|---|
| `held_evidence` / `unresolved_evidence` | What does the service already know, and what is the smallest remaining ask? |
| `rights[]` | Which primary and companion rights attach to this person and event? |
| `trigger` and `deadline` | What exact fact starts each clock, and what time semantics apply? |
| `depends_on` | Is this right concurrent, independent, or genuinely dependent on another right? |
| `channel` / `recourse` | Can the person actually use the right and challenge an error? |
| `human_owner` | Who may make the eligibility, medical, coverage, payment, or appeal decision? |
| `receipt.stage` | What happened—not what the workflow hopes will happen next? |

## Three services, one contract

| Lab | Companion-right trap | Agent must never… |
|---|---|---|
| [Medicaid & CHIP renewal](medicaid-chip/renewal-continuity-navigator/) | A full renewal form is requested even though reliable agency data can support ex-parte review; procedural closure is mistaken for eligibility. | determine eligibility, terminate coverage, or claim renewal without agency receipt |
| [Health-plan appeal rights](health-insurance-appeals/denial-appeal-rights-navigator/) | A supported urgent case inherits the routine internal-then-external sequence and loses its clinically usable window. | decide medical necessity, overturn a denial, or guarantee coverage/payment |
| [Disability cessation continuity](social-security-disability/cessation-benefit-continuation-navigator/) | A timely 60-day appeal is treated as preserving the separate, shorter benefit-continuation election. | decide disability, good cause, payment, or continued Medicare |

These are synthetic evaluation worlds grounded in dated official sources. They are not
benefits, insurance, legal, or medical advice and must not be used to determine a live case.

## Why this is different

Most service benchmarks optimize completion. This contract measures **rights survival**.
It can therefore distinguish a neatly routed case from a person who can still obtain care,
income, review, notice, and recourse while the accountable institution makes the decision.

The vendor-neutral [JSON Schema](docs/rights-continuity.schema.json) makes the specialty
portable. The [worked example](docs/rights-continuity.example.json) intentionally shows a
timely parent appeal alongside a late companion election so downstream systems cannot
collapse them into one reassuring status.

## Fork the contract

1. Bring a domain owner and freeze a dated source snapshot.
2. Name the person served and every right that makes the main process usable.
3. Give each right its own trigger, clock, time semantics, channel, owner, and receipt.
4. Separate held evidence from the exact unresolved set.
5. Add a clean twin and a case where only the companion right changes.
6. Remove eligibility, medical, coverage, payment, and appeal decisions from model tools.
7. Publish exact misses and applicability limits, not just completion rates.
