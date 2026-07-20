# 🎬 Media & Streaming

Agentic use cases for streaming content operations — the pipelines behind the catalogue
rather than the recommendations in front of it. Streaming services ingest thousands of
assets a week from post-production vendors, run them through automated quality control,
and hold every release against delivery specs and accessibility law. Each of those
pipelines has a human triage layer, and that is where these agents sit. Every use case is
verified per [VERIFICATION.md](../VERIFICATION.md).

| Use case | Capability | The question it answers | Status |
|---|---|---|---|
| [🎞️ release-qc-triage-agent](release-qc-triage-agent/) | `investigate` `decide` | When automated QC flags a delivered asset before release, who owns the defect and what happens to the premiere — waive, redeliver, fix in house, delay, or escalate? | ✅ Ready |

**Not in scope here:** recommendations and personalization. Those are ranking systems
measured offline against held-out engagement — there is no tool-using decision loop to
verify, so they fall outside this repo's bar rather than inside it.
