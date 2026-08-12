# AAU Forge

AAU Forge closes the gap between finding a useful evaluation architecture and creating a
working adaptation. Forge 2 is **contract-aware**: it consumes the vendor-neutral brief downloaded from
[AAU Studio](https://immu4989.github.io/awesome-agentic-usecases/#studio) and emits a
runnable lab whose world, tools, scorecard, tests, and visual explanation match the
recommended reusable contract.

```bash
git clone https://github.com/immu4989/awesome-agentic-usecases.git
cd awesome-agentic-usecases
python -m pip install -e harness[dev]
aau forge ~/Downloads/aau-evaluation-brief.json --name my-workflow-eval
```

By default, Forge imports the generated package directly, creates its committed scenarios,
runs its exact tests, and completes a three-repeat mock evaluation before reporting success.
This verification works without contacting a package registry.

## Three contracts compile to three different labs

| Studio contract | Generated structure | Conjunctive headline |
|---|---|---|
| [Decision Gate](DECISION_GATE_CONTRACT.md) | Evidence registry, hard gate nodes, bounded candidate action, protected decision tool | `decision_gate_exact` |
| [Rights Continuity](RIGHTS_CONTINUITY_CONTRACT.md) | Independent primary/companion rights, triggers, clocks, accessible route, recourse, receipts | `rights_continuity_exact` |
| [Critical Event Fan-Out](CRITICAL_EVENT_FANOUT_CONTRACT.md) | Emergency, initial notification, recipient, update, and follow-up branches with independent receipts | `critical_event_fanout_exact` |

Every supported output includes `contract-blueprint.json`. Other Studio contracts remain
usable through Forge's original generic fallback, explicitly marked `generic-fallback` in
`aau-forge.json` rather than silently pretending to be contract-specific.

## What Forge creates

- A seeded synthetic world with a compiled, machine-checkable contract.
- Strict tools, terminal action semantics, and a deterministic mock with a nonzero gap.
- Contract-specific tests for determinism, node independence, minimum evidence, protected
  authority, strict schemas, and conjunctive scoring.
- The original Studio brief plus a provenance manifest tied to the source commit and lab.
- A domain-adaptation checklist that protects human authority and primary-source review.
- A standalone GitHub Actions workflow for the new lab.
- README and observed-failure templates that preserve the repository's verification bar.

## Forge Doctor

Generation passing is the beginning, not publication approval. Doctor reports the exact
remaining gaps—domain placeholders, scenario volume, real-model evidence, observed
failures, blueprint integrity, and generated verification status:

```bash
aau forge doctor path/to/your-generated-lab
aau-forge doctor path/to/your-generated-lab --json
```

A new lab normally reports `ADAPTATION REQUIRED`. That is intentional: its infrastructure
works, while its domain truth and real-model evidence still belong to qualified owners.

## The deliberate safety boundary

Forge generates evaluation infrastructure—not domain truth. Every output begins with a
warning and carries `status: adaptation_required` in `aau-forge.json`. The package remains
synthetic and unvalidated until qualified owners replace its generic rules, sources,
authority boundary, scenarios, and failure evidence.

Forge inherits the closest lab's **evaluation shape and contract**. It does not silently
copy that lab's regulatory conclusions into another organization, jurisdiction, or date.
For the three compiled contracts, inheritance is structural: the contract topology and
score semantics are reused while every domain rule remains a visible `TODO(domain)`.

## Useful options

```bash
# Choose a human title or explicit scenario seed
aau forge brief.json --name claims-eval --title "Claims Evidence Gate" --seed 417

# Generate files without installing or executing them
aau forge brief.json --name claims-eval --no-verify

# Equivalent standalone command
aau-forge brief.json --name claims-eval
```

Complete `ADAPTATION_CHECKLIST.md`, replace every `TODO(domain)`, run real models, commit
scenario-linked failures, and make Forge Doctor green before proposing the lab as verified evidence.

## Publish the evidence, not a self-selected badge

The [AAU Community Forge Gallery](gallery/README.md) is the public path for useful
adaptations. Add a `gallery/entries/<id>.json` record and run:

```bash
aau gallery validate <id>
```

The validator derives `Generated`, `Domain reviewed`, `Reproduced`, or `Verified` from the
lab's committed provenance, blueprint, source review, scenarios, repeated model results,
observed failures, human boundary, and CI coverage. Contributors cannot set the level in
their entry. Open the
[ready-to-use workspace](https://codespaces.new/immu4989/awesome-agentic-usecases?quickstart=1)
or browse the [live Gallery](https://immu4989.github.io/awesome-agentic-usecases/#gallery).
