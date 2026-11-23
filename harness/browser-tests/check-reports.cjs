// Targeted browser mechanics, not WCAG/Section 508 conformance or an assistive-technology study.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright');

const REPORTS = [
  'public/unsafe/review.html', 'public/legitimate/review.html',
  'public/cohort-regressed/review.html', 'public/dossier-intermittent/review.html',
  'public/budget-aggregate-trap/review.html', 'public/budget-repaired/review.html',
  'public/budget-matrix/matrix.html', 'public/retry-earlier-harm/review/review.html',
  'reference/packet/review.html', 'coverage/gap/review.html',
  'inspect/diagnostic/review.html', 'stress/review.html',
  'grader-comparison/net-gain-with-regression/review.html',
  'candidate-bounds/pending/review.html', 'candidate-bounds/earlier-failure/review.html',
  'paired-review/net-gain-with-regression/review.html', 'paired-review/fixed-benchmark/review.html',
  'evidence-index/complete-with-failed-policy/review.html', 'evidence-index/missing-coverage/review.html',
  'evaluation-design/planned/review.html', 'evaluation-design/limited/review.html',
  'evaluation-design/fixed-benchmark/review.html',
];

async function inspectStructure(page) {
  const issues = await page.evaluate(() => {
    const failures = [];
    const require = (condition, message) => { if (!condition) failures.push(message); };
    require(document.documentElement.lang === 'en', 'document language');
    require(document.title.trim() && document.querySelectorAll('h1').length === 1, 'page identity');
    require(document.querySelectorAll('main').length === 1, 'main landmark');
    require(!document.querySelector('script,iframe,link[rel="stylesheet"],img,video,audio'), 'external or executable content');
    require(document.documentElement.scrollWidth <= window.innerWidth + 1, 'page-level horizontal overflow');
    const tables = [...document.querySelectorAll('table')];
    require(tables.length > 0, 'no tables checked');
    for (const table of tables) {
      const wrapper = table.parentElement;
      const caption = table.caption?.textContent.trim();
      require(Boolean(caption), 'table caption');
      require(wrapper.classList.contains('scroll') && wrapper.tabIndex === 0, 'table keyboard focus');
      require(wrapper.getAttribute('role') === 'group' && wrapper.getAttribute('aria-label') === `Scrollable table: ${caption}`, 'table accessible name');
      const headers = [...table.querySelectorAll('thead tr > *')];
      require(headers.length > 0 && headers.every(h => h.tagName === 'TH' && h.scope === 'col'), 'column headers');
      for (const row of table.querySelectorAll('tbody tr')) {
        if (row.cells.length === 1 && row.cells[0].colSpan === headers.length) continue;
        require(row.cells.length === headers.length && row.cells[0]?.tagName === 'TH' && row.cells[0].scope === 'row', 'row headers');
      }
    }
    for (const link of document.querySelectorAll('a[href^="#"]')) {
      require(Boolean(document.getElementById(link.hash.slice(1))), 'broken section navigation');
    }
    return failures;
  });
  assert.deepEqual(issues, [], `report structure: ${issues.join(', ')}`);
}

async function exerciseKeyboard(page) {
  const navigation = page.locator('nav.report-nav a');
  for (let i = 0; i < await navigation.count(); i++) {
    const link = navigation.nth(i);
    const fragment = await link.getAttribute('href');
    await link.focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(() => location.hash), fragment, 'section link did not activate with Enter');
    assert.equal(await page.evaluate(() => document.activeElement.id), fragment.slice(1), 'section link did not move focus');
    assert.ok(parseFloat(await page.evaluate(() => getComputedStyle(document.activeElement).outlineWidth)) >= 2,
      'section target has no visible keyboard focus');
  }
  // Open every disclosure through its native keyboard action, not an injected open attribute.
  const summaries = page.locator('summary');
  for (let i = 0; i < await summaries.count(); i++) {
    const summary = summaries.nth(i);
    await summary.focus();
    if (!await summary.evaluate(el => el.parentElement.open)) await page.keyboard.press('Enter');
    assert.equal(await summary.evaluate(el => el.parentElement.open), true, 'disclosure did not open with Enter');
  }
  await inspectStructure(page);
  const groups = page.locator('.scroll');
  let scrolled = 0;
  for (let i = 0; i < await groups.count(); i++) {
    const group = groups.nth(i);
    await group.focus();
    assert.equal(await group.evaluate(el => document.activeElement === el), true, 'table cannot receive focus');
    const outline = await group.evaluate(el => getComputedStyle(el).outlineWidth);
    assert.ok(parseFloat(outline) >= 2, 'keyboard focus indicator missing');
    const overflowing = await group.evaluate(el => el.scrollWidth > el.clientWidth + 2);
    if (overflowing) {
      await group.evaluate(el => { el.scrollLeft = 0; });
      await page.keyboard.press('ArrowRight');
      // Poll from the test process: page animation callbacks may not run with page scripts disabled.
      let moved = false;
      for (let attempt = 0; attempt < 60; attempt++) {
        if (await group.evaluate(el => el.scrollLeft > 0)) { moved = true; break; }
        await new Promise(resolve => setTimeout(resolve, 50));
      }
      const state = moved ? null : await group.evaluate(el => ({
        scrollLeft: el.scrollLeft, scrollWidth: el.scrollWidth, clientWidth: el.clientWidth,
        focused: document.activeElement === el, rect: el.getBoundingClientRect().toJSON(),
      }));
      assert.ok(moved, `arrow key did not scroll table ${i} in ${page.url()}: ${JSON.stringify(state)}`);
      scrolled++;
    }
    await page.keyboard.press('Tab');
    assert.equal(await group.evaluate(el => document.activeElement === el), false, 'keyboard focus trapped in table');
  }
  // Native tab order must reach every scroll group, not only programmatic focus().
  await page.reload();
  await page.locator('summary').evaluateAll(items => items.forEach(el => { el.parentElement.open = true; }));
  const reached = new Set();
  const count = await page.locator('a[href],summary,[tabindex="0"]').count();
  for (let step = 0; step < count + 3; step++) {
    await page.keyboard.press('Tab');
    const index = await page.evaluate(() => [...document.querySelectorAll('.scroll')].indexOf(document.activeElement));
    if (index >= 0) reached.add(index);
  }
  assert.equal(reached.size, await groups.count(), 'tab order omits table groups');
  return scrolled;
}

