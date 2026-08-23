# AAU Federal AI Portfolio Observatory

Turn a public or synthetic agency AI inventory into questions an accountable portfolio
team can inspect:

- Which entries lack a benefit, owner, boundary, outcome metric, strategic goal, cost, or
  completed high-impact determination?
- Which investments may overlap enough to deserve human review?
- Which existing AAU evaluation contracts could seed a test plan?
- Which projects have only a baseline and which have bounded observed measurements?
- Does one evaluation plan cover model testing, red teaming, and field simulation?
- Do AI acquisition obligations map to tests, evidence, owners, and failure actions?

The Observatory **does not** rank investments or vendors, recommend funding, consolidation,
cancellation, award, or deployment, claim audited savings, approve contract language,
certify compliance, or replace agency officials. Possible overlap is a review prompt, not
proof of duplication.

## Start in five minutes

Everything is standard-library Python and uses synthetic data:

~~~bash
python federal-portfolio-observatory/aau_portfolio.py analyze \
  federal-portfolio-observatory/examples/synthetic-agency-inventory.json

python federal-portfolio-observatory/aau_portfolio.py assess-public-value \
  federal-portfolio-observatory/examples/public-value-ledger.json \
  --inventory federal-portfolio-observatory/examples/synthetic-agency-inventory.json

python federal-portfolio-observatory/aau_portfolio.py tev-v-coverage \
  federal-portfolio-observatory/examples/three-layer-tev-v-plan.json \
  --inventory federal-portfolio-observatory/examples/synthetic-agency-inventory.json

python federal-portfolio-observatory/aau_portfolio.py clause-coverage \
  federal-portfolio-observatory/examples/clause-testbench.json
~~~

Build and verify the exact eight-file evidence pack:

~~~bash
python federal-portfolio-observatory/aau_portfolio.py pack \
  federal-portfolio-observatory/examples/synthetic-agency-inventory.json \
  federal-portfolio-observatory/examples/public-value-ledger.json \
  federal-portfolio-observatory/examples/three-layer-tev-v-plan.json \
  federal-portfolio-observatory/examples/clause-testbench.json \
  --out /tmp/aau-portfolio-pack

python federal-portfolio-observatory/aau_portfolio.py verify-pack \
  /tmp/aau-portfolio-pack
~~~

## Open contracts

| Contract | Question it makes inspectable |
|---|---|
| [Inventory](inventory.schema.json) | Is the portfolio entry complete enough to govern and measure? |
| [Public Value Ledger](public-value-ledger.schema.json) | What changed from the declared baseline, at what cost, and with what limitations? |
| [Three-Layer TEV&V](three-layer-tev-v.schema.json) | Are model tests, adversarial tests, and human field simulation independently planned? |
| [Clause Testbench](clause-testbench.schema.json) | Does each acquisition obligation have tests, evidence, an owner, and a failure path? |
| [Dated sources](sources.json) | Which official dependencies informed the contract and when must they be reviewed? |

## Public-data boundary

The public site and examples accept only public, synthetic, or public-synthetic records.
They must attest that human review is complete and that no personally identifiable,
procurement-sensitive, controlled, classified, or credential material is present. The
narrow scanner returns codes and fingerprints without matched values. A zero-finding result
is not disclosure authorization, privacy approval, DLP, classification review, or legal
advice.

## Why these checks

The dated [source ledger](sources.json) records the exact official materials behind the
design. The core evidence comes from 2026 GAO findings on federal AI inventory quality,
strategic portfolio management, systematic acquisition lessons, public inventory reporting,
data quality, and workforce constraints; OMB federal AI governance and acquisition
memoranda; NIST ARIA's model/red-team/field-testing structure; and current federal customer
experience guidance.

Run:

~~~bash
pytest federal-portfolio-observatory/tests -q
python federal-portfolio-observatory/aau_portfolio.py policy-drift --as-of 2026-08-23
~~~

## Verify a tagged release

Tagged releases ship a deterministic ZIP, exact manifest, SPDX 2.3 file inventory,
`SHA256SUMS`, GitHub build-provenance attestation, and archive SBOM attestation. Follow
[`RELEASE_VERIFICATION.md`](RELEASE_VERIFICATION.md) to verify both local byte integrity and the
GitHub workflow identity that built the artifacts.
