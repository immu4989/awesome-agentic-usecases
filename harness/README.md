# aau-harness

Shared evaluation harness for every use case in this repo. Three pieces:

- `cost.py` — accumulates token usage from API `usage` blocks and prices it in dollars
  at published per-model rates, including prompt-cache reads and writes.
- `runner.py` — runs an eval function across scenarios × repeats and aggregates metrics
  with paired bootstrap confidence intervals. Agents are stochastic; the runner makes
  n≥3 the path of least resistance.
- `report.py` — renders the aggregate into the markdown results table use-case READMEs
  embed.

Install: `pip install -e harness`
