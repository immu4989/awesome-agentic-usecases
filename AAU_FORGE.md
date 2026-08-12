# AAU Forge

AAU Forge closes the gap between finding a useful evaluation architecture and creating a
working adaptation. It consumes the vendor-neutral brief downloaded from
[AAU Studio](https://immu4989.github.io/awesome-agentic-usecases/#studio) and emits a
runnable lab in your repository fork.

```bash
git clone https://github.com/immu4989/awesome-agentic-usecases.git
cd awesome-agentic-usecases
python -m pip install -e harness[dev]
aau forge ~/Downloads/aau-evaluation-brief.json --name my-workflow-eval
```

By default, Forge imports the generated package directly, creates its committed scenarios,
runs its exact tests, and completes a three-repeat mock evaluation before reporting success.
This verification works without contacting a package registry.

## What Forge creates

- A seeded synthetic world with hidden deciding facts and a shared gold function.
- Strict tools, terminal action semantics, and a deterministic mock with a nonzero gap.
- Tests for determinism, coverage, deception, scoring, schemas, and completion.
- The original Studio brief plus a provenance manifest tied to the source commit and lab.
- A domain-adaptation checklist that protects human authority and primary-source review.
- A standalone GitHub Actions workflow for the new lab.
- README and observed-failure templates that preserve the repository's verification bar.

## The deliberate safety boundary

Forge generates evaluation infrastructure—not domain truth. Every output begins with a
warning and carries `status: adaptation_required` in `aau-forge.json`. The package remains
synthetic and unvalidated until qualified owners replace its generic rules, sources,
authority boundary, scenarios, and failure evidence.

Forge inherits the closest lab's **evaluation shape and contract**. It does not silently
copy that lab's regulatory conclusions into another organization, jurisdiction, or date.

## Useful options

```bash
# Choose a human title or explicit scenario seed
aau forge brief.json --name claims-eval --title "Claims Evidence Gate" --seed 417

# Generate files without installing or executing them
aau forge brief.json --name claims-eval --no-verify

# Equivalent standalone command
aau-forge brief.json --name claims-eval
```

Complete `ADAPTATION_CHECKLIST.md`, replace every `TODO(domain)`, run real models, and
commit scenario-linked failures before proposing the lab as verified evidence.
