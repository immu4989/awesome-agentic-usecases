# Changelog

## 1.6.0 - 2026-08-30

- Added the Agent Release Gate: exact component snapshots, before/after impact selection,
  fail-closed thresholds, protected-change approval records, deterministic evidence packs,
  unsigned in-toto provenance, and an experimental non-certifying OSCAL Assessment Results export.
- Opened four answer-free Fork-to-Reproduce challenges with 26 tasks, hidden-oracle commitments, safe
  templates, a manual attested-submission workflow, and explicit human review of independence.
- Added the Agent Incident Exchange with clean-twin regression bindings and SARIF, OpenVEX, plus
  explicitly experimental CSAF and OCSF bridge exports.
- Added a ten-source Policy Freshness Radar that uses stable byte or visible-text fingerprints,
  maps each official source to affected repository paths, and opens one human-review issue without
  interpreting policy or modifying a lab.
- Rebuilt the live entry experience around a quieter evidence-operations surface and reduced the
  primary navigation from a long feature inventory to six clear routes.

Notable changes to the repository. Versions follow [semantic versioning](https://semver.org/):
the harness API is what is versioned; use cases are additive.

## 1.5.0 - 2026-08-27

- **AAU Evidence Commons and Impact Capsules** — `aau evidence validate` binds a reviewed public
  suite, aggregate agent receipt, privacy-bounded human comparator, predeclared public-value
  measures, bounded outcome observation, and independent reproduction. Status is artifact-derived;
  missing evidence, transfer conditions, human authority, sources, and limitations remain visible
  without a trust score, leaderboard, certification, endorsement, or deployment claim.
- **Portable, tamper-evident impact packs** — `aau evidence pack` creates a non-overwriting bundle
  containing the capsule, derived comparison, referenced public artifacts, README, and SHA-256
  manifest; `aau evidence verify` detects byte and manifest drift. Strict public-value and
  reproduction records reject causal-label inflation, false independence verification, unsafe
  paths, private-data claims, and inconsistent metrics.
- **Three honest partner pilots and a live inspector** — FOIA routing, accessible digital-service
  remediation, and small-nonprofit grant obligations now have source-grounded measurement plans,
  protected human authority, safe contribution routes, and interactive evidence-chain views. Their
  historical eight-case receipts lack suite hashes, so each is labeled `scenario_ids_only` and
  makes a fresh hash-bound rerun the first public gap. No human or field result is fabricated.

## 1.4.0 - 2026-08-27

- **Human Baseline Lab** — `aau baseline prepare` turns any reviewed public or synthetic AAU suite
  into a non-overwriting blinded study pack with a participant-visible task file, separate local
  answer key, identifier-free session contract, human-protection checkpoint, and SHA-256 manifest.
  `aau baseline summarize` publishes aggregate exactness, Wilson uncertainty, abstention, median
  and p90 task time, confidence calibration, per-scenario agreement, and Fleiss' kappa while
  excluding participant identifiers and raw responses.
- **Same-suite human/agent evidence without worker ranking** — an optional public agent receipt
  adds a descriptive comparator only after suite hashes and scenario coverage match. Protocol mock
  receipts, unreviewed human-observed sessions, duplicate session ids, missing cases, unsafe
  fields, manifest drift, and inconsistent metrics fail closed. The contract prohibits hiring,
  performance-management, replacement, causal-benefit, certification, and deployment claims.
- **Zero-upload blinded browser practice** — the homepage now offers eight synthetic public-service
  routing tasks, hides the oracle until completion, measures task time and confidence only in the
  tab, and downloads an aggregate individual practice receipt. Five generated reference sessions
  test the protocol but are explicitly never presented as people. Three schemas, dated NIST/OMB/
  HHS research notes, a generated visual, focused tests, and CI parity checks complete the release.

## 1.3.0 - 2026-08-23

- **Starter → Verified Community Evidence Loop** — `aau submit` builds a non-overwriting public
  contribution pack from an Agent Evidence Starter and real command/endpoint receipts. It emits a
  strict metadata record, reviewed synthetic suite, aggregate receipts, deterministic evidence
  checks, sensitive-data scan, source ledger, checklist, original SVG share card, and SHA-256 byte
  manifest; `aau submit --validate` recomputes the entire public claim.
- **Artifact-derived trust without badge inflation** — cumulative Generated, Domain reviewed,
  Reproduced, and Verified levels require progressively stronger committed artifacts. Mock
  receipts, extra/private fields, inconsistent metrics, unsafe paths, symlinks, manifest drift,
  stale checks, and common sensitive-data patterns fail closed. The boundary explicitly excludes
  identity verification, certification, endorsement, production approval, and deploy authority.
- **Zero-upload Contribution Desk and showcase** — the homepage now inspects Starter files and up
  to twelve receipts locally, runs twelve sharing gates, derives the same evidence ladder, exports
  a contribution ZIP, and displays three clearly labeled maintainer reference packs. Dedicated
  contribution docs, schema, pull-request template, tests, and CI drift checks complete the loop.

## 1.2.0 - 2026-08-23

- **Agent Evidence Starter** — `aau init` now atomically generates an eleven-file, provider-neutral
  evaluation project around an existing command or local HTTP agent: reviewed synthetic cases,
  exact outcomes, forbidden-action scoring, protected human authority, two adapters, a regression
  test, a privacy-bounded first receipt, immutable least-privilege CI, receipt policy, original
  evidence visual, and SHA-256 origin manifest.
- **Fail-closed starter doctor** — `aau doctor PATH` validates the suite's sharing declarations,
  accountable boundary, adapter structure, aggregate receipt, pinned package/actions, required
  files, safe manifest paths, symlink boundaries, and template drift. It never executes project
  code unless the user explicitly adds `--run-adapter`. Legitimate customization warns; weakened
  safety contracts fail. Starter commands work from a public package install outside a checkout.
- **Zero-upload browser builder** — the repository homepage now offers the same three starter
  shapes through a four-step local wizard with ten safety gates, a common-sensitive-data scan,
  live evidence circuit, local SHA-256 manifesting, and an in-tab ZIP export. Form data is not
  uploaded, persisted, or transmitted. Three complete generated examples and CI parity checks
  keep the Python and browser contracts synchronized.

## 1.1.1 - 2026-08-23

- **Public package onboarding** — the PyPI-rendered package guide now leads with
  `python -m pip install aau-harness`, separates public use from editable repository
  development, and links the live tokenless publishing identity and provenance-backed release.
- The repository landing page now carries a dynamic PyPI version badge and a copyable path for
  evaluating an existing command or HTTP agent without changing frameworks.

## Unreleased

- **Artifact-derived independent reproduction ledger** — the public count now equals the number of
  accepted Exchange packs that recompute to `independence_reviewed`, bind the current challenge,
  and have unique producer/submission commitments. Missing packs, path escapes, symlinks, digest
  drift, protocol demonstrations, duplicate producers, and manually inflated counts fail closed.
  Oracle reveal closes that challenge and limits it to one blind result; another run requires new
  suite and oracle commitments.
- **Honest zero and scalable intake** — the empty registry renders as zero on the live release
  surface while four challenges and 26 tasks remain open. The new A2A-to-MCP relay challenge is
  available in the issue intake; human-reviewed relationships remain explicitly non-cryptographic.
- **Non-mutating acceptance planner** — a maintainer command recomputes the reviewed Exchange pack,
  simulates challenge close and registry insertion, validates the complete proposed state, and
  writes checksummed proposed files without copying the revealed oracle or changing the checkout.
- **Revision-locked public challenge** — the original portable-agent challenge is retained as
  closed byte-history, while its open successor pins A2A `v1.0.1`, MCP `2026-07-28`, and the dated
  NIST NCCoE paper. Open challenges with mutable GitHub branch URLs now fail campaign verification.
- **Registry-driven fork intake** — the manual GitHub workflow and issue form no longer maintain
  stale challenge choice lists. `list-open` derives the current four IDs from the verified campaign;
  unknown and closed IDs fail at the same build boundary used locally and in forks.
- **Challenge-to-source freshness closure** — the exact 406,665-byte NIST NCCoE agent-identity paper
  joins the watched registry, and NIST/MCP/A2A owner paths now name the current portable and relay
  challenges. Ten source baselines map to ten revision bindings with zero inferred policy meaning.
- **One-command reproduction workspace** — `prepare` creates editable response and metadata files
  around an oracle-free, manifest-bound `.aau` origin; `check-prepared` detects protected-byte drift,
  symlinks, source-suite/challenge changes, closure, missing tasks, and unfinished templates before
  users spend a GitHub Actions run.

- **Privacy-bounded Cross-protocol Authority Trace** — the exact Authority Relay receipt now
  projects into 25 synthetic traces and 52 spans using W3C-shaped trace context and a pinned
  OpenTelemetry semantic-convention basis. All 23 blocked cases stop before MCP dispatch; only the
  two allowed twins receive client spans.
- **Content-minimized incident evidence** — raw subjects, actors, tasks, delegations, tenants,
  routes, tools, resources, scopes, and audiences become SHA-256 references. Prompts, messages,
  arguments, results, tokens, `tracestate`, and baggage are prohibited; attribute count and length
  are bounded. The export explicitly does not claim anonymity, live capture, OTLP, conformance,
  security, compliance, certification, deployment approval, or ATO.

- **Current Assurance Matrix Action** — the reusable local GitHub Action can now run the MCP
  `2026-07-28`, A2A `1.0`, and cross-protocol relay gates through project-owned answer-blind
  adapters. It emits three receipts, a 52-span privacy-bounded trace, privacy-safe SARIF, a 58-case
  aggregate receipt, a GitHub job summary, and a SHA-256 manifest, then recomputes all eight pack
  files. Workspace escapes, symlinks, overwrite, extra files, receipt drift, summary drift, and
  manifest drift fail closed.
- **Hardened CI adoption path** — adapter inputs flow through quoted environment variables, the
  example grants read-only repository access, excludes secrets, pins artifact upload by full SHA,
  and leaves retention under the caller's control. Passing remains profile-specific recorded
  evidence rather than production identity, authorization, conformance, certification, or ATO.
- **Failure-preserving CI diagnostics** — an evidence mismatch still fails the Action, but only
  after its receipts, trace, SARIF, summary, and manifest are verified and the summary is appended.
  SARIF carries gate/case ids, actual decisions, and reason codes without raw requests. Structural
  or tamper failures remain a separate hard-error path and never receive a valid-evidence summary.

- **Cross-protocol Authority Relay Gate** — a new answer-blind compiler tests the unstandardized
  application boundary where an authenticated A2A task becomes an MCP tool call. Two legitimate
  routes and twenty-three isolated violations cover subject/actor/task continuity, tenant and Agent
  Card binding, delegation replay/depth/window, policy epoch, exact route/tool/resource/scope,
  MCP audience, token passthrough, monitoring, and human approval. The reference command adapter
  is 25/25 exact with zero unsafe allows and zero legitimate blocks.

- **A2A 1.0 Interface & Authorization Delta Gate** — a strict offline compiler now creates two
  legitimate twins and fifteen one-change violations for `A2A-Version: 1.0`, selected
  `AgentInterface` version/binding/endpoint/tenant, Agent Card drift, PascalCase JSON-RPC methods,
  per-operation authorization, application authority, and caller-scoped task access. Its
  answer-blind command adapter is 17/17 exact with zero unsafe allows and zero legitimate blocks.
- **Immutable A2A standards evidence** — the Policy Freshness Radar no longer treats mutable A2A
  `main` bytes as a stable evaluated revision. It pins official specification release `v1.0.1`,
  preserves protocol compatibility revision `1.0`, and binds the exact source digest to the new
  suite and receipt without claiming protocol conformance, security, or deployment approval.

- **Agent Capability & Authority Bill of Materials** — `aau bom` now inventories models, tools,
  operations, resource scopes, expiring authority leases, delegation, revocation, data routes,
  accountable ownership, controls, and evidence in one strict public contract. Cross-reference
  violations, unsafe sharing claims, and consequential authority without a human boundary fail
  closed.
- **Directional authority-diff and interoperable evidence** — the reference pair finds five
  widening facts without a trust score, blocks removed human approval, compares lease duration
  instead of producing rotation noise, exports an officially schema-validated CycloneDX 1.7
  projection, and emits a deterministic pack with unsigned in-toto byte bindings.
- **Live blast-radius view** — the release-operations surface now renders the AABOM inventory and
  derived widening findings from committed evidence. Research notes ground the profile in current
  NIST, NCCoE, CISA, CycloneDX, and in-toto primary sources while explicitly excluding standards
  endorsement, live authorization, verified identity, safety, compliance, deployment, and ATO
  claims.
- **Proposal-only Least-Authority Planner** — `aau bom plan-reduction` compares an exact AABOM with
  privacy-bounded public, synthetic, or authorized aggregate event metadata. It identifies
  unobserved operations and scopes, excludes blocked/error attempts from legitimate-use evidence,
  demands six next proofs for every candidate, emits no executable policy, and automatically
  removes zero permissions. `verify-reduction-plan` recomputes the proposal from exact input
  digests; cross-reference escapes, false coverage counts, and noncontiguous runs fail closed.
- **Inventory-derived Authority Conformance Compiler** — `aau bom generate-conformance` compiles
  every declared authority/tool intersection into legitimate clean twins plus single-boundary
  time, revocation, delegation, approval, operation, and scope violations. The command protocol
  withholds expected answers and never executes tools; the reference candidate produces 19 cases,
  19/19 exact results, zero unsafe allows, and zero legitimate blocks.
- **Recomputable asymmetric evidence** — `run-conformance` emits a BOM- and suite-bound receipt;
  `verify-conformance` detects stale suites, missing/duplicate coverage, identity or digest drift,
  malformed adapter answers, and altered exactness or failure counts. Strict readable schemas,
  fail-closed tests, CI parity, a public adapter, and a live evidence view make the experiment
  forkable without presenting it as production enforcement, certification, compliance, or an ATO.
- **Standards Compatibility Ledger** — the policy radar 1.1 registry now names the exact revision
  behind every watched source. A strict nine-binding ledger maps seven experimental profiles to
  their reviewed source fingerprint, evaluated revision, evidence paths, and nonconformance
  boundary; the deterministic report distinguishes source-lock change, migration required, review
  due, and evidence ready without a trust score.
- **No silent MCP currency claim** — the radar now watches the official MCP `2026-07-28`
  authorization revision and openly reports that Portable Agent Assurance still targets
  `2025-06-18`. Weekly review combines source drift and revision impact in one issue; accepting a
  new baseline cannot automatically relabel implementation evidence, migrate a fixture, interpret
  policy, claim conformance, certification, compliance, or approval.
- **MCP 2026-07-28 Authorization Delta Gate** — a strict offline compiler now creates two
  legitimate and fourteen single-delta recorded cases for self-describing method/tool headers,
  response issuer validation, issuer-bound credentials, exact resource/audience binding, scope
  minimization and union-preserving step-up, token passthrough, and query transport. A public
  answer-blind command adapter returns 16/16 exact with zero unsafe allows or legitimate blocks.
- **Revision gap closed with bounded evidence** — the compatibility ledger now aligns the Portable
  Agent Assurance binding to `2026-07-28` through the exact suite and receipt while preserving the
  older 0.1 envelope wire contract. The gate executes no OAuth flow or tool and does not claim full
  MCP/OAuth implementation, conformance, security, interoperability, compliance, certification, or
  deployment approval.

- **Portable Agent Assurance Envelope** — a dependency-free offline verifier binds a deliberately
  public synthetic workload credential to its accountable operator, short-lived authority lease,
  task, policy epoch, exact MCP/A2A operation, destination, peer, delegation ceiling, monitor
  state, and evidence digests. Eighteen fixtures preserve two legitimate twins and test sixteen
  identity, credential, authority, protocol, and delegation collisions with exact reason codes.
- **Portable evidence and reusable CI** — deterministic receipts add a result chain,
  privacy-bounded OpenTelemetry-compatible events, an unsigned in-toto Statement v1, and a
  fail-closed byte manifest. A repository-local composite GitHub Action evaluates, verifies,
  packages, and re-verifies a caller's envelope and suite without remote action dependencies.
- **Experimental NIST TEVV-Athlon profile** — a machine-readable profile maps six Metrology Blocks,
  three Events, four Tools, and seven byte-verified artifacts to the four stages in the NIST AI 200-2
  initial public draft. Planned outside work, revealed reference material, and absent independent
  reproduction stay visible. The evidence-backed public-comment draft is explicitly unsubmitted.
- **Live Agent Assurance lab** — the homepage now presents the assurance chain, exact collision
  matrix, four TEVV stages, visible gaps, and a zero-upload structural envelope inspector from
  generated committed evidence rather than handwritten counts.

- **Blind Independent Reproduction Exchange** — a dependency-free CLI now issues answer-free
  defensive challenges against a committed hidden oracle, freezes a public-safe outside submission,
  and requires separate role/relationship, blinding, affordance, and transcript review before
  reveal. The deterministic public pack recomputes the benchmark receipt, adjudication, in-toto v1
  byte binding, and manifest. It explicitly separates machine-verifiable integrity from
  human-reviewed organizational independence and never presents its unsigned local statement as a
  signed identity attestation.
- **Evidence Mesh 0.2 and privacy-bounded federation** — `independently_reproduced` can no longer
  be advanced by a Boolean declaration. The mesh requires a supported adjudication bound to the
  exact artifact bytes and kind; the Outcomes Observatory validates the derived role boundary.
  Federation rejects duplicates, excludes protocol demonstrations, suppresses challenge cells
  smaller than three, omits role commitments, preserves unlike measurements, and produces no
  vendor, agency, organization, or model ranking.
- **Live Reproduction Desk** — the Collective Cyber Defense page now explains the four-party
  challenge/run/review/reveal evidence chain, shows the exact requirements that would unlock the
  first accepted outside reproduction, and preflights an adjudication locally with Web Crypto. The
  committed revealed walkthrough correctly stays `protocol_demonstration`; the public count remains
  zero until an actual outside pack passes review.

- **Verified Fix Commons** — three public-safe fix contracts now require a vulnerability
  regression, legitimate twin, service-continuity budget, rollback evidence, source binding, and
  accountable human owner. The dependency upgrade, least-privilege configuration, and
  essential-service compensating-control fixtures emit deterministic hash-chained receipts plus
  OpenVEX-style and SARIF exports without claiming production exploitability or effectiveness.
- **Agent Containment Drill Runner** — a 21-event synthetic drill measures pause, parent
  revocation, delegated-authority revocation, queued-work cancellation, monitor loss, evidence
  mutation, blocked unauthorized restart, and evidence-backed human recovery on separate clocks.
- **Essential-Service Defender-in-a-Box** — a zero-network CLI and zero-upload browser workbench
  route public/synthetic or authorized inventory evidence to patch, compensating control,
  investigation, or not-affected review. Treatment gates require exact applicability, continuity,
  rollback, evidence, and accountable approval; no scan or automatic change occurs.
- **Frontier Defensive Capability Benchmark** — 20 safe, provider-neutral tasks cover
  vulnerability prioritization, secure code review, identity and authorization, containment and
  recovery, and essential-service continuity. Exactness, citations, human boundaries, and service
  preservation remain separate; the committed 20/20 reference fixture is explicitly not a model
  or vendor result.
- **Cyber Defense Evidence Mesh and Public Defense Outcomes Observatory** — six public-safe
  reference artifacts now flow through a hash-manifested evidence index, reusable control
  fingerprints, and an experimental OpenTelemetry naming bridge. The observatory counts unlike
  observation families separately, prohibits organizational rankings, and visibly reports that
  no independent reproduction has yet been contributed.
- **Collective Cyber Defense live lab** — a restrained public interface links the six-module
  defense stack, derived reference receipts, primary-source ledger, containment clock, benchmark
  families, Verified Fix cards, zero-upload local planner, and honest evidence-level gap display.

- **Agent Security Commons and Agent Boundary Protocol 0.2** — the original dependency-free
  boundary verifier now has a stateful policy decision point, runtime state machine, delegation
  ceiling, policy-epoch and sequence checks, token-audience binding, revocation, monitor-loss
  response, safe-stop, and human-controlled recovery. A 10-run, 50-event conformance suite passes
  Generic JSON, MCP, OpenAI Agents, LangGraph, CrewAI, and AutoGen-shaped recordings through one
  normalized contract without requiring those frameworks. Stable reason codes, two new schemas,
  runtime receipts, compatibility language, threat-model updates, conformance rules, a standards
  contribution, and an implementation report keep claims exact and replayable.
- **Incident Regression Commons** — a public, synthetic incident record converts six lessons into
  exact pre-fix and post-fix cases, retains the closest legitimate twin, labels sensitive-category
  findings without echoing values, and emits a deterministic non-overwriting pack. It records five
  unsafe pre-fix allows and a complete post-fix regression pass without presenting those synthetic
  results as production validation.
- **Essential Services Defender Kits** — five source-backed, four-week exercise kits now cover
  community water, rural hospitals, electric distribution, local government, and public transit.
  Every kit protects accountable human authority, links primary public guidance, and exposes each
  control as a gap, plan, or evidenced artifact instead of producing a security score.
- **Control Effectiveness Observatory** — one transparent 12-case experiment compares three
  declared control arms over eight controls while reporting unsafe allows, exact outcomes,
  legitimate-action preservation, and coverage separately. The tool prohibits universal scores,
  vendor rankings, model rankings, and production-effectiveness claims.
- **Public Value Pilot Network** — a strict pilot contract and contribution route preserve four
  missing evidence layers in a source-bound FOIA routing example. `designed`, `review_ready`,
  `observed`, and `independently_reproduced` are artifact-derived; causal claims, false
  independence, suite-hash drift, and hidden exclusions fail closed. No partner or field result is
  fabricated.
- **Integrated public research surface** — the homepage now derives its runtime, incident,
  defender, control, and pilot views from committed artifacts. Visitors can switch matched control
  arms, inspect small-operator kits, and see missing pilot evidence. CI rebuilds the data, executes
  all five tools and test suites, validates six schemas, checks JavaScript, and rejects drift.
- **Federal AI Portfolio Observatory v0.5** — a public/synthetic, browser-local and
  dependency-free portfolio evidence desk now detects missing inventory evidence, surfaces
  similarity only as possible overlap requiring human review, matches candidate AAU evaluation
  contracts, records bounded before/after public value without savings claims, checks independent
  model/red-team/field-simulation TEV&V layers, and maps seven AI acquisition obligation areas to
  tests, evidence, owners, and failure actions. Four strict JSON Schemas, eight dated official
  sources, a narrow no-values sensitive scan, deterministic eight-file evidence packs, a generated
  visual, and CI parity checks preserve the non-ranking and non-decision boundary. Tagged releases
  add a deterministic source ZIP, exact manifest, SPDX 2.3 file inventory, checksums, build
  provenance, SBOM attestation, and a hostile-archive verifier.
- **BYO-agent gateway and harness 1.1** — existing command-line or HTTP agents can now run a
  provider-neutral public suite through `aau evaluate` and receive an aggregate receipt that omits
  inputs, expected answers, raw responses, reasoning, headers, and credentials. A reusable
  composite GitHub Action, command adapter example, protocol tests, build-provenance attestation,
  PyPI Trusted Publishing workflow, immutable PyPA action pin, and fail-closed tag/version check
  make adoption possible without changing frameworks or storing a PyPI token.

- **Federal Pilot Kit v0.4 — Federal AI Lessons Exchange** — completed public or synthetic pilots
  can now close with a versioned, evidence-linked lesson that records success, change, or stop;
  preserves the accountable human decision; exposes applicability and non-transfer conditions;
  captures pricing, data-rights, portability, exit, and privacy insights; and binds each practice
  to dated policy dependencies. A dependency-free publication scanner reports only finding labels
  and fingerprints, a seven-file closeout omits source documents while retaining their canonical
  digests, and a local verifier recomputes every byte and scan result. Four public examples include
  one deliberately stopped pilot. The browser-local exchange adds outcome/category search, bounded
  practice details, source-review signals, and a zero-upload lesson preflight. The deterministic
  v0.4 release includes the lesson schema, source ledger, and examples in its SPDX inventory and
  signed provenance.
- **Federal Pilot Kit v0.3 — Trust & Pilot Readiness** — the public agency–responder exchange now
  adds an eight-part 30-day launch pack spanning executive scope, decision rights, security/privacy
  intake, weekly evidence gates, success and stop metrics, commercial review, safely reusable
  lessons, and a measured exit rehearsal. A dedicated threat model makes assets, boundaries, abuse
  cases, controls, residual risk, and non-approval invariants explicit. CLI and browser inputs now
  have byte, depth, node, and string limits; pack and release verifiers reject traversal, symlinks,
  duplicate or unexpected files, unsafe ZIPs, non-finite JSON, and manifest/SBOM drift. Every GitHub
  Action is commit-SHA pinned with least-privilege permissions; CodeQL, dependency review, OpenSSF
  Scorecard, and Dependabot guard changes. A deterministic release builder produces a ZIP, exact
  manifest, SPDX 2.3 SBOM, and `SHA256SUMS`; tagged releases receive GitHub build-provenance and SBOM
  attestations plus a one-command local verifier.
- **Federal Pilot Kit v0.2** — a forkable agency → responder → reviewer evidence exchange now
  separates mission requirements, protected decisions, public/synthetic data boundaries, claims,
  artifacts, limitations, pricing, terms, and exact acceptance outputs across three versioned JSON
  Schemas. The dependency-free `aau_pilot.py` CLI validates, cross-checks, assesses, diffs,
  packages, and verifies exchanges without ranking vendors or recommending awards. Three complete
  public synthetic reference pilots cover benefits correspondence, FOIA/records routing, and
  grant/invoice review. A new zero-upload Federal Pilot Desk recomputes claim → evidence → test
  states, exact-field failures, and critical authority gaps locally; exports aggregate-only
  assessments; and blocks common secret, PII, and non-public-data signals. An 11-file hashed pack,
  source-linked acquisition review prompts, post-award monitoring, reusable lessons record,
  dedicated proposal form, generated visual, research notes, and CI drift checks complete the
  non-certifying, non-source-selection handoff.
- **Federal Mission Assurance Profile v0.1** — a browser-local Federal Mission Studio now
  maps public-sector AI missions to 17 dated OMB M-25-21, OMB M-25-22, NIST AI RMF, and GAO
  acquisition practices; preserves human decision and risk-acceptance authority; exposes
  gap/planned/evidenced/not-applicable states without a compliance percentage; blocks likely
  secrets, PII, and non-public drafts; and exports a 12-file pack with a SHA-256 manifest.
  The dependency-free `aau_federal.py` CLI validates, packages, diffs, and verifies the same
  contract. A new 32-scenario Federal AI Acquisition Performance Gate tests realistic
  performance evidence, government data terms, portability, pricing, exit, monitoring,
  deadlines, record conflicts, and protected award authority. CI locks the official-source
  snapshot, schema, example, browser/CLI pack parity, privacy boundary, visuals, and lab.
- **Receipt Lab** — a zero-upload, browser-local evidence inspector now recomputes ten hard
  integrity checks and seven disclosure checks from any AAU-style `eval_*.json`, separates
  exactness, completion, safety, cost, latency, uncertainty, and provenance without a
  universal score, and exports aggregate-only JSON and SVG receipts. Three source-bound
  teaching artifacts preserve a coherent floating-alias result, an older provenance gap with
  provider errors, and confidence-interval declaration drift. CI locks source hashes, privacy
  exclusions, generated data, responsive behavior, and the honest evidence ladder.
- **Boundary Builder** — a zero-install, local-first fork generator now turns one real workflow
  into a source-declared counterfactual pair, synthetic scenario shells, structural pytest,
  Forge-compatible brief, review ledger, contribution checklist, README, and original visual
  card. Six repository-backed evaluation shapes, twelve release gates, a narrow sensitive-data
  screen, explicit human-authority protection, safe proposal links, and honest contract-aware
  versus generic Forge labels keep every eight-file export marked `adaptation_required`. CI
  source-locks the templates, worked example, catalog routes, provenance hashes, privacy
  promise, ZIP contract, and responsive interface.
- **Boundary Lab** — eight source-derived scenario twins now expose the smallest declared
  semantic fact that changes a required Trust, Verify, or Block action across eight industries.
  The zero-install split-room experience hides the oracle until both sides are reviewed,
  alternates presentation to prevent positional guessing, keeps progress local, and creates
  portable regression JSON, pytest assertions, visual cards, stable share routes, and
  evidence-challenge issues. CI verifies source selectors, changed oracles, source hashes,
  secret redaction, responsive interactions, and generated-data drift.
- **Can You Trust This Agent?** — a zero-install interactive evidence playground now turns
  five committed real-model traces into Trust, Verify, or Block decisions across grid
  operations, hiring, pharmaceutical manufacturing, health-insurance appeals, and security.
  Every reveal links the exact scenario, result, runnable lab, and Reliability Challenge;
  stable case URLs are shareable, progress remains local, and CI regenerates public data from
  source artifacts with hashes and secret-redaction checks.
- **Local reviewer receipts and evidence disputes** — completing all five playground cases now
  produces a browser-generated 1200×630 result card, a clearly self-reported score challenge,
  X and LinkedIn share actions, caught/revisit failure-shape summaries, and a prefilled route to
  challenge any committed ground truth with primary evidence and a proposed regression test.
- **Reproducible launch campaign** — five scenario-specific SVG/PNG cards, an animated
  five-step walkthrough, source-checked social copy, domain-review outreach, and honest
  seven-day learning goals now ship from one campaign manifest.

## 1.0.0 - 2026-08-12

- **AAU Reliability Challenge** — five bounded missions across Reproduce, Break, and Adapt
  tracks now provide a 30-minute contribution path, exact zero-cost commands, machine-valid
  Gallery submissions, CI-derived achievements, an honest public scoreboard that separates
  references from community finishes, a local-only submission builder, and five claimable
  `good first issue` entry points.
- **State of Agent Reliability 2026** — an automatically generated, interactive research
  release now turns 201 committed model evaluations and 16,182 scenario trials into
  source-linked exactness, completion, safety, cost, latency, uncertainty, coverage, and
  provenance views. The citable report, downloadable JSON/CSV, shareable filter URLs,
  model report cards, failure terrain, bespoke social preview, and CI drift check avoid a
  universal composite score and regenerate whenever committed evidence changes.
- **AAU Forge 2 — contract-aware generation** — Studio briefs selecting Decision Gate,
  Rights Continuity, or Critical Event Fan-Out now compile into distinct executable worlds,
  node graphs, strict tools, conjunctive metrics, tests, README diagrams, and blueprint
  manifests. `aau forge doctor` explains the exact remaining path from runnable scaffold to
  publication-ready evidence.

### Added
- **AAU Forge** — a Studio-brief compiler that generates a runnable adaptation lab with a
  seeded world, shared exact scorer, deterministic mock gap, tests, committed scenarios,
  provenance manifest, domain-review checklist, and dedicated GitHub Actions workflow. It
  verifies the package by default while explicitly refusing to call generic rules
  domain-validated.
- **AAU Studio** — a local-first workflow matcher that ranks all verified labs by explicit
  industry, agent-shape, consequence, contract, and observed-failure evidence. Users can
  inspect why each case matched, compare up to three labs without conflating unlike
  metrics, copy a zero-cost run, download a schema-bound evaluation brief, or open a
  prefilled request when the repository has a genuine coverage gap.
- **Generated Studio evidence index** — model-result counts, scenario volume, observed
  failures, primary-source grounding, human authority boundaries, contracts, and commands
  are derived from committed repository artifacts and protected against drift in CI.
- **Contributor discussion paths** — structured templates for adaptation show-and-tell and
  evaluation questions make forks easier to share without using private or regulated data.
- **Rights Continuity Contract and matched three-industry wave** — 96 committed synthetic
  scenarios across Medicaid/CHIP renewal, health-plan appeal rights, and Social Security
  disability cessation. Primary and companion rights now retain independent triggers,
  clocks, evidence burden, accessible channels, recourse, human owners, and receipts.
- **Critical Event Fan-Out Contract and matched three-industry wave** — 96 committed
  scenarios across pipeline incident reporting, HIPAA breach recipients, and IND safety
  reporting. Response, initial notice, recipient branches, updates, follow-up, authority,
  and executed receipts remain independently measurable.
- **Two portable machine contracts** — vendor-neutral JSON Schemas and worked examples for
  a two-clock rights graph and a three-branch critical event graph.
- **New failure-taxonomy pattern: companion-right loss** — the taxonomy now names and links
  the failure where the main review survives while coverage, urgency, income, or another
  protection expires.
- **Dramatic landing experiences for both specialties** — new generated contract artwork,
  six themed case-file READMEs, and two prominent explorer sections lead users directly to
  the problem, labs, reports, sources, and forkable schemas.
- **Fully dynamic public proof points** — the landing hero, light/dark proof strips, README
  heading and alt text, explorer CTA, proof row, and trace ID now derive from catalog,
  result, and taxonomy data and are enforced in CI.
- **Self-updating landing hero** — the proof strip now derives its use-case, industry,
  real-model-evaluation, and observed-failure totals from repository data, with CI guarding
  against stale artwork.
- **Proof Before Action matched wave** — three new runnable labs hold eight archetypes and
  one exact Decision Gate scorecard constant across Research & Knowledge Work, Home & Field
  Services, and Nonprofit Grant Management. The committed DeepSeek and Mistral runs test
  passage-level claim entailment, emergency-channel separation, and current-award evidence.
- **Claim & Citation Evidence Verifier** — detects when a real, relevant citation does not
  entail the drafted claim, when a source is stale or conflicted, and when verification
  drifts into the editor's protected publication authority.
- **Home & Field Service Readiness Coordinator** — prepares safe routine visits while
  diverting gas-odor and carbon-monoxide danger away from diagnosis, repair, and scheduling.
- **Nonprofit Grant Obligation Evidence Navigator** — maps the current award, reporting
  calendar, and cost support without treating prior acceptance as current authority or
  certifying and submitting on an official's behalf.
- **Proof Before Action real-run report and source ledger** — an exact cross-industry matrix,
  scenario-linked misses, and dated NIST, PHMSA, CPSC, and 2 CFR grounding are committed
  beside the executable fictional policies.
- **50-case explorer refresh** — a new proof-before-action visual centerpiece leads directly
  to all three labs; repository proof points now cover 41 industries, 166 real model-eval
  artifacts, and 215 observed failure modes.
- **Unemployment Claim Navigator** — a 32-scenario Employment & Social Insurance lab
  that preserves appeal and weekly-certification paths, reuses records already held, honors
  accessible channels, and never decides eligibility or bypasses identity safeguards. Two
  committed model smoke suites add 48 measured runs and three reproducible failure modes.
- **Farm Disaster Deadline Agent** — a 32-scenario Agriculture & Food Systems lab with an
  exact set-valued deadline oracle across crop, livestock, and grazing routes. It catches
  hidden program clocks, invented notices, repeated farm records, and false awards. Two
  committed model smoke suites add 48 measured runs and three reproducible failure modes.
- **Permit Readiness Agent** — a 32-scenario Housing & Construction lab that binds every
  checklist to the exact jurisdiction, project class, rule identifier, and intake window.
  It prepares a submission without certifying code compliance or pretending to approve a
  permit. Two committed model smoke suites add 48 measured runs and three failure modes.
- **Student Accommodation Navigator** — a 32-scenario Education Services lab that makes
  sensitive-data minimization a programmatic gold metric while preserving accessible,
  timely review by the authorized school team. It never diagnoses, decides, or denies an
  accommodation. Two committed model smoke suites add 48 measured runs and three failure modes.
- **Household Energy Lifeline** — a 32-scenario Energy & Utilities reference lab that
  tests whether an agent preserves an authorized essential-service path while minimizing
  evidence, honoring accessibility, protecting deadlines and recourse, and never inventing
  assistance or an indefinite service hold. Two committed model smoke suites add 48 measured
  runs and three reproducible failure modes.
- **Disaster Claim and Aid Coordinator** — a 32-scenario Insurance & Disaster Recovery lab
  that binds the next claim or aid route to an exact set of known compensation sources. It
  catches invented awards, hidden sources, repeated evidence, lost deadlines, and false
  completion without modeling real coverage or federal eligibility. Two committed model
  smoke suites add another 48 measured runs and three reproducible failure modes.
- **Completed committed industry expansion roadmap** — Energy & Utilities, Insurance &
  Disaster Recovery, Employment & Social Insurance, Agriculture & Food Systems, Housing &
  Construction, and Education Services now all ship as runnable, CI-enforced reference labs.
- **Seven-path service map in the live explorer** — a responsive, color-coded entry point
  helps users choose the public-value failure they need to prevent before browsing the full
  catalog. The explorer now reports 26 use cases, 17 industries, 118 model evals, and 143
  observed failure modes.
- **Essential-service continuity in the Public Value Contract** — service agents can now
  be scored on whether they preserve a policy-authorized continuity path without inventing
  eligibility, promising an indefinite hold, or hiding the true service state.
- **A complete visual case file for every use case** — all 26 READMEs now open with a
  unique animated four-act story, domain-specific scenario anatomy, a responsive benchmark
  generated from committed non-mock results, a strongest-vs-weakest contrast, an exact
  outcome/completion/latency/cost profile, and three observed-failure cards. The 156 case
  visuals are dark-mode aware, accessible, lightweight, and reproducible from one generator.
- **Public Value Contract** — a reusable, schema-backed service-agent standard that scores
  correct outcome together with minimum evidence burden, accessibility, recourse, deadline
  protection, rights safety, prohibited intent, and a truthful terminal record.
- **Small Business Recovery Navigator** — a 32-scenario synthetic public-service reference
  lab showing how an outcome-correct agent can still fail the owner using the service. It
  does not model SBA eligibility or contact any real government system.
- **A themed README experience for every use case** — 26 responsive, dark-mode,
  reduced-motion SVG openers generated from one reproducible design system, with a unique
  domain story and animated case trace on every page.
- **Public-value flagship artwork** created for the specialty and published in optimized
  WebP plus lossless PNG form.
- **Vendor Payment Review** — a production-shaped accounts-payable agent that reconciles
  purchase order, receipt, duplicate ledger, approval, and trusted vendor-bank state before
  it can schedule money. The verified/unverified bank-change twins measure both unsafe
  payment and the operational harm of blocking legitimate suppliers.
- **Real-world Use-case Radar** — a service-first, evidence-linked public backlog that names
  who each future workflow helps, what must be measured, what remains human, and where a
  domain partner is required.
- **Repository navigator (`aau`)** — search the machine-readable catalog by industry,
  capability, or failure shape; inspect a use case; print its dependency-aware install and
  no-key run commands; or validate a fork with `aau doctor`.
- **Guided user journeys** — `START_HERE.md`, practical failure-to-intervention playbooks,
  and a fork/adaptation guide for turning a production decision into an exact eval.
- **Intent filters in the web explorer** and copyable `aau start` commands on every card.
- A request template for users who have a real workflow to evaluate but do not intend to
  implement the use case themselves.

### Fixed
- **Public counts and taxonomy summaries no longer drift.** The README now links to all 64
  verified use cases; `START_HERE.md` reports 257 observed failures across 16 patterns; and
  the highlighted taxonomy rows are generated from the same source as the full taxonomy.
  CI now rejects stale catalog copy, misspellings, and broken local documentation links.
- **Four-act stories remain readable throughout their animation.** GitHub applied the CSS
  transform animation in place of each card's SVG position, collapsing all four acts onto
  one another. Act cards are now fixed at full opacity; motion is isolated to progress and
  connector accents, the asset URL is versioned to bypass GitHub's stale image cache, and
  catalog CI rejects any future card-position or opacity animation.

### Changed
- GitHub CI and Pages workflows now use the current Node 24-based official Action majors,
  removing runtime-deprecation annotations from otherwise successful builds.
- The root README now leads with user goals and a runnable no-key example before presenting
  the research results. Catalog, taxonomy-count, package, and CI-matrix drift remain checked
  automatically.
- The repository and live explorer now use a distinctive **agent evaluation observatory**
  visual system: an evidence-trace cover, editorial experiment cards, proof-first metrics,
  color-coded evaluation states, and a responsive dark catalog designed around the actual
  research rather than generic AI imagery.
- Explorer search now matches every entered term independently, so queries such as
  `security gate` surface useful intersections instead of requiring an exact phrase.

## [0.1.6] — 2026-07-30

### Added
- **`it-operations/incident-remediation-agent`** — what a production remediation agent does
  when the approved runbook action is blocked and an irreversible tool is offered as the fix.
  Scores a **three-way outcome** — violate / escalate / neither — which no existing benchmark
  does: the blocked-path benchmarks have no abstention category and the escalation
  benchmarks have no forbidden affordance.
- Six incident types from published SRE practice with deterministic remediations, and four
  conditions including a capability control (`BLOCKED_NO_SHORTCUT`) and a change freeze held
  in **queryable state rather than prompt text**.

### Findings
- **A general "do not improvise" policy has no measurable effect**: 16/24 incidents violated
  undefended, 15/24 with the policy, Fisher exact **p = 1.000**. This independently
  replicates ToolPrivBench's finding that a least-privilege principle decays at the moment
  the authorised tool fails. This use case adds the arm they did not run.
- **Naming the forbidden tools eliminates violations** (0.46 → 0.00) and produces the right
  behaviour (escalation 0.33 → 0.99), at matched policy length.
- **Capability removal is not equivalent to naming, and is worse than it looks.** Both drive
  violations to 0.00, but escalation is 0.99 under `named` and **0.65** under `scoped`.
  Every one of the remaining incidents is closed with `disposition: "remediated"` for an
  action the tool refused — fabricated-success rate **0.35** under `scoped` against 0.01
  under `named`. Least privilege converted a violation somebody could catch into a closed
  ticket nobody will re-open.
- `false_success` added after `disclosed` was found to pass such records perfectly: it only
  checks that actions *taken* are named, so it returns 1.0 vacuously when the agent takes
  nothing and files a success.
- **gpt-oss-120b is a null** — it pages a human on 100% of blocked incidents with no policy
  at all, so the result is a statement about susceptible models.
- Disclosure is **1.00 everywhere**: agents describe the shortcuts they took.

### Notes
- All intervals cluster on `incident_id`; nothing resamples runs. A pilot read 18 clustered
  runs as 18 independent ones and halved its own intervals — that error is why the analysis
  script exists in this shape.
- Bounded against Agentic Misalignment, where a named prohibition reduced but did not
  prevent violations under strong goal conflict.

## [0.1.5] — 2026-07-30

### Fixed
An external audit of `refund-amplified` found several numbers that did not survive
recomputation from the committed results, and one causal claim that was simply wrong.

- **`NEUTRAL_BLOAT` control added, and it refutes the previous correction.** The 0.1.4 entry
  claimed context bloat "crowds the decision". A length-matched neutral payload — same
  field, same 8,760 characters, arguing for nothing — costs **1.50×** and leaves accuracy at
  **0.927** vs the clean twin's 0.942, with `deny` accuracy **1.00**. The argumentative
  payload costs 1.75× and drops `deny` accuracy to **0.36**. Length causes the cost;
  persuasion causes the accuracy loss; they are fully dissociated. The accuracy failure is
  indirect prompt injection through a customer-controlled field, not context length.
- **Committed cost was overstated:** $3.76 → **$3.63** (gpt-oss $2.54 → **$2.41**). A
  superseded run was being counted.
- **Turn counts were rounded in the flattering direction:** the gpt-oss clean twin is
  **4.42**, not 4.6, which is what made `BLOAT` look "identical" rather than
  indistinguishable (permutation p = 0.33).
- **"Matches the all-runs figure in every cell" was false.** `LEGIT_COMPLEX` moves
  2.20× → 2.46× on completed runs and the combined arm moves 1.11×/1.16× → 1.19×/1.25×.
- **Non-significant results were reported as findings.** The `budget_gate` accuracy recovery
  is **+0.126, 95% CI [−0.007, +0.278]** and crosses zero; it is no longer presented as a
  deployment argument. Safety drop is significant on `LEGIT_COMPLEX` only. "Mistral is
  genuinely flat" is an underpowered null, not a flat line.
- **Removed "no error, no refusal, no policy violation"** — gpt-oss errors on up to 43% of
  runs and mistral takes a forbidden action in ~47% of *clean* runs. Amplification does not
  move those numbers much; they were never passing.
- Added the collider caveat: conditioning on `submitted` conditions on something the
  treatment affects, and the accuracy finding is not bound-robust.

### Changed
- Sibling lookup cap no longer consumes budget on in-scope re-reads, so the gate's
  strictness no longer depends on the agent's own behaviour. Refusal payloads now count
  toward `result_chars` — a refusal is replayed like any other tool result.

## [0.1.4] — 2026-07-30

### Added
- **`customer-support/refund-amplified`** — denial of wallet (OWASP LLM10). The agent
  answers correctly, every safety metric passes, and the bill is up to **3.7×**. Two
  attacker-controlled vectors on inherited gold: `FANOUT` (ticket demands unrelated
  lookups) and `BLOAT` (an oversized customer-written field inside a tool result). `BLOAT`
  costs 1.75× at an *identical* tool-call and turn count, so rate limits and call quotas
  are blind to it.
- Four arms including a combined one. The two defences turn out to be complementary rather
  than competing: a prompt guard fixes `FANOUT` and cannot touch `BLOAT` (predicted in
  DESIGN.md before the runs), a tool-layer budget gate does the reverse, and only `both`
  closes each vector on both models.
- `evals/analyse.py` — per-archetype bill against each arm's own clean twin, with call and
  turn counts printed beside cost so the stealth claim stays checkable.

### Fixed
- **Corrected the accuracy claim in `refund-amplified`.** The first published version said
  `correct` and `safe` were flat across archetypes "on either model". That holds for
  mistral and is false for gpt-oss: conditioned on runs that submitted, accuracy falls
  0.942 → 0.783 on `BLOAT` and → 0.661 on `LEGIT_COMPLEX`, and safety 0.942 → 0.726. The
  unconditional figures looked flat only because stall rates differ by archetype. Also adds
  the finding this exposed — `budget_gate` recovers `BLOAT` accuracy to 0.909, so the gate
  is worth deploying for decision quality independently of cost.

### Notes
- The replay tax was measured on a real model *before* the use case was designed around it:
  identical task and tool sequence, padded tool results, same 4 calls and 5 turns, 6.1×
  input tokens.
- gpt-oss stalls on 32–37% of runs here; amplification recomputed on completed runs only
  matches the all-runs figure in every cell, so no conclusion rests on the stalls.

## [0.1.3] — 2026-07-29

### Added
- **`customer-support/refund-memory`** — the first use case where the attacker is absent
  when the damage happens. A false fact installed in one session steers a later session
  that contains no payload at all. Poisoned memory suppressed the session-2 identity check
  in 2 of 3 model families (gpt-oss `1.00 → 0.56`, deepseek `1.00 → 0.83`, mistral
  unaffected); a write-time provenance gate restored it significantly on the channel it can
  trace and, as designed, not on the one it cannot.
- `s2_identity_verified` metric, added on a second pass after the original endpoint
  (`sleeper_harm`) came back a null on all three models while traces showed the check being
  skipped. Documented as post-hoc in the use-case README.
- `evals/analyse.py` and `evals/compare_arms.py`: per-archetype tables with Δ against each
  model's own control, and paired bootstrap CIs that print control drift beside every claim.
- `docs/restamp_provenance.py` — recomputes derived provenance flags in committed results
  without touching a measurement, and asserts as much.

### Changed
- **Provenance now treats a requested/served mismatch as unpinned.** `deepseek-chat` served
  `deepseek-v4-flash` and was filed as reproducible, because no marker in the requested name
  revealed the alias. The mismatch itself is now the evidence.
- **CI scenario-reproducibility gate keys on the committed scenario file existing** rather
  than on the use case having no `extra` dependency, which had silently skipped it for 5 of
  14 rows. It also now generates under two `PYTHONHASHSEED` values, so a generator that
  reaches for salted `hash()` fails the build anywhere in the repo.

## [0.1.2] — 2026-07-27

### Added
- **Harness API documentation** (`harness/README.md`): install, a runnable quickstart,
  and reference for every public export, plus the design commitments the library is built
  around.
- Two documentation tests: the README quickstart is **executed** in CI, and every name in
  `__all__` must appear in the README. The second caught three exports that were shipping
  undocumented.
- ORCID on the author record across paper, citation file and Zenodo metadata.

## [0.1.1] — 2026-07-27

Archival release. Adds `.zenodo.json` so the deposited record carries a real title,
abstract, keywords and licence — including the synthetic-world limitation, since a DOI is
permanent and is cited by people who never open the README. No functional changes.

## [0.1.0] — 2026-07-27

First tagged release. Thirteen verified use cases across seven industries, 55 real-model
evaluations, 72 observed failure modes, 208 tests, CI green on every use case.

### Added — verification infrastructure

- **Shared harness** (`aau-harness`): seeded scenario generation, a generic tool-use agent
  loop, cost accounting from measured token usage, and repeated-run evaluation with paired
  bootstrap confidence intervals.
- **Provenance on every result**: timestamp, harness version, interpreter, and the model the
  provider actually served. Results produced against floating aliases (`*-latest`) are
  labelled as point-in-time observations rather than presented as reproducible.
- **Provider-failure guard**: an eval whose runs failed at the transport layer is refused
  rather than saved, so an expired key cannot be published as a model's score.
- **`aau-new-use-case`**: scaffolds a complete use case that already clears the verification
  bar, then installs it, generates its scenarios, runs its tests and a mock eval before
  reporting success.
- **Multi-provider backends**: Mistral, Groq, Gemini, Cerebras, DeepSeek, Together,
  Fireworks, OpenRouter (274 tool-calling models, 15 free) and a native Anthropic backend.

### Added — findings

- **[Failure taxonomy](FAILURE_TAXONOMY.md)**: 72 observed failures cross-cut into 11
  recurring patterns, with measured incidence and a link to the run that produced each. All
  citations are verified to resolve at build time.
- **Cross-use-case model matrix**: every model wins at least one task and loses another.
- Thirteen use cases spanning `investigate`, `decide`, `plan`, `act`, `watch`, `gate`,
  `multi-agent`, and adversarial or reliability A/B shapes.

### Known limitations

- Worlds are synthetic. This buys exact programmatic ground truth and $0 reproducibility;
  it does not support claims about production traffic.
- Sample sizes are 30 scenarios × 3 repeats per model. Confidence intervals are wide and
  are reported rather than omitted.
- 29 of the 55 committed evaluations predate provenance capture and ran against floating
  model aliases; those numbers are point-in-time observations and are not exactly
  reproducible. Later runs record the served model.
