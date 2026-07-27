---
title: 'aau-harness: reproducible evaluation of LLM agents with programmatic ground truth, measured cost, and observed failure modes'
tags:
  - Python
  - large language models
  - LLM agents
  - evaluation
  - reproducibility
  - benchmarking
authors:
  - name: Fnu Imran Ahamed
    orcid: 0009-0002-7717-7480
    affiliation: 1
affiliations:
  - name: Independent researcher
    index: 1
date: 27 July 2026
bibliography: paper.bib
---

# Summary

`aau-harness` is a Python package for evaluating tool-using large language model (LLM)
agents in a way that a practitioner can act on and a third party can reproduce. It supplies
the machinery an agent evaluation needs and that ad-hoc scripts usually omit: synthetic
worlds generated from a committed seed, ground truth produced by the *same* function the
generator used, cost in dollars computed from measured token usage, repeated runs
aggregated with paired bootstrap confidence intervals [@efron1993], and provenance recorded
alongside every result.

The package ships with a corpus of thirteen agent use cases built on it, spanning seven
industries and several agent shapes — routing and triage, agents that take irreversible
actions, agents that consume a stream and must decide when they have seen enough,
admission gates, multi-agent crews, and controlled adversarial and reliability
experiments. Each use case is admitted to the corpus only if it clears a fixed bar: it runs
from a clean clone with one command and no API key, it has at least twenty scenarios with
programmatic ground truth, it reports cost per run in dollars, it reports at least three
repeated runs with confidence intervals, and it documents at least three failure modes that
were *observed* in a committed run rather than hypothesised.

Because scoring is exact and every scenario file and result is committed, all reported
numbers can be regenerated. Backends for nine providers are included, several of which
expose free tiers with tool-calling models, so a reader can reproduce any result at zero
cost.

# Statement of need

Demonstrations of LLM agents are abundant; evaluations that support a deployment decision
are not. Existing agent benchmarks such as SWE-bench [@jimenez2024], AgentBench [@liu2024],
and $\tau$-bench [@yao2024] are valuable for tracking frontier capability, but they answer
a different question from the one a practitioner faces: not *how capable is this model in
general*, but *how often does this agent get this task right, at what cost, and how does it
fail*. Broad evaluation suites such as HELM [@liang2023] established multi-metric reporting
for language models; the equivalent discipline for agents built on tool use, where the unit
of interest is a decision with consequences rather than a token sequence, is less
established in practice.

Four gaps recur in applied agent evaluation, and `aau-harness` is built to close them.

**Scoring frequently depends on a judge model.** Where a judge is used, its error is
entangled with the agent's. This package instead generates scenarios from seeded rules and
scores against the identical rule function, so the correct answer is known by construction
rather than inferred, and disagreement about a score becomes a question about a committed
rule rather than about a grader.

**Cost is rarely reported despite being decisive.** Cost is accumulated per run from
provider usage fields and priced at published rates. In the corpus this repeatedly changes
conclusions: on one task the cheapest model scored highest, and on another the most
expensive model was last.

**Single runs are reported despite agent stochasticity.** Repeated runs are the default
rather than an option, and confidence intervals are computed by a paired bootstrap over
scenarios so repeats of a scenario stay together.

**Failures are described rather than recorded.** The package encourages, and the corpus
requires, failure modes traceable to a committed run and a reproducing input. Aggregating
these across thirteen use cases produced a cross-cutting taxonomy of eleven recurring
patterns, several observed independently in eight domains — a synthesis that is only
available once many evaluations share one measurement method.

Two safeguards address failure modes of the evaluation process itself, both prompted by
incidents during development. Runs that fail at the transport layer — an expired key, an
exhausted balance — produce a complete, well-formed result of zeros that is
indistinguishable in storage from a model failing every scenario; the harness detects this
and refuses to save such a run. Separately, every result records the model the provider
actually served, because widely used aliases such as `*-latest` resolve to different
weights over time; results obtained against a floating alias are labelled as point-in-time
observations rather than presented as exactly reproducible.

# Functionality

The package provides seeded scenario generation and serialisation; a provider-agnostic
tool-use agent loop handling turn-taking, usage accounting, refusals and non-termination;
cost tracking with cache-aware pricing; repeated-run evaluation with paired bootstrap
confidence intervals; provenance capture; a guard against saving non-measurements; and
backends for Anthropic plus eight OpenAI-compatible providers, including an aggregator
exposing several hundred tool-calling models.

A generator, `aau-new-use-case`, scaffolds a complete new use case — seeded world, shared
gold function, deterministic mock backend with a deliberate engineered gap, and tests
enforcing the properties the bar depends on — then installs it, generates its scenarios,
runs its tests and a mock evaluation, and reports success only if all four pass.

# Limitations

The worlds are synthetic. This is a deliberate trade: it yields exact ground truth and
zero-cost reproduction, and it does not license claims about production traffic. Rules are
authored by the use-case author, and different rules would produce different numbers.
Corpus sample sizes are thirty scenarios by three repeats per model, so intervals are wide
and are reported rather than omitted. A fuller treatment is given in `LIMITATIONS.md`.

# Acknowledgements

This work used free and low-cost inference tiers from several providers, without which
zero-cost reproduction of the corpus would not be possible.

# References
