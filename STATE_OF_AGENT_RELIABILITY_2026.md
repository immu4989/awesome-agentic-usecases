# State of Agent Reliability 2026

> An automatically generated evidence snapshot from this repository—not a market ranking,
> safety certification, or claim about all agent deployments. [Open the interactive report](https://immu4989.github.io/awesome-agentic-usecases/#reliability).

## The evidence surface

| Committed model evals | Scenario trials | Labs | Industries | Recorded spend | Observed failures |
|---:|---:|---:|---:|---:|---:|
| **202** | **16,278** | **71** | **62** | **$22.84** | **278** |

The snapshot reads every committed, non-mock `eval_*.json` artifact across
71 evidence-backed public labs.
It keeps each lab's metric name and 95% interval visible, and links every plotted value to
the exact source result. Download the same evidence as
[JSON](docs/reliability-data.json) or [CSV](docs/reliability-data.csv).

## Five findings worth acting on

1. **Completion is not correctness.** Across 198 artifacts
   with both endpoints, completion ran **26.6
   points above exact task success** on average. 73 artifacts
   completed at least 95% of runs while exact success remained below 70%.
2. **A perfect finish can still hide a failed task.**
   17 artifacts reached 100% completion with less than
   50% exact success. Status alone is not an outcome metric.
3. **Uncertainty is part of the result.** The median width of the committed 95% interval on
   the selected exact endpoint is **29.9 points**.
   A three-decimal score without its interval overstates what these smoke runs know.
4. **Exceptions dominate the observed cross-industry failures.** “Similarity erases the
   exception” appears in **29 labs**. A rule that works on a
   clean twin is not evidence that it transfers to the nearby exception.
5. **Reproducibility needs an identity check.** 147 of
   202 artifacts carry a provenance stamp; only 74
   record a pinned model snapshot, and 3 record that the
   served model differed from the requested alias.

## Model coverage—not a universal leaderboard

The medians below describe the selected endpoint inside each model's *uneven* evaluation
portfolio. They are useful for coverage and hypothesis generation, not for declaring a winner.
A head-to-head field exists only where two or more models ran the same lab, arm, and source metric.

| Model | Evals | Labs | Median exact (n) | Median completion (n) | Median cost/scenario | Median p50 | Head-to-head wins/fields |
|---|---:|---:|---:|---:|---:|---:|---:|
| mistral-small-latest | 88 | 71 | 0.583 (85) | 1.000 (88) | $0.000391 | 7.93s | 14/78 |
| deepseek-v4-flash | 56 | 49 | 0.795 (56) | 1.000 (56) | $0.000713 | 14.97s | 47/56 |
| gpt-oss-120b | 35 | 18 | 0.574 (34) | 0.678 (35) | $0.001341 | 10.97s | 9/31 |
| Qwen/Qwen3.7-Plus | 11 | 8 | 0.967 (11) | 1.000 (11) | $0.003185 | 29.77s | 8/11 |
| kimi-k2p6 | 7 | 6 | 0.844 (7) | 0.978 (7) | $0.006484 | 17.20s | 3/7 |
| deepseek-chat | 3 | 1 | 0.792 (3) | 0.708 (3) | $0.008783 | 23.79s | 3/3 |
| Llama-3.3-70B-Instruct-Turbo | 1 | 1 | 0.156 (1) | 0.967 (1) | $0.001216 | 4.47s | 0/1 |
| llama-3.3-70b-versatile | 1 | 1 | 0.167 (1) | 0.875 (1) | $0.001395 | 7.92s | 0/1 |

## Most widespread observed failure patterns

| Pattern | Labs | What it catches |
|---|---:|---|
| [Similarity erases the exception](https://github.com/immu4989/awesome-agentic-usecases/blob/main/FAILURE_TAXONOMY.md#similarity-erases-the-exception) | 29 | A valid rule from the clean twin is confidently reused where one deciding fact reverses it. |
| [The outcome can be right while the service fails](https://github.com/immu4989/awesome-agentic-usecases/blob/main/FAILURE_TAXONOMY.md#the-outcome-can-be-right-while-the-service-fails) | 22 | Correct routing can still impose duplicate burden, exclude a user, lose a deadline, or erase recourse. |
| [Stage collapse](https://github.com/immu4989/awesome-agentic-usecases/blob/main/FAILURE_TAXONOMY.md#stage-collapse) | 20 | A draft, attempt, intake, appointment, or handoff is stored as the later event everyone hoped would happen. |
| [One event becomes one obligation](https://github.com/immu4989/awesome-agentic-usecases/blob/main/FAILURE_TAXONOMY.md#one-event-becomes-one-obligation) | 10 | A multi-duty event is flattened into one familiar route, losing an actor, clock, recipient, exception, or parallel protection. |
| [Commit-stall](https://github.com/immu4989/awesome-agentic-usecases/blob/main/FAILURE_TAXONOMY.md#commit-stall) | 9 | The agent investigates correctly, reaches the right conclusion, and never commits it. |

## How to read and reproduce this report

- **Exact, completion, and safety are separate.** The generator chooses the strictest
  available source metric for each view and publishes that metric name. It never averages
  them into one “reliability score.”
- **Inverted risk metrics are explicit.** For safety views, a harmful event rate such as
  `exfiltration_success` is displayed as `1 − rate`; the source name and inversion remain in
  the data.
- **Cost and latency are observed, not normalized.** Provider pricing, cache behavior,
  regions, and floating aliases can change.
- **Failure incidence is repository incidence.** It does not estimate real-world prevalence.
- **Rebuild the complete release:** `python docs/make_reliability_report.py`.
- **Run a source lab at $0:** follow its `eval --backend mock --repeats 3` command.

The selection rules are code, not editorial judgment hidden in a chart. Inspect
[`docs/make_reliability_report.py`](docs/make_reliability_report.py), the
[verification standard](VERIFICATION.md), and the [failure taxonomy](FAILURE_TAXONOMY.md).
