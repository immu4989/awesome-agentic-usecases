# Federal AI Lessons Exchange

The Lessons Exchange turns a completed public or synthetic pilot into a small, inspectable record
of **what changed, why it changed, what evidence supports the observation, where the practice may
transfer, and where it must not transfer**.

It exists because a pilot can finish without leaving the next team anything safe and useful to
reuse. The exchange keeps the lesson connected to its requirement, synthetic case, public evidence,
human decision, commercial insight, privacy boundary, and dated policy dependencies.

> This is an independent public-learning format. It is not the GSA-managed repository, a system of
> record, a source-selection tool, a vendor comparison, contract language, legal advice, a
> certification, or government approval.

## What ships

- [`lesson-record.schema.json`](../lesson-record.schema.json) — the vendor-neutral public lesson contract.
- [`source-ledger.json`](source-ledger.json) — dated official sources and review dates.
- [`examples/`](examples/) — three reference closeouts and one deliberately stopped synthetic pilot.
- `aau_pilot.py scan-lesson` — structural and narrow sensitive-data screening.
- `aau_pilot.py closeout` — a seven-file, hashed lesson bundle linked to a source exchange.
- `aau_pilot.py verify-closeout` — digest and scan recomputation.
- `aau_pilot.py policy-drift` — source-dependency review-date visibility.
- The browser-local [Lessons Exchange](https://immu4989.github.io/awesome-agentic-usecases/#lessons-exchange)
  — search and filter without uploading a lesson.

## Close a reference pilot

```bash
python federal-pilot-kit/aau_pilot.py scan-lesson \
  federal-pilot-kit/lessons/examples/benefits-accessibility-change.json

python federal-pilot-kit/aau_pilot.py closeout \
  federal-pilot-kit/examples/benefits-correspondence/agency-intake.json \
  federal-pilot-kit/examples/benefits-correspondence/vendor-response.json \
  federal-pilot-kit/examples/benefits-correspondence/acceptance-tests.json \
  federal-pilot-kit/lessons/examples/benefits-accessibility-change.json \
  --out /tmp/aau-benefits-lesson

python federal-pilot-kit/aau_pilot.py verify-closeout /tmp/aau-benefits-lesson
```

## Public-release gate

The deterministic scanner blocks a closeout when it sees common email, Social Security number,
telephone, private-key, GitHub-token, AWS-key, bearer-token, or sensitive-field patterns. It also
requires explicit false attestations for PII, procurement-sensitive information, controlled
unclassified information, classified information, and secrets.

That scanner is deliberately narrow. A zero-finding result is **not** a disclosure, privacy,
records, classification, export-control, procurement-sensitivity, or legal determination. The
record must name the human redaction reviewer and publication authority, and those roles remain
responsible.

## Safe reuse

Every lesson must include prerequisites, limitations, non-transfer conditions, a transfer-test
requirement, dated policy dependencies, and a future review date. A stopped pilot is a useful
lesson. A successful synthetic result is not proof that a practice will work in a different agency,
population, data environment, contract, or operational system.
