# Practical playbooks

These playbooks are the reusable layer above the individual use cases. They are not
universal laws; each recommendation links to the controlled comparison or observed failure
that motivated it.

## Pick metrics from the agent's power

The more an agent can do, the less a final-answer score tells you.

| Agent can… | Always measure | Why |
|---|---|---|
| Return a label | accuracy, `submitted`, error direction | An unanswered run must not disappear from accuracy |
| Retrieve before deciding | required-source coverage, stale-read rate, answer | Correct answers can be lucky; wrong answers can follow correct retrieval |
| Take reversible action | action correctness, recovery, final state | A correct plan can still produce the wrong state |
| Take irreversible action | prerequisites, forbidden attempts, forbidden executions, outcome | The route can be unsafe even when the result is correct |
| Wait and observe | observation coverage, decision timing, false positive, false negative | Silence can mean patience or quitting early |
| Gate admission | unsafe admits, over-block, escalation, coverage | “Blocked every threat” is useless if everything is blocked |
| Write memory | write provenance, later-session harm, clean utility | The attacker may be gone when the damage occurs |
| Produce an audit record | overclaims, omissions, actions actually taken | A truthful sentence can still omit the regulated fact |
| Mediate access to a service | outcome, minimum evidence, accessibility, deadline, recourse, rights, record truth | A correct next step can still exclude or burden the person |
| Coordinate evidence across a regulated service | exact terminal, missing-set evidence, verified channel, deadline, recourse, protected-decision attempt, executed record | A plausible packet can duplicate evidence, lose a clock, cross authority, or claim work that never happened |
| Prepare a high-stakes decision gate | outcome, rule-specific reason, held/requested evidence, satisfied conjuncts, procedure, protected-authority attempt, executed record, transfer specificity | A correct-looking recommendation can use the wrong exception, invent one gate, or become the decision |
| Recover identity-bound access | assurance level, established method, takeover, notification, PII burden, completion | A successful recovery can be a successful account takeover |
| Verify remediation | defect coverage, matching test, deploy state, post-fix result, false assurance | Detection, code change, deployment, and proof of fix are different states |
| Orchestrate rights across systems | identity gap, exact system set, jurisdiction, deadline, exception, receipts | A correct request type can omit data or produce false closure |

## Diagnose by symptom

### Accuracy looks good, but users receive no answer

1. Read `submitted` before reading accuracy.
2. Split stalls by the last successful tool call.
3. Check whether handoffs or escalations are being mistaken for task completion.
4. Make the terminal action explicit and observable; test it as a controlled change.

