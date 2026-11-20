# Inspect interoperability fixture

`scored_0.3.100.json` is a public **mock-model** log from Inspect's own tests. The JSON contents
are unchanged; this copy appends one final LF byte for repository text-file conventions.

- [Pinned upstream file](https://github.com/UKGovernmentBEIS/inspect_ai/blob/c574b6bf6674e6d5f6cbb0f95059d7427b23d54b/tests/sentinel/fixtures/scored_0.3.100.json).
- Upstream revision: `c574b6bf6674e6d5f6cbb0f95059d7427b23d54b`, inspected November 19, 2026.
- Declared producer: `inspect_ai` version `0.3.100`; log version `2`; model `mockllm/model`.
- SHA-256: `2920eb09222718abb780ce7204d744d977594e801393e69767cbdf9bbc4ced7f`.
- Original upstream SHA-256, before the appended LF: `1ed213000785c874c25f46d8a3785934b7c81f5a9e9a8aa90c0de42b9404b5cf`.
- [MIT license](LICENSE), retained from the same upstream revision.

The regression test checks both hashes, reads JSON as data, maps the `graded` numeric score, and checks byte retention
and normalized output. It never executes the task, model, tools, or any code in the log. This is
one observed compatibility case, not proof of support for every Inspect version or schema feature,
nor an independently reproduced evaluation. Do not edit this fixture to make an adapter pass;
make separate synthetic mutations in tests. The packaged demo is separately constructed and
does not claim to be output from Inspect.