async function main() {
  const root = path.resolve(process.argv[2] || '');
  assert.ok(process.argv[2] && fs.statSync(root).isDirectory(), 'provide the generated synthetic-fixture directory');
  const screenshots = process.argv[3] ? path.resolve(process.argv[3]) : null;
  if (screenshots) fs.mkdirSync(screenshots, { recursive: false });
  const browser = await chromium.launch({ headless: true });
  let keyboardScrolls = 0;
  try {
    const context = await browser.newContext({ javaScriptEnabled: false, offline: true, reducedMotion: 'reduce' });
    const page = await context.newPage();
    const unexpectedRequests = [];
    let allowedFile = '';
    await page.route('**/*', route => {
      const url = route.request().url().split('#')[0];
      if (url === allowedFile) return route.continue();
      unexpectedRequests.push(url);
      return route.abort();
    });
    for (const relative of REPORTS) {
      allowedFile = pathToFileURL(path.join(root, relative)).href;
      for (const width of [1280, 320]) {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(allowedFile);
        await inspectStructure(page);
        keyboardScrolls += await exerciseKeyboard(page);
        await page.emulateMedia({ forcedColors: 'active' });
        await page.locator('.scroll').first().focus();
        assert.ok(parseFloat(await page.locator('.scroll').first().evaluate(el => getComputedStyle(el).outlineWidth)) >= 2);
        await page.emulateMedia({ forcedColors: 'none' });
        const screenshotName = {
          'public/budget-matrix/matrix.html': 'matrix', 'stress/review.html': 'stress',
          'paired-review/net-gain-with-regression/review.html': 'paired',
          'evidence-index/complete-with-failed-policy/review.html': 'evidence-index',
          'evaluation-design/planned/review.html': 'evaluation-design',
        }[relative];
        if (screenshots && screenshotName) {
          await page.evaluate(() => window.scrollTo(0, 0));
          await page.screenshot({ path: path.join(screenshots, `${screenshotName}-${width}.png`) });
        }
      }
    }
    assert.ok(keyboardScrolls > 0, 'no actual horizontal scrolling was exercised');
    assert.deepEqual(unexpectedRequests, [], 'reports attempted resource or network loads');
    // Negative controls prove the test detects missing focus/name/headers and page-wide overflow.
    allowedFile = pathToFileURL(path.join(root, 'stress/review.html')).href;
    const defects = [
      () => document.querySelector('.scroll').setAttribute('tabindex', '-1'),
      () => document.querySelector('.scroll').removeAttribute('aria-label'),
      () => document.querySelector('tbody th').removeAttribute('scope'),
      () => { document.querySelector('main').style.width = '1600px'; },
    ];
    for (const defect of defects) {
      await page.goto(allowedFile);
      await page.evaluate(defect);
      await assert.rejects(() => inspectStructure(page), /report structure/);
    }
    console.log(JSON.stringify({ reports: REPORTS.length, viewports: [1280, 320], keyboardScrolls,
      rejectedNegativeControls: defects.length, browser: browser.version(), playwright: require('playwright/package.json').version,
      boundary: 'Targeted Chromium DOM, keyboard, focus, disclosure and reflow checks only. Not screen-reader testing, all-browser coverage, WCAG/Section 508 conformance, certification, or user-study evidence.' }));
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
