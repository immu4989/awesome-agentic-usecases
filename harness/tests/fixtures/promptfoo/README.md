# Pinned upstream Promptfoo fixture

Retrieved November 19, 2026 from the public Promptfoo repository, commit
`cbf602f0a02691ccf3eb11d3574ae57160f50cc3`:

- [Original sample export](https://github.com/promptfoo/promptfoo/blob/cbf602f0a02691ccf3eb11d3574ae57160f50cc3/test/__fixtures__/sample-export.json)
- [Export types](https://github.com/promptfoo/promptfoo/blob/cbf602f0a02691ccf3eb11d3574ae57160f50cc3/src/types/index.ts)
- [Failure categories](https://github.com/promptfoo/promptfoo/blob/cbf602f0a02691ccf3eb11d3574ae57160f50cc3/src/types/results.ts)
- [Upstream license](https://github.com/promptfoo/promptfoo/blob/cbf602f0a02691ccf3eb11d3574ae57160f50cc3/LICENSE), retained as LICENSE here.

The retained JSON bytes are unchanged, renamed locally to `sample-export-0.118.10.json`.
Both upstream and retained SHA-256:
`60f4c9f191453cbc3ddaa95474828c48734d34f31eaee9e110f27970fe22a9e7`.
Its own metadata declares Promptfoo `0.118.10`; that is a declaration, not a verified runtime.
The file has two tests across two provider columns and four failed assertions. All rows contain
error text, but `failureReason` is ASSERT (1), not ERROR (2). Both columns share a prompt ID;
provider and column identity must therefore be checked too. Scores vary by column.

This public upstream example includes riddle prompts, recorded responses, and upstream author
metadata. It is not agency data, an AAU model run, a newly executed exporter run, or evidence
of all-version compatibility. The regression checks its original bytes; mutation tests are
explicitly synthetic. No credentials, models, endpoints, or Promptfoo installation are used.
