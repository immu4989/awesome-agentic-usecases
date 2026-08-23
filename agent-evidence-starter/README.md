# AAU Agent Evidence Starter

Most evaluation projects lose people between “install the tool” and “write the first trustworthy
test.” The Agent Evidence Starter closes that gap with one command:

```bash
python -m pip install aau-harness
aau init my-agent-eval
cd my-agent-eval
aau doctor
```

The generated project contains a reviewed synthetic suite, command and HTTP adapters, exact and
forbidden-action scoring, a deterministic first receipt, a standard-library regression test,
least-privilege GitHub CI, receipt policy, an accountable human boundary, and original evidence-flow
artwork. It never needs an AAU account, hosted dataset, model key, or upload.

## Pick a starting shape

| Template | Use it to test | Protected boundary |
|---|---|---|
| [`public-service-routing`](examples/public-service-routing/) | Current source and accessible-service routing | Eligibility, approval, and official records |
| [`customer-escalation`](examples/customer-escalation/) | Billing, identity, and safety escalation | Refunds, account changes, and safety closure |
| [`incident-triage`](examples/incident-triage/) | Operational impact and evidence preservation | Restarts, log deletion, declarations, and closure |

```bash
aau init public-service-eval --template public-service-routing
aau init support-eval --template customer-escalation
aau init incident-eval --template incident-triage --adapter http
```

These are onboarding smoke suites, not production validation. Adapt the domain facts, add
counterfactual and adversarial cases, complete qualified review, and keep protected decisions with
the declared accountable people.

## Browser-local path

The [Bring Your Agent wizard](https://immu4989.github.io/awesome-agentic-usecases/#agent-starter)
builds the same contract in the browser and downloads an eleven-file ZIP. Form values remain in the
tab: there is no account, persistence, telemetry, model call, or form-data upload.

## Integrity contract

`aau doctor` checks the starter version, required files, suite sharing declarations, human
authority, reference adapter structure, public receipt, immutable CI dependencies, safe manifest
paths, and template drift. It does not execute project code unless you explicitly use
`aau doctor . --run-adapter` on code you trust. Changing generated files is expected and reported
as a warning; missing safety declarations, invalid adapter structure, symlinks, traversal, or
weakened CI fail the doctor.

Regenerate committed browser data and examples with:

```bash
python docs/make_agent_starter_data.py
python docs/make_agent_starter_examples.py
python docs/check_agent_starter.py
```
