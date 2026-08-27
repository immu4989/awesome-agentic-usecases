# Evidence partner guide

The Commons is looking for domain and evaluation partners who can close one narrow evidence gap
without sharing participant-level or protected records. A good pilot is useful even when it stops,
diverges, or shows no benefit.

## Safe contribution path

1. **Name the accountable owner.** Identify the official or organizational role that owns the
   service outcome and every protected decision. AAU does not accept an AI system as that owner.
2. **Freeze the reviewed task contract.** Review scope, source freshness, intended environment,
   affected groups, accessibility, expected outcomes, forbidden actions, and transfer limits.
3. **Rerun the agent with a suite hash.** Record exact artifacts, model/provider provenance,
   repeated-run uncertainty, cost, latency, attempted actions, and executed actions.
4. **Obtain the institution's determination before observing people.** Use the
   [Human Baseline Lab](../human-baseline-lab/) only after the responsible institution defines
   consent, accessibility, withdrawal, privacy, labor, retention, security, and incident handling.
5. **Publish aggregates only.** Compare the same reviewed task set without names, demographics,
   free text, participant rows, production records, or worker rankings.
6. **Measure public value under a frozen plan.** Preserve affected group, baseline source, window,
   method, uncertainty, cost, burden, harms, and limitations. A before/after change is not
   automatically causal.
7. **Invite a separate organization to reproduce.** Publish the exact source hashes, environment,
   tolerance, divergences, and non-transfer conditions. AAU records an independence attestation;
   it does not verify identity.

## What to submit

- A reviewed public or synthetic suite and fresh hash-bound aggregate agent receipt.
- An Impact Capsule that passes `aau evidence validate`.
- If people were observed, only the aggregate Human Baseline report and contributor attestation
  that an appropriate institutional basis was recorded.
- If value was observed, a `aau-public-value-observation/1.0` record.
- If reproduced, a `aau-impact-reproduction/1.0` record from a different organization.
- Explicit limitations, transfer conditions, source review dates, and accountable human authority.

Open the [Evidence partner issue](https://github.com/immu4989/awesome-agentic-usecases/issues/new?template=evidence-partner.yml)
before preparing files. Do not attach private records to the issue.

## Stop conditions

Stop and use the organization's approved channel if the proposed work requires protected or
production data, participant-level publication, observation without notice, individual worker comparison,
an employment decision, a protected eligibility/safety decision, or a claim of certification or
government approval.
