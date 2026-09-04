# Workflow Dependency Trust Lock research notes

Research checked on 2026-09-04. This tool answers a narrow question: do all literal external
GitHub Action references use immutable commits that GitHub resolves inside the repositories named
by the workflow, and does the reviewed inventory still describe the same job-scoped use sites?

## Source-to-control ledger

| Primary source fact | Executable design choice | Explicit non-claim |
|---|---|---|
| GitHub says a full-length commit SHA is the only immutable Action release reference and recommends confirming it belongs to the Action repository | Every external reference must use a lowercase 40-character commit; online mode asks the repository commit endpoint to resolve it | Membership is not source review, maintainer trust, availability, or safety |
| GitHub defines `jobs.<job_id>` as a unique workflow identifier and distinguishes `jobs.<job_id>.steps[*].uses` from job-level reusable-workflow `uses` | A use is located by workflow path, job ID, external-use ordinal, and Action component | The locator does not attest workflow behavior, ordering, permissions, or inputs |
| GitHub supports reusable workflows and YAML anchors as composition mechanisms | Literal step Actions and job-level reusable workflows are inventoried; aliases and merge keys are rejected because this dependency-free scanner does not expand them | Rejection is a parser boundary, not a claim that YAML composition is unsafe |
| Local `./` and `$/` references resolve to repository content rather than a separately fetched external repository | Local references do not consume the external-use ordinal | The trust lock does not review local Action code |

## Premise checks

1. **A line number is not dependency identity.** Comments, blank lines, or a local `run` step can
   move a pinned reference without changing its repository, revision, job, or external-use order.
2. **A stable locator must still detect meaningful drift.** Adding, removing, reordering,
   repinning, changing the Action component, or moving an external use to another job changes the
   scanned inventory and fails verification.
3. **A step name is display text, not a required unique identifier.** The lock does not depend on
   optional names. Job IDs are required and unique; an ordinal distinguishes external uses within
   that job.
4. **Ignoring local uses is not ignoring code.** They remain normal repository content protected by
   review and other checks. They are excluded only from the external repository-origin question.
5. **YAML expansion needs a real parser.** Rather than pretend a regular-expression scanner can
   safely expand aliases, 1.1 rejects structural aliases and merge keys. Block-scalar bodies are
   masked so embedded shell text cannot become a phantom use. Flow-style, quoted-key, multiline,
   or mutable external `uses` values fail the canonical full-SHA syntax boundary.
6. **Origin and signature are distinct observations.** Repository membership is required. GitHub's
   commit-verification result is recorded but is not converted into a universal safe/unsafe label.
7. **The lock is a point-in-time observation.** Scheduled online reverification remains necessary;
   the file does not guarantee future availability or detect later compromise of upstream code or
   infrastructure.

## Official sources

- [GitHub secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)
- [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [GitHub reusable workflow configurations](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations)
- [GitHub REST API — get a commit](https://docs.github.com/en/rest/commits/commits#get-a-commit)
