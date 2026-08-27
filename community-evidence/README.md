# Built with AAU: community evidence

This directory is the public handoff between a five-minute Agent Evidence Starter and a
full Community Forge Gallery lab. A contribution is a small, inspectable evidence pack:
a reviewed synthetic suite, one or more aggregate agent receipts, derived checks, a
privacy scan, a SHA-256 manifest, and a share card.

Evidence levels are computed, never selected:

| Level | Required public evidence |
|---|---|
| **Generated** | Valid Starter contract, a non-mock command or endpoint receipt, and protected human authority |
| **Domain reviewed** | Everything above, plus an adapted 10-case suite, named review scope, and at least two source links |
| **Reproduced** | Everything above, plus three distinct public run receipts |
| **Verified** | Everything above, plus a named different contributor linked to one reproduction receipt |

These levels describe submitted artifacts. They do **not** verify identity, certify an
agent, prove production safety, imply regulator or government endorsement, or authorize
automation of a protected decision.

## Submit your adaptation

1. Generate an [Agent Evidence Starter](https://immu4989.github.io/awesome-agentic-usecases/#agent-starter), connect your agent, and create a public receipt.
2. Build the local contribution bundle:

   ```bash
   python -m pip install aau-harness==1.4.0
   aau submit ./my-agent-eval \
     --receipt ./public-receipt.json \
     --id my-agent-evidence \
     --contributor-name "Your name" \
     --github your-handle \
     --summary "What the agent helps with." \
     --why-fork "What another team can adapt." \
     --beneficiaries "Who benefits." \
     --industry "Your industry" \
     --failure-shape "The failure boundary this catches." \
     --tag routing --tag human-authority
   ```

3. Validate it from the bundle directory: `aau submit --validate .`
4. Copy the bundle into `community-evidence/entries/<id>/` and open the
   [Community evidence pull-request template](https://github.com/immu4989/awesome-agentic-usecases/compare).

The browser [Contribution Desk](https://immu4989.github.io/awesome-agentic-usecases/#community-evidence-loop)
can inspect Starter files and receipts locally. It does not upload or persist form data.

Maintainer reference entries are deliberately labeled `maintainer-reference`. They show
the file contract, not community adoption.
