# Independent Reproduction Exchange research notes

Verified: **2026-08-29**. These notes explain the primary-source basis and narrow claims behind the
blind reproduction, provenance, and federated-publication protocol. They are not NIST, government,
in-toto, SLSA, GitHub, or Sigstore guidance or endorsement.

## 1. Why the old Boolean was insufficient

The Evidence Mesh 0.1 allowed a contributor to declare `independent_reproduction: true`. That flag
was transparent but did not bind the claim to a prior challenge, a held answer set, a source
contract, a receipt, or distinct roles. Version 0.2 removes the Boolean. Advancing the public count
now requires a recomputable adjudication that binds the exact artifact bytes and kind.

This still does not make independence cryptographic. A hash can show that three role commitments
differ; it cannot establish corporate control, funding, contracting, employment, shared personnel,
or whether a declared relationship is complete. The protocol therefore labels this boundary
`relationship_evidence_human_reviewed` and fixes `independence_cryptographically_proved` to false.

## 2. Valid, reproducible, contamination-aware evaluation

Primary sources:

- [NIST AI 800-2 initial public draft](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.800-2.ipd.pdf)
- [NIST: Towards Best Practices for Automated Benchmark Evaluations](https://www.nist.gov/news-events/news/2026/01/towards-best-practices-automated-benchmark-evaluations)
- [NIST AITE announcement](https://www.nist.gov/news-events/news/2026/07/announcing-nists-artificial-intelligence-technology-evaluation-aite)
- [NIST CAISI: Cheating on AI Agent Evaluations](https://www.nist.gov/caisi/cheating-ai-agent-evaluations)
- [NIST CAISI: four prevention and detection practices](https://www.nist.gov/caisi/cheating-ai-agent-evaluations/4-practices-detecting-and-preventing-evaluation-cheating)
- [NIST: Building Evaluation Probes into Agentic AI](https://www.nist.gov/programs-projects/building-evaluation-probes-agentic-ai)

NIST's automated-evaluation work emphasizes validity, transparency, and reproducibility across
objective definition, implementation, execution, analysis, and reporting. AITE describes blind
data in a sequestered environment as a way to reduce contamination. CAISI separately identifies
solution contamination and grader gaming, recommends preserving held-out material, declaring
affordances and restrictions such as network access, reviewing transcripts, and publishing enough
configuration and review information for scrutiny.

The Exchange maps those ideas into an offline public protocol:

1. the issuer hashes an oracle before publishing a challenge that structurally cannot contain gold
   outcomes or gold actions;
2. the challenge fixes network, live-target, external-walkthrough, tool, and oracle affordances;
3. the reproducer freezes responses, environment, method, sharing declarations, and a challenge
   digest before reveal;
4. a separate reviewer records blinding, relationship-evidence, affordance, and transcript review;
5. reveal reconstructs the exact committed source suite and deterministically scores the response.

**Premise check:** a public Git repository cannot keep a committed example secret. The included
walkthrough is therefore labeled revealed training material and `protocol_demonstration`. A real
issuer must generate a new challenge and keep the oracle in a separate approved location until the
submission is frozen.

## 3. Provenance and signed identity are different layers

Primary sources:

- [in-toto Statement v1](https://in-toto.io/Statement/v1)
- [SLSA provenance 1.2](https://slsa.dev/spec/v1.2/provenance)
- [GitHub Artifact Attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)
- [Sigstore attestation verification](https://docs.sigstore.dev/cosign/verifying/attestation/)

The in-toto statement layer binds an immutable subject digest to a typed predicate. SLSA uses
provenance to describe where, when, and how an artifact was produced. The Exchange emits an in-toto
v1 statement whose subject digest is the exact `receipt.json` bytes and whose predicate binds the
challenge, oracle commitment, source suite, submission, and role-review result.

That local statement is unsigned and says so in machine-readable form. It proves no GitHub account,
workflow, person, or organization produced the pack. A publisher that needs a signed workflow
identity should separately create and verify a GitHub Artifact Attestation or Sigstore attestation.
The local verifier intentionally does not simulate a signature or trust root.

## 4. Federated learning without organizational ranking

The federation command accepts only complete packs that independently recompute. It deduplicates
the challenge, producer commitment, and receipt tuple. Only adjudications whose reviewed role gate
reaches `independence_reviewed` can enter an aggregate cell. Maintainer demonstrations remain
visible only in the demonstration count.

Public cells smaller than three are suppressed and report neither their count nor measurements.
Role commitments never enter the public report. Measurements stay within one challenge; unlike
challenge families are not combined into a universal score. These constraints reduce incentives
for league tables and some obvious reidentification paths.

**Premise check:** a minimum cell size of three is not differential privacy, anonymity, or a formal
disclosure-risk guarantee. It does not authorize publication of operational security evidence. A
responsible organization must perform its own privacy, security, records, legal, contracting, and
disclosure review before contributing a pack.

## 5. Claims this release deliberately does not make

The protocol does not prove:

- that the oracle was never disclosed or memorized;
- that a submitted transcript is complete or authentic;
- the legal identity or actual independence of any role;
- that a benchmark predicts production behavior or transfers to another environment;
- field effectiveness, safety, compliance, certification, procurement fitness, government
  endorsement, an Authority to Operate, or authority to deploy or change a system.

Those limits are machine-readable in the adjudication and public report, visible on the live page,
and exercised in tests so a convenient reference run cannot silently cross the evidence boundary.
