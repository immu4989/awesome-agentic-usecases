# AAU TEVV-Athlon Profile

This module turns the four stages in the **NIST AI 200-2 initial public draft** into a
machine-readable, artifact-bound profile:

1. **Articulate & Organize** — state the goal, stakeholders, lifecycle, attributes, cost/time
   scope, organizational decision, and challenges.
2. **Define & Construct** — define Metrology Blocks and the exact evidence each Block needs.
3. **Apply & Measure** — connect Events to Blocks, Tools, protocol choices, and public artifacts.
4. **Synthesize & Interrogate** — state how evidence will be jointly analyzed, reported, limited,
   and used by an accountable decision owner.

It is an independent experimental implementation. It is not a NIST validator, NIST conformance,
certification, compliance finding, deployment authorization, or government endorsement.

## Run the reference assessment

```bash
python3 tev-v-athlon-profile/aau_tevva.py validate \
  tev-v-athlon-profile/examples/agent-assurance-tevva.json

python3 tev-v-athlon-profile/aau_tevva.py assess \
  tev-v-athlon-profile/examples/agent-assurance-tevva.json \
  --root . --out /tmp/aau-tevva-assessment.json
```

The reference has six Blocks, three Events, four Tools, and seven byte-verified public artifacts.
It is structurally complete while preserving three visible gaps:

- the outside production-adapter event is planned, not observed;
- the public reference suite is revealed, not held out;
- no outside independent reproduction has been observed.

## Build and verify a self-contained evidence pack

```bash
python3 tev-v-athlon-profile/aau_tevva.py pack \
  tev-v-athlon-profile/examples/agent-assurance-tevva.json \
  --root . --out /tmp/aau-tevva-pack

python3 tev-v-athlon-profile/aau_tevva.py verify-pack /tmp/aau-tevva-pack
```

The pack copies every referenced public artifact without flattening its path, emits a derived
assessment and evidence index, and binds every byte in a manifest. Symlinks, traversal, missing
evidence, hash drift, extra files, and unsupported claims fail closed.

## Time-sensitive standards contribution

NIST opened the draft for public comment on August 7, 2026, with comments due October 6, 2026.
The repository includes an evidence-backed [public comment draft](NIST_AI_200_2_COMMENT_DRAFT.md)
for owner and community review. It has not been submitted.

- [NIST TEVV-Athlon page](https://www.nist.gov/artificial-intelligence/ai-research/tevv-athlon-framework-evaluating-ai-systems)
- [NIST AI 200-2 initial public draft](https://doi.org/10.6028/NIST.AI.200-2.ipd)

The comment package contains no proprietary, operational, personal, controlled, or classified
information.
