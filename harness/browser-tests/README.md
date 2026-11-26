# Offline report interaction checks

This suite checks specific browser behavior in synthetic evidence reports. It is **not** a
WCAG or Section 508 conformance assessment, an Accessibility Conformance Report, certification,
screen-reader test, or evidence that users with disabilities have evaluated the workflow.

## Reproduce

From a trusted current checkout, with approved Python tooling and Node.js 20+:

```bash
python -m pip install -e harness
npm ci --prefix harness/browser-tests --ignore-scripts --no-audit --no-fund
harness/browser-tests/node_modules/.bin/playwright install chromium --only-shell
python harness/tools/make_report_accessibility_fixtures.py --out /tmp/aau-report-fixtures
node harness/browser-tests/check-reports.cjs /tmp/aau-report-fixtures
```

Use a new fixture directory. On Linux the browser may need system dependencies; CI uses
Playwright's `install --with-deps chromium --only-shell` on an ephemeral runner. Do not install
software or system packages on restricted systems without approval. Tool/browser installation
may need network access; the report checks run with page scripts disabled, network offline,
and resource requests restricted to the selected local report. This is not an OS-enforced air gap.
Playwright and its transitive packages are pinned with registry integrity values in package-lock.json.
These are optional development/CI dependencies, not dependencies of the AAU Python runtime.

An optional third argument names a **new** screenshot directory:

```bash
node harness/browser-tests/check-reports.cjs /tmp/aau-report-fixtures /tmp/aau-report-screenshots
```

Screenshots remain local unless a user separately chooses to publish them. The suite prints the
actual browser and Playwright versions, tested widths, scroll count, and rejected negative controls.

## Tested scope

Twenty-nine reports cover policy failures and passing results, cohort regressions, diagnostic dossiers,
operating-budget gates, candidate matrices, retry evidence, reference labels, condition coverage,
incomplete Inspect and Promptfoo evidence, source-retaining Promptfoo policy handoffs, paired grader changes, candidate-family uncertainty, paired-system comparisons, evidence indexes,
including native-source missing-conversion and unavailable-context deliveries,
linked grader false passes and substituted reference-label deliveries,
hypothetical evaluation designs (found, bounded-search failure, and benchmark withholding),
and a long-identifier/HTML-escaping stress case. At widths of 1280 and
320 CSS pixels, the checks exercise:

- Document language, title, main landmark, one primary heading, and no page-level horizontal overflow.
- Captions, column headers, row headers, and named focusable scroll groups.
- Real Tab traversal to every table group, arrow-key scrolling of overflowing tables, and leaving
  a group with Tab. Merely calling `focus()` is not the only keyboard reachability check.
- Native disclosure opening with Enter; policy section links must move both location and focus.
- Visible focus outlines, including a forced-colors rendering check.
- Four deliberately broken controls: removed keyboard focus, accessible name, row-header scope,
  and forced page-wide overflow. Each must be detected or the suite fails.

There is no screenshot pixel-baseline gate and no general-purpose accessibility scanner here.
The 320-pixel test is a narrow-layout check, not a claim to have manually tested 400% browser zoom.
Checking a CSS outline does not establish adequate contrast in every browser or operating system.
The four negative controls cover those four mechanisms, not every possible accessibility defect.

Local validation on November 22, 2026 observed one initial ArrowRight failure on an unchanged
policy report. A fresh run passed the unchanged assertions across the then-current seventeen reports; the
cause of the first failure is not established. Failure diagnostics now include focus, scroll
dimensions, and element bounds. There is no automatic whole-test retry or suppression: a future
recurrence must be investigated, not treated as a pass. This remains a browser-test limitation.

## Manual evaluation still required

Before claiming accessibility, qualified reviewers should test the real supported browser/OS and
assistive-technology combinations: screen-reader table navigation and announcements; reading order;
keyboard-only task completion; zoom/text resizing and text spacing; contrast/forced colors; print
output; disclosure discoverability; understandable labels and error recovery. Include users with
disabilities in authorized usability studies. Record barriers and unresolved findings, not just passes.

This change centralizes table behavior for the policy/diagnostic/budget, matrix, reference, coverage,
and Inspect-diagnostic reports. Other repository pages and report families are **not** covered by this
suite. Table groups are named groups rather than dozens of additional navigation landmarks; native
table/caption/header semantics remain intact. Source JSON and policy outcomes are not changed by styling.

Report HTML and manifest bytes do change. Verify older packets with the matching earlier trusted
harness. Do not modify approved or historical evidence in place to make a newer verifier accept it.
The repository's fixed public synthetic examples are regenerated together with their manifests and ZIPs.

## Primary-source rationale

Research checked November 19, 2026:

- [W3C reflow guidance](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) distinguishes page
  reflow from data that needs a two-dimensional layout. We keep wide tables in their own scroll area.
- [W3C table guidance](https://www.w3.org/WAI/tutorials/tables/two-headers/) describes explicit row
  and column headers and captions. Our shared renderer preserves those relationships.
- [W3C focus guidance](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html) explains why
  keyboard users need a visible focus indicator.
- [MDN overflow guidance](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/overflow)
  explains that explicit focusability and a named role help keyboard and screen-reader users navigate
  scrolling containers. Browser defaults alone are not our cross-browser contract.
- [GSA's Section 508 testing playbook](https://www.section508.gov/manage/playbooks/technology-accessibility-playbook/10/)
  says automated checks provide partial coverage and systematic manual testing remains necessary.
- [Playwright keyboard API](https://playwright.dev/docs/api/class-keyboard) and
  [browser installation guidance](https://playwright.dev/docs/browsers) document the test mechanism.

These sources motivate engineering and evaluation choices; they do not certify this repository.
