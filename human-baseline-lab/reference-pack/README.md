# Public Service Routing Human Baseline

> Blinded human-baseline protocol · public or synthetic tasks only

This pack asks a question that model-only leaderboards cannot answer: **how does the agent's
measured performance compare with the existing human process on the same reviewed tasks?**

## Before involving any person

1. Keep `answer-key.json` away from participants.
2. Obtain and record the appropriate institutional determination. Calling an activity
   “evaluation” or “quality improvement” does not decide whether human-subjects rules apply.
3. Use voluntary participation, a withdrawal path, accessible instructions, and no employment
   consequences. Do not collect names, email addresses, demographics, free text, or production
   records in AAU session files.
4. Adapt the measures and task set with a domain owner and human-factors reviewer.
5. Publish only the aggregate report—not participant session files.

The generated pack starts with `review_status: not_determined`. It may be used immediately with
synthetic reference sessions, but **must not be represented as an observed human baseline** until
the responsible institution records its own determination outside this public pack.

## Commands

```bash
python -m pip install aau-harness==1.4.0
aau baseline validate .
aau baseline summarize . --session sessions/session-01.json --out report.json
```

## Files

- `study.json` — blinded task order, inputs, outcomes, measures, and protection boundary.
- `answer-key.json` — separate local scorer; do not show it during a session.
- `session-template.json` — identifier-free response contract.
- `manifest.json` — SHA-256 byte integrity for the pack.

**Boundary:** This blinded synthetic protocol supports baseline design and aggregate measurement. It is not an institutional human-subjects determination, IRB approval, production validation, certification, workforce decision, or authority to deploy AI.
