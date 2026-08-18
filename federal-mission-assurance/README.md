# AAU Federal Mission Assurance Profile

The **AAU Federal Mission Assurance Profile (AAU-FMAP)** is an open, versioned evidence handoff for
public-sector AI work. It turns a mission description into explicit tests, authority
boundaries, acquisition terms, monitoring triggers, appeal paths, and inspectable artifacts.

It is intentionally **not** a federal standard, government endorsement, certification,
FedRAMP authorization, FISMA determination, Authority to Operate, source-selection decision,
or legal conclusion. It helps teams prepare and inspect evidence; accountable officials retain
every approval, acquisition, operational, rights, safety, and risk-acceptance decision.

## What ships in v0.1

- [`federal-profile.schema.json`](federal-profile.schema.json): machine-readable profile contract.
- [`example-acquisition-profile.json`](example-acquisition-profile.json): complete worked example.
- [`policy-sources.json`](policy-sources.json): dated official-source snapshot and control crosswalk.
- [`aau_federal.py`](aau_federal.py): dependency-free validation, pack, diff, and manifest verification.
- [Federal Mission Studio](https://immu4989.github.io/awesome-agentic-usecases/#federal-mission): browser-local guided builder and 12-file pack exporter.
- [Federal AI Acquisition Performance Gate](../federal-ai-acquisition/acquisition-performance-gate/): runnable, synthetic benchmark.

## Use it locally

```bash
python federal-mission-assurance/aau_federal.py validate \
  federal-mission-assurance/example-acquisition-profile.json

python federal-mission-assurance/aau_federal.py pack \
  federal-mission-assurance/example-acquisition-profile.json \
  --out /tmp/aau-federal-pack

python federal-mission-assurance/aau_federal.py verify-pack /tmp/aau-federal-pack
```

`pack` refuses to overwrite a non-empty output directory. The manifest hashes every generated
artifact. Hashes prove byte integrity, not authorship, independent reproduction, policy
compliance, or government approval.

## Evidence states, not a compliance score

Every mapped control is one of:

- `gap`: no adequate plan or artifact has been identified;
- `planned`: an owner and evidence path exist, but evidence is not yet present;
- `evidenced`: the referenced artifact is present and should be inspected;
- `not_applicable`: the team records why the control does not apply.

AAU-FMAP never adds those states into a percentage. A single missing human-review or cease-use gate
can be more important than dozens of present documents.

## Privacy boundary

The public Mission Studio runs entirely in the browser. It does not upload, persist, or transmit
form contents. Use synthetic or public information in the public site. Agency-sensitive,
controlled, classified, procurement-sensitive, source-selection, or personally identifiable
information belongs only in an agency-approved environment.

## Policy grounding

The v0.1 crosswalk is grounded in:

- [OMB M-25-21](https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-21-Accelerating-Federal-Use-of-AI-through-Innovation-Governance-and-Public-Trust.pdf)
- [OMB M-25-22](https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-22-Driving-Efficient-Acquisition-of-Artificial-Intelligence-in-Government.pdf)
- [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework)
- [NIST AI Resource Center](https://airc.nist.gov/)
- [GAO-26-107859](https://www.gao.gov/products/gao-26-107859)

Policy changes. Every source carries a verification and review-due date. Users must confirm the
current rule, agency implementation, scope, exceptions, and local procedures before relying on a
profile. The [`FEDERAL_MISSION_RESEARCH_NOTES.md`](../docs/FEDERAL_MISSION_RESEARCH_NOTES.md)
file records the source-to-feature reasoning and premise checks behind v0.1.
