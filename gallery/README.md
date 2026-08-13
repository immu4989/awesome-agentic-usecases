# AAU Community Forge Gallery

The Gallery is a public evidence ladder for adaptations created from AAU Studio, AAU Forge,
or a verified reference lab. It is designed to make useful forks discoverable without
turning “verified” into a badge a contributor can select for themselves.

**Every status is computed from committed artifacts.** The entry file supplies attribution,
purpose, and review metadata; `aau gallery validate` inspects the lab, scenarios, results,
failures, source ledger, human boundary, catalog, and CI before deriving the level.

## The evidence ladder

| Level | What it proves | What it does not prove |
|---|---|---|
| **Generated** | A runnable package and contract/provenance record exist. | Domain truth or real-model behavior. |
| **Domain reviewed** | Named review scope and a linked source ledger exist; generated domain placeholders are gone. | Regulator approval, production safety, or model quality. |
| **Reproduced** | ≥20 committed scenarios, a zero-cost run, a real-model result with n≥3, and ≥3 observed failures exist. | Independent model coverage or production validity. |
| **Verified** | All prior checks plus ≥2 measured model IDs, a protected human boundary, and catalog/CI coverage pass. | Certification, endorsement, or permission to automate protected decisions. |

Levels are progressive: an entry cannot skip a lower evidence stage. `Domain reviewed`
means only the named scope in the entry was reviewed; it never means approved by a regulator,
government agency, employer, or production owner.

## Validate the reference entries

```bash
python -m pip install -e harness
aau gallery list
aau gallery validate batch-disposition-reference
aau gallery list --trust Verified
```

The initial cards are explicitly marked `maintainer-reference`. They demonstrate the
submission format and three different reusable contracts; they are not presented as
independent community contributions.

## Publish your adaptation

1. Fork the repository and open it in the included Codespaces/dev-container environment.
2. Use [AAU Studio](https://immu4989.github.io/awesome-agentic-usecases/#studio) and Forge,
   or adapt the closest verified lab by contract and failure shape.
3. Complete the generated `ADAPTATION_CHECKLIST.md`. Use only synthetic or public data.
4. Copy [`gallery-entry.example.json`](gallery-entry.example.json) to
   `gallery/entries/<your-id>.json` and fill in attribution. Leave review fields empty until
   an accountable reviewer has actually completed the stated scope.
5. Run `aau gallery validate <your-id>`. Its output is the evidence claim your card will show.
6. Open a PR using the Gallery checklist. CI rebuilds `docs/gallery-data.json` and rejects
   hand-edited or inflated trust claims.

Community entries use `origin: "forge-adaptation"` and must commit both `aau-forge.json`
and `contract-blueprint.json`. `maintainer-reference` exists only for canonical labs that
predate Forge and is not accepted as a shortcut for new submissions.

### Optional: connect the entry to a Reliability Challenge

Adapt contributors can choose a [Challenge mission](../challenge/README.md), then add
`challenge.id`, `track`, and a narrow `claim` to the Gallery entry. Reproduce and Break use
the lighter Challenge receipt instead. Run `aau challenge validate <entry-id>` after the
normal Gallery check. Finishes and achievements are derived from evidence; maintainers
cannot manually grant them.

## Recognition

Every accepted card links the contributor's GitHub profile and the exact evidence directory.
The public site can be filtered by industry, contract, evidence level, model, and failure
shape. Contributions remain Apache-2.0 under this repository's license; attribution in the
Gallery records who built the adaptation, not ownership of its underlying public rules.
