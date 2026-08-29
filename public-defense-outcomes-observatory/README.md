# Public Defense Outcomes Observatory

The observatory counts public evidence artifacts, evidence levels, defensive control shapes, and family-specific observations—without turning heterogeneous tests into a deceptive universal score.

```bash
python aau_outcomes.py evaluate /path/to/evidence-index.json --out /tmp/outcomes.json
python aau_outcomes.py verify /tmp/outcomes.json --index /path/to/evidence-index.json
```

It deliberately:

- counts artifacts, not organizations;
- keeps fix cases, containment events, defense decisions, and benchmark tasks separate;
- shows the absence of independent reproductions as a gap;
- never ranks vendors, agencies, or models;
- never converts a synthetic reference into field effectiveness.

This creates a public learning loop without rewarding inflated claims. A future partner can publish an independently reproduced artifact, but the label is accepted only when its independent-reproduction flag is explicit.
