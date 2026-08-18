# Federal Mission Assurance research notes

Verified: **2026-08-18**. These notes explain the public-source basis and deliberately
narrow claims behind the Federal Mission Assurance Profile v0.1 and the Federal AI
Acquisition Performance Gate.

They are research notes—not agency guidance, a legal interpretation, procurement advice,
or a representation that the profile satisfies an agency's implementation requirements.

## 1. OMB M-25-21: use, governance, and public trust

Primary source: [OMB M-25-21](https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-21-Accelerating-Federal-Use-of-AI-through-Innovation-Governance-and-Public-Trust.pdf).

The profile maps the memorandum's high-impact AI practices into visible evidence fields:

- pre-deployment testing and risk mitigation;
- an impact assessment tied to intended purpose, expected benefit, affected people, data,
  privacy, civil rights, civil liberties, and cost;
- independent review and accountable risk acceptance;
- ongoing monitoring, human oversight, intervention, training, and failsafe;
- human review, appeal, remedy, and feedback paths; and
- reassessment and safe discontinuation when required practices cannot be met.

**Premise check:** putting a person somewhere in the workflow does not automatically make
the AI low impact. The use-specific effect still must be assessed. The Studio therefore
defaults the determination to `uncertain` and never infers `no` from a human-review field.

## 2. OMB M-25-22: acquiring AI

Primary source: [OMB M-25-22](https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-22-Driving-Efficient-Acquisition-of-Artificial-Intelligence-in-Government.pdf).

The acquisition controls focus on evidence that can survive the acquisition lifecycle:

- cross-functional participation;
- measurable performance requirements and realistic testing;
- government data, intellectual-property, privacy, and training-use terms;
- open formats, portability, knowledge transfer, licensing, and exit;
- pricing and lifecycle-cost visibility; and
- post-award monitoring and performance evidence.

**Premise check:** a product demonstration or generic benchmark is not automatically
evidence of fitness for an agency's intended environment. That transfer failure is the
featured benchmark's cleanest counterexample.

## 3. GAO-26-107859: reusable acquisition lessons

Primary source: [GAO-26-107859](https://www.gao.gov/products/gao-26-107859), published
2026-04-13.

GAO reported that federal agencies more than doubled reported AI use from 2023 to 2024 and
identified recurring acquisition challenges involving access to expertise, requirements and
contract terms, government data and intellectual-property protections, early and continuous
testing, pricing, and cost. GAO also found that selected agencies were not systematically
collecting AI acquisition lessons for reuse.

The profile's portable risk register, acquisition acceptance plan, source snapshot, and
manifest are designed to make lessons inspectable and reusable. They do not represent
submission to, compatibility with, or endorsement by a GSA or agency repository.

## 4. NIST AI RMF and AIRC

Primary sources: [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework) and
[NIST AI Resource Center](https://airc.nist.gov/).

The crosswalk uses the stable GOVERN, MAP, MEASURE, and MANAGE function names as organizing
labels. The detailed NIST material is voluntary, evolving guidance. The policy snapshot is
versioned so that later NIST revisions can be reviewed rather than silently treated as
equivalent.

**Premise check:** an RMF mapping is not a NIST certification. The UI and exported pack never
use a certification badge or composite compliance percentage.

## 5. Authority and cryptographic boundaries

The acquisition lab separates evidence preparation from final source selection. The agent
cannot select or finally rank an offeror, make a responsibility or best-value determination,
accept residual risk, obligate funds, or award a contract.

The pack manifest uses SHA-256 only to detect byte changes. It does not prove authorship,
identity, independent reproduction, source quality, policy compliance, or government approval.
Those claims remain `false` in the machine-readable manifest.

## 6. Public-site data boundary

Federal Mission Studio makes no remote request other than loading its own committed static
data. It does not use browser storage. It scans locally for common credential, Social
Security number, email, phone, and payment-card shapes and enables export only for profiles
marked public, without PII, and synthetic-or-public-only.

Pattern matching is a guard, not a data-loss-prevention guarantee. Controlled, classified,
procurement-sensitive, source-selection, agency-sensitive, or personally identifiable
information belongs only in an agency-approved environment.

## 7. Future review questions

Before v0.2, domain reviewers should challenge:

1. whether every mapped control preserves the source's scope and conditional language;
2. whether agency-specific implementation evidence needs an extension mechanism;
3. whether public and internal redacted pack variants can share a verifiable relationship
   without leaking sensitive facts;
4. whether independent-review identity should use signed attestations; and
5. how policy-source supersession should be represented without deleting the historical
   snapshot that governed an earlier evaluation.
