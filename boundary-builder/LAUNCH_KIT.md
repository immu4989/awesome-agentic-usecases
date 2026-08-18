# Boundary Builder launch kit

This kit keeps the Boundary Builder story reproducible after launch. Use the static PNG when
platform animation is distracting and the matching GIF when the reveal sequence adds context.
Every asset describes the tool as a local-first evaluation-draft builder—not as a domain
validator, compliance product, or production certification.

| Story | Static | Animated | Best use |
|---|---|---|---|
| Bring a workflow; leave with a fork | [PNG](../docs/assets/boundary-builder-social/launch-hero.png) | [GIF](../docs/assets/boundary-builder-social/launch-hero.gif) | X or LinkedIn launch/update |
| One fact moves the required action | [PNG](../docs/assets/boundary-builder-social/boundary-proof.png) | [GIF](../docs/assets/boundary-builder-social/boundary-proof.gif) | Explain the counterfactual method |
| The eight-file handoff | [PNG](../docs/assets/boundary-builder-social/export-bundle-square.png) | [GIF](../docs/assets/boundary-builder-social/export-bundle-square.gif) | Show what a fork receives |

Editable SVG sources live beside each PNG and GIF. Alt text should describe the specific
diagram rather than repeat post copy.

## Honest launch language

Good:

> Boundary Builder turns one declared workflow boundary into a local eight-file evaluation
> draft. The source and domain review remain yours.

Avoid claims such as “production-ready,” “compliance verified,” “regulator approved,” or
“automatically safe.” Every bundle remains `adaptation_required` until qualified review,
scenario generation, independent evidence, and the repository's verification bar are met.

## Rebuild the GIFs

The PNG files are the design masters used by the deterministic animation script. With Pillow
installed, run:

```bash
python docs/make_boundary_builder_social_gifs.py
```

The generator preserves a readable first frame, reveals the evidence in sequence, pauses on
the complete card, and resets cleanly for a loop. It writes feed-sized GIFs in place without
changing the SVG or PNG masters.
