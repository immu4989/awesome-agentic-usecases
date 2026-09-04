# Workflow Dependency Trust Lock

A full 40-character SHA is immutable, but it is not automatically a commit in the repository named
by a workflow. This verifier closes that gap for every external GitHub Action used by AAU.

```bash
python3 workflow-dependency-trust/aau_action_trust.py verify
python3 workflow-dependency-trust/aau_action_trust.py verify --online
```

Offline verification scans every workflow and local composite Action, rejects mutable revisions,
and requires an exact match with [`action-trust-lock.json`](action-trust-lock.json). The lock binds
each repository/commit pair to every workflow path, job ID, external-use ordinal, and Action
component where it is used. Line numbers are diagnostics, not dependency identity: inserting a
comment, run step, or local Action no longer invalidates reviewed origin evidence. Adding, removing,
reordering, repinning, renaming, or moving an external use to another job still fails closed.

Version 1.1 also rejects YAML aliases and merge keys that could expand hidden Action uses outside
the scanner's literal job structure. It masks block-scalar bodies so shell text cannot create a
phantom dependency, while flow-style or quoted `uses` mappings fail closed instead of disappearing
from the inventory. Local `./` and `$/` references do not consume external-use ordinals because
they resolve from the repository itself. Job-level reusable workflows and step-level Actions share
the same locator contract.

Online verification asks GitHub's commit API to resolve each SHA inside its named repository. A tag
object, a commit available only from a fork, an unknown object, or a repository mismatch fails.
The scheduled security workflow authenticates with its read-only `GITHUB_TOKEN`; no additional
secret is required.

To propose a refreshed lock without overwriting reviewed evidence:

```bash
python3 workflow-dependency-trust/aau_action_trust.py snapshot \
  --as-of YYYY-MM-DDTHH:MM:SSZ \
  --out /tmp/action-trust-lock.json
python3 workflow-dependency-trust/aau_action_trust.py verify \
  --lock /tmp/action-trust-lock.json --online
```

Review changed Action source and release notes before replacing the committed lock. Repository
membership and commit-signature metadata are different claims: signature status is recorded, but
unsigned commits are not silently promoted to unsafe or safe. This mechanism does not audit Action
code, workflow behavior or execution order, prove upstream availability, prevent a maintainer
compromise, or authorize workflow output.

## Why this exists

On 2026-08-30, an attempted CodeQL v4 migration used the 40-character object behind the annotated
`v4` tag rather than the tag's dereferenced commit. CodeQL executed, but OpenSSF rejected the result
because that object was not a commit belonging to the named Action repository. The trust lock turns
that production finding into a reusable regression boundary. A later harmless line shift then
exposed a different defect: the 1.0 lock treated presentation coordinates as trust identity. The 1.1
scope-and-ordinal locator preserves the dependency boundary without that false failure mode.

## Sources

- [GitHub secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)
- [GitHub workflow syntax — job IDs, step Actions, and reusable workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [GitHub reusable workflow and YAML-anchor reference](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations)
- [GitHub repository commit API](https://docs.github.com/en/rest/commits/commits#get-a-commit)
- [OpenSSF Scorecard workflow restrictions](https://github.com/ossf/scorecard-action#workflow-restrictions)
