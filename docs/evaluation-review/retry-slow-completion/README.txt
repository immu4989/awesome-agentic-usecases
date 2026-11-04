AAU retry evaluation handoff

Open review/review.html for policy checks and logical-task operating diagnostics.
The page is self-contained and script-free. It does not verify itself. Using the
same trusted harness, verify the entire folder from its parent:

  aau retry-review verify PATH_TO_THIS_FOLDER

Exit 0: complete source chain verifies and combined policy and candidate budget constraints are met.
Exit 1: complete source chain verifies but combined policy and candidate budget constraints are NOT met or not verified.
Exit 2: invalid inputs, incomplete evidence, or failed verification.

Retain all 31 files. Baseline and candidate each contain their accounting plan,
complete declared retry ledger, recording, evaluation, accounting report, and
manifest. Review contains both derived recordings, policy, diagnostics, and all
derived review files. The outer report, guide, and manifest bind all three folders.
Verification recomputes from both ledgers, not just hashes or standalone reviews.
An individually valid but unrelated nested review cannot replace this source chain.

Each observation is one logical task, not a transport call. Both plans must use
identical metric reducers and sequential_disjoint scope. Last-only metrics can
hide earlier harm; inspect both accounting reports, not only final task scores.
Attempts are not independently executed repeats. No retry is run or authorized.
Costs include every declared attempt only when coverage is complete. Whole-task
latency must be supplied separately; missing measurements remain unknown.

Inspect and independently approve plans, source census, reducers, scoring context,
policy and diagnostic definitions. CLI review can disclose absent context, while
the GitHub Action requires matching declared context and independent approval pins.
Hashes do not establish execution, authenticity, precommitment, scoring validity,
complete external collection, invoice accuracy, or deployment approval. Coordinated
replacement can verify. Both JSON ledgers retain values, not original file bytes.

NOT SANITIZED: all identifiers and source values may be sensitive. Inspect before
sharing. No uploads, model calls, credential use, or automated retries occur.
Interrupted folders are not complete evidence; verification must succeed first.

This handoff includes the candidate operating budget and combined gate. Both policy
and budget must be met independently. Missing required budget evidence cannot pass.
Reject a missing budget layer with: aau retry-review verify PATH_TO_THIS_FOLDER --require-budget