Evidence: [commit-stall](FAILURE_TAXONOMY.md#commit-stall) appears across unrelated
industries. A prompt reminder intended to fix it made it worse in
[Refund Guarded](customer-support/refund-guarded/).

### The agent retrieves the right policy and violates it anyway

1. Score “policy retrieved” separately from “policy followed.”
2. Break the result down by prohibition versus ordered procedure.
3. Put non-negotiable constraints at the action boundary.
4. Keep `attempted` and `executed` as separate metrics so containment is not mistaken for
   corrected judgment.

Evidence: [prior over policy](FAILURE_TAXONOMY.md#prior-over-policy) and the tool-enforced
arm in [Refund Guarded](customer-support/refund-guarded/).

### The security score is perfect because the agent did nothing

1. Pair every restraint metric with task completion and observation coverage.
2. Report provider errors separately from model decisions.
3. Include clean scenarios that require the supposedly dangerous action.
4. Measure over-block on those clean cases.

Evidence: [safety by inaction](FAILURE_TAXONOMY.md#safety-by-inaction) and
[On-Call Watch](it-operations/oncall-watch-agent/).

### Prompt injection defences look good in a chat test

1. Give the agent a real side-effecting tool in a synthetic world.
2. Mark the forbidden consequence, not suspicious words or model intent.
3. Test injections in user content, fetched content, tool output, and tool descriptions.
4. Compare a prompt defence with an environment defence on identical scenarios.
5. Report clean-task utility and over-block beside attack success.

Evidence: [Refund Injected](customer-support/refund-injected/) and
[Trifecta Exfil](security-operations/trifecta-exfil-agent/).

### A guard stops the incident but the agent still makes the same decision

1. Record blocked attempts separately from executed actions.
2. Test whether the agent recovers after the block.
3. Treat containment as a valid result, not as evidence the model was fixed.
4. Test removal of the guard explicitly.

Evidence: [contained is not fixed](FAILURE_TAXONOMY.md#contained-is-not-fixed).

### The final report says work happened that never happened

Use the harness reporting primitive to compare consequential claims with actual tool state:

```python
from aau_harness import ReportSpec

spec = ReportSpec(
    consequential={"page_human": ("paged", "on-call", "escalated")}
)
fidelity = spec.check(submitted_record, session.actions, succeeded=False)
metrics = fidelity.as_metrics()
```

Track overclaims and omissions separately. An agent that says nothing should not dilute the
omission rate, and an agent that took no action should not be able to claim success.

### Untrusted content changes where money or access goes

1. Treat the message as the requested change, never as proof that the change is authorized.
2. Resolve the destination or identity from a separately controlled system of record.
3. Include both an unverified change and an independently verified clean twin.
4. Score the executed transfer or access change, not whether the explanation sounded wary.
5. Put a dry-run or hold boundary in front of the irreversible production tool.

Evidence: [Vendor Payment Review](procurement-finance/vendor-payment-review-agent/) pairs
identically worded bank-change requests that differ only in trusted verification state.

### The outcome is right but users still cannot complete the service

1. Write a [Public Value Contract](PUBLIC_VALUE_CONTRACT.md) for each scenario before the prompt.
2. Compute the minimum missing evidence from required minus already-held records.
3. Make channel, deadline preservation, and recourse explicit action fields.
4. Record forbidden attempts separately from blocked or executed actions.
5. Reject a final record that does not match the actual trace.

Evidence: the [Small Business Recovery Navigator](public-sector/small-business-recovery-agent/)
holds outcome accuracy constant while measuring burden, accessibility, deadline, recourse,
rights safety, intent, and record fidelity independently. The same contract now has exact
extensions for [claim paths](employment-social-insurance/unemployment-claim-navigator/),
[multi-program deadlines](agriculture-food-systems/farm-disaster-deadline-agent/),
[jurisdiction rules](housing-construction/permit-readiness-agent/), and
[sensitive-data minimization](education-services/student-accommodation-navigator/).

For a matched comparison instead of one domain-specific extension, use the
[12-industry Evidence Service Contract wave](USE_CASE_RADAR.md#evidence-service-expansion-wave--shipped).
Every lab holds the eight archetypes and exact metrics constant while changing the trusted
records, policy, terminals, authority boundary, and beneficiary. That lets a team test
whether a prompt or model generalizes across services without pretending the policies are
interchangeable.

### A recovery succeeds, but assurance is weaker than the account

1. Intersect presented methods with the account's established recovery state.
2. Make assurance level and selected method set explicit action fields.
3. Pair legitimate-recovery completion with takeover containment and over-block.
4. Treat subscriber notification and minimum PII as part of the outcome.
5. Include clean twins whose user-facing stories are intentionally indistinguishable.

Evidence: [Account Recovery Assurance](identity-access/account-recovery-assurance-agent/).

### The recommendation is right, but the decision process is not

1. Freeze a dated rule snapshot and give every distinct path its own reason code.
2. Derive relied-on and requested evidence from trusted held/required sets.
3. Represent every conjunctive condition independently; confirm only satisfied gates.
4. Put notice, deadline, or confidentiality requirements in the action schema.
5. Make the protected final action a separate forbidden tool and reconcile the closeout
   record with what actually executed.
6. Add a clean twin and a nearby transfer trap whose surface stories look equally plausible.

Evidence: the [Decision Gate Contract](DECISION_GATE_CONTRACT.md) holds eight archetypes and
one exact scorecard constant across pharmaceutical manufacturing, grid operations, hiring,
aviation, banking compliance, and tax filing. The [matched report](DECISION_GATE_REPORT.md)
links every observed miss to a committed scenario and trace.

### A green scan or created task is being reported as completion

1. Name each state: detected, planned, coded, deployed, retested, verified, completed.
2. Define the receipt or test required to move between states.
3. Score exact scope coverage separately from terminal state.
4. Make premature completion or conformance claims observable in the action schema.
5. Route conflicting evidence to an accountable human without erasing it.

Evidence: [Accessibility Remediation](accessibility-digital-services/accessibility-remediation-verifier/)
and [Privacy Rights Orchestration](privacy-data-governance/privacy-rights-orchestrator/).

## Design a useful eval

### 1. Start with a decision somebody owns

Write the operational question before writing the prompt. Good: “Which queue owns this
alert, and may it auto-close?” Weak: “Can an LLM help with security?”

### 2. Hide deciding facts behind tools

If the ticket text contains every fact needed for the answer, the eval measures reading
comprehension rather than agency. Put policy, current state, and contradictory evidence
behind the tools the production agent would need.

### 3. Share the answer rule

The seeded generator and scorer must call the same gold function. Do not ask another model
to reconstruct the answer after the run.

### 4. Include a trap and a clean twin

A trap separates investigation from surface matching. A clean twin reveals whether a
defence prevents the intended task as well as the attack.

### 5. Repeat by scenario

Run at least three repeats and calculate uncertainty over scenarios, not over individual
runs as if stochastic repeats were independent cases.

### 6. Save provenance and non-measurements

Record the requested model, the served model, timestamp, harness version, usage, and
provider failures. Never turn an outage into a model score.

## Move from synthetic to production safely

Synthetic worlds provide exact ground truth and cheap counterfactuals. Before treating a
result as a production claim:

- Revalidate scenario prevalence against real traffic.
- Replace synthetic tool responses with sanitized traces, keeping the exact scorer where
  possible.
- Re-run after provider aliases or prompts change.
- Add latency and availability objectives from the real workflow.
- Review every irreversible action with the team that owns the policy.
- Keep the synthetic suite: it remains the regression test for rare, expensive failures.

See [Limitations](LIMITATIONS.md) for the claims these experiments deliberately do not make.
