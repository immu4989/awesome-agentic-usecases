const REPO = "https://github.com/immu4989/awesome-agentic-usecases";
const state = {
  cases: [],
  search: "",
  industry: "all",
  compare: [],
  studioInput: null,
  studioMatches: [],
  gallery: [],
  galleryQuery: "",
  galleryTrust: "all",
  galleryContract: "all",
  galleryIndustry: "all",
  galleryModel: "all",
  galleryFailure: "all",
  reliability: null,
  reliabilityMetric: "exact",
  reliabilityModel: "all",
  reliabilityIndustry: "all",
  reliabilityContract: "all",
};

const els = {
  grid: document.querySelector("#grid"),
  count: document.querySelector("#count"),
  search: document.querySelector("#search"),
  industry: document.querySelector("#industry"),
  clear: document.querySelector("#clear"),
  goals: document.querySelectorAll("[data-query]"),
  studioForm: document.querySelector("#studio-form"),
  studioWorkflow: document.querySelector("#studio-workflow"),
  studioIndustry: document.querySelector("#studio-industry"),
  studioShape: document.querySelector("#studio-shape"),
  studioExample: document.querySelector("#studio-example"),
  studioResults: document.querySelector("#studio-results"),
  studioResultTitle: document.querySelector("#studio-result-title"),
  studioResultSummary: document.querySelector("#studio-result-summary"),
  studioMatchGrid: document.querySelector("#studio-match-grid"),
  studioKit: document.querySelector("#studio-kit"),
  studioKitTitle: document.querySelector("#studio-kit-title"),
  studioKitCopy: document.querySelector("#studio-kit-copy"),
  studioCommand: document.querySelector("#studio-command"),
  copyStudioCommand: document.querySelector("#copy-studio-command"),
  downloadStudioSpec: document.querySelector("#download-studio-spec"),
  forgeCommand: document.querySelector("#forge-command"),
  copyForgeCommand: document.querySelector("#copy-forge-command"),
  studioRequest: document.querySelector("#studio-request"),
  galleryGrid: document.querySelector("#gallery-grid"),
  galleryCount: document.querySelector("#gallery-count"),
  gallerySearch: document.querySelector("#gallery-search"),
  galleryTrust: document.querySelector("#gallery-trust"),
  galleryContract: document.querySelector("#gallery-contract"),
  galleryIndustry: document.querySelector("#gallery-industry"),
  galleryModel: document.querySelector("#gallery-model"),
  galleryFailure: document.querySelector("#gallery-failure"),
  galleryTrustLadder: document.querySelector("#gallery-trust-ladder"),
  galleryAdaptations: document.querySelector("#gallery-adaptations"),
  galleryContributors: document.querySelector("#gallery-contributors"),
  galleryContracts: document.querySelector("#gallery-contracts"),
  reliabilityEvals: document.querySelector("#reliability-evals"),
  reliabilityTrials: document.querySelector("#reliability-trials"),
  reliabilityLabs: document.querySelector("#reliability-labs"),
  reliabilityFailures: document.querySelector("#reliability-failures"),
  reliabilitySpend: document.querySelector("#reliability-spend"),
  reliabilityGap: document.querySelector("#reliability-gap"),
  reliabilityGapNote: document.querySelector("#reliability-gap-note"),
  reliabilityCi: document.querySelector("#reliability-ci"),
  reliabilityExceptionLabs: document.querySelector("#reliability-exception-labs"),
  reliabilityPinned: document.querySelector("#reliability-pinned"),
  reliabilityAliasNote: document.querySelector("#reliability-alias-note"),
  reliabilityMetric: document.querySelector("#reliability-metric"),
  reliabilityModel: document.querySelector("#reliability-model"),
  reliabilityIndustry: document.querySelector("#reliability-industry"),
  reliabilityContract: document.querySelector("#reliability-contract"),
  reliabilityReset: document.querySelector("#reliability-reset"),
  reliabilityViewLabel: document.querySelector("#reliability-view-label"),
  reliabilityResultCount: document.querySelector("#reliability-result-count"),
  reliabilityScaleMid: document.querySelector("#reliability-scale-mid"),
  reliabilityScaleMax: document.querySelector("#reliability-scale-max"),
  reliabilityChart: document.querySelector("#reliability-chart"),
  reliabilityChartCaveat: document.querySelector("#reliability-chart-caveat"),
  reliabilityLedger: document.querySelector("#reliability-ledger"),
  reliabilityModels: document.querySelector("#reliability-models"),
  reliabilityPatterns: document.querySelector("#reliability-patterns"),
  copyReliabilityLink: document.querySelector("#copy-reliability-link"),
  compareTray: document.querySelector("#compare-tray"),
  compareCount: document.querySelector("#compare-count"),
  compareNames: document.querySelector("#compare-names"),
  clearCompare: document.querySelector("#clear-compare"),
  openCompare: document.querySelector("#open-compare"),
  compareDialog: document.querySelector("#compare-dialog"),
  compareTable: document.querySelector("#compare-table"),
};

function normalize(text) {
  return String(text || "")
    .toLocaleLowerCase()
    .replace(/[’']/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function terms(text) {
  const stopwords = new Set([
    "agent", "and", "are", "can", "every", "for", "from", "into", "must",
    "only", "our", "should", "that", "the", "their", "this", "with", "without",
  ]);
  return [
    ...new Set(
      normalize(text)
        .split(/\s+/)
        .filter((term) => term.length > 2 && !stopwords.has(term)),
    ),
  ];
}

function searchable(item) {
  return [
    item.title,
    item.industry,
    item.kind,
    item.question,
    item.contract?.name,
    ...item.capabilities,
    ...(item.failure_patterns || []).flatMap((pattern) => [pattern.name, pattern.one_liner]),
  ].join(" ").toLocaleLowerCase();
}

function filteredCases() {
  const queryTerms = terms(state.search);
  return state.cases.filter((item) => {
    const matchesIndustry = state.industry === "all" || item.industry === state.industry;
    const haystack = searchable(item);
    return matchesIndustry && queryTerms.every((term) => haystack.includes(term));
  });
}

function cardAccent(item) {
  const haystack = searchable(item);
  if (/rights.continuity|appeal|companion.right/.test(haystack)) return "#a66cff";
  if (/critical.event|event.fan.out|emergency.response/.test(haystack)) return "#ff7b42";
  if (/clock.collision|obligation.graph|deadline/.test(haystack)) return "#57c7ff";
  if (/public.protection|public.safety|recall.remedy|consumer.rights/.test(haystack)) return "#ff6b4a";
  if (/security|adversarial|injection|exfil|poison/.test(haystack)) return "var(--red)";
  if (/guardrail|environment|tool.enforcement|approval/.test(haystack)) return "var(--green)";
  if (/regulated|statutory|record|compliance|financial/.test(haystack)) return "var(--amber)";
  if (/memory|multi.agent|coordination|context/.test(haystack)) return "var(--violet)";
  return "var(--blue)";
}

function proofBadges(item, compact = false) {
  const evidence = item.evidence;
  const badges = [
    [evidence.real_result_artifacts > 0, `${evidence.real_result_artifacts} real result${evidence.real_result_artifacts === 1 ? "" : "s"}`],
    [evidence.reproducible_scenarios, `${evidence.scenario_count} seeded scenarios`],
    [evidence.observed_failure_modes > 0, `${evidence.observed_failure_modes} observed failures`],
    [evidence.official_sources, "official sources"],
    [evidence.human_boundary, "human boundary"],
    [evidence.mock_available, "$0 mock"],
  ].filter(([show]) => show);
  return badges.slice(0, compact ? 4 : badges.length);
}

function makeBadge(label, className = "proof-badge") {
  const badge = document.createElement("span");
  badge.className = className;
  badge.textContent = label;
  return badge;
}

function renderTrustLadder(levels) {
  const descriptions = {
    "Generated": "Runnable package + provenance",
    "Domain reviewed": "Named scope + source ledger",
    "Reproduced": "Scenarios + repeated model run + failures",
    "Verified": "Independent models + boundary + CI",
  };
  els.galleryTrustLadder.replaceChildren(...levels.map((level, index) => {
    const item = document.createElement("div");
    item.className = `trust-step trust-${normalize(level).replaceAll(" ", "-")}`;
    item.innerHTML = `<span>0${index + 1}</span><div><b>${level}</b><small>${descriptions[level]}</small></div>${index < levels.length - 1 ? "<i>→</i>" : ""}`;
    return item;
  }));
}

function galleryHaystack(item) {
  return normalize([
    item.title,
    item.industry,
    item.contract.name,
    item.summary,
    item.why_fork,
    item.contributor.name,
    item.contributor.github,
    ...item.tags,
    ...item.evidence.models,
    ...(item.failure_patterns || []).flatMap((pattern) => [pattern.name, pattern.one_liner]),
  ].join(" "));
}

function filteredGallery() {
  const queryTerms = terms(state.galleryQuery);
  return state.gallery.filter((item) => (
    queryTerms.every((term) => galleryHaystack(item).includes(term))
    && (state.galleryTrust === "all" || item.trust.level === state.galleryTrust)
    && (state.galleryContract === "all" || item.contract.name === state.galleryContract)
    && (state.galleryIndustry === "all" || item.industry === state.galleryIndustry)
    && (state.galleryModel === "all" || item.evidence.models.includes(state.galleryModel))
    && (state.galleryFailure === "all" || (item.failure_patterns || []).some((pattern) => pattern.id === state.galleryFailure))
  ));
}

function trustClass(level) {
  return `trust-${normalize(level).replaceAll(" ", "-")}`;
}

function galleryCard(item, index) {
  const article = document.createElement("article");
  article.className = "gallery-card";
  article.style.setProperty("--gallery-accent", cardAccent({
    ...item,
    kind: `${item.contract.name} ${item.tags.join(" ")}`,
    capabilities: item.tags,
  }));

  const top = document.createElement("div");
  top.className = "gallery-card-top";
  const number = document.createElement("span");
  number.textContent = `ADAPTATION ${String(index + 1).padStart(2, "0")}`;
  const trust = document.createElement("b");
  trust.className = `gallery-trust-badge ${trustClass(item.trust.level)}`;
  trust.textContent = `${item.trust.level} · ${item.trust.score.passed}/${item.trust.score.total}`;
  trust.title = "Computed from committed Gallery evidence checks";
  top.append(number, trust);

  const heading = document.createElement("h3");
  heading.textContent = `${item.icon} ${item.title}`;
  const meta = document.createElement("p");
  meta.className = "gallery-card-meta";
  meta.textContent = `${item.industry} · ${item.contract.name}`;
  const summary = document.createElement("p");
  summary.className = "gallery-card-summary";
  summary.textContent = item.summary;

  const fork = document.createElement("div");
  fork.className = "gallery-fork-note";
  const forkLabel = document.createElement("span");
  forkLabel.textContent = "WHY FORK THIS";
  const forkCopy = document.createElement("p");
  forkCopy.textContent = item.why_fork;
  fork.append(forkLabel, forkCopy);

  const evidence = document.createElement("div");
  evidence.className = "gallery-evidence";
  const evidenceItems = [
    [String(item.evidence.scenario_count), "scenarios"],
    [String(item.evidence.model_count), "models"],
    [String(item.evidence.observed_failure_modes), "failures"],
    [`n≥${item.evidence.minimum_repeats}`, "repeats"],
  ];
  for (const [value, label] of evidenceItems) {
    const cell = document.createElement("span");
    cell.innerHTML = `<b>${value}</b><small>${label}</small>`;
    evidence.append(cell);
  }

  const tags = document.createElement("div");
  tags.className = "gallery-tags";
  for (const label of item.tags) tags.append(makeBadge(label, "gallery-tag"));

  const contributor = document.createElement("div");
  contributor.className = "gallery-contributor";
  const origin = document.createElement("span");
  origin.textContent = item.origin === "maintainer-reference" ? "MAINTAINER REFERENCE" : "COMMUNITY ADAPTATION";
  const profile = document.createElement("a");
  profile.href = item.contributor.profile_url;
  profile.textContent = `@${item.contributor.github} ↗`;
  contributor.append(origin, profile);

  const actions = document.createElement("div");
  actions.className = "gallery-card-actions";
  const open = document.createElement("a");
  open.className = "button primary";
  open.href = `${REPO}/tree/main/${item.lab_path}`;
  open.textContent = "Inspect evidence ↗";
  const copy = document.createElement("button");
  copy.className = "button secondary";
  copy.type = "button";
  copy.textContent = "Copy $0 run";
  copy.addEventListener("click", () => copyText(item.commands.run, copy, "Copy $0 run"));
  const checks = document.createElement("a");
  checks.className = "gallery-check-link";
  checks.href = `${REPO}/blob/main/gallery/entries/${item.id}.json`;
  checks.textContent = "Audit trust record ↗";
  actions.append(open, copy, checks);
  article.append(top, heading, meta, summary, fork, evidence, tags, contributor, actions);
  return article;
}

function renderGallery() {
  const entries = filteredGallery();
  els.galleryGrid.replaceChildren();
  els.galleryCount.textContent = `${entries.length} of ${state.gallery.length} evidence-scored adaptations`;
  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "gallery-empty";
    empty.textContent = "No adaptation matches those filters. Clear a filter—or become the contributor who adds it.";
    els.galleryGrid.append(empty);
    return;
  }
  els.galleryGrid.append(...entries.map(galleryCard));
}

function addGalleryOptions(select, values) {
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  }
}

async function loadGallery() {
  const response = await fetch("gallery-data.json?v=2");
  if (!response.ok) throw new Error(`Gallery evidence failed to load (${response.status})`);
  const data = await response.json();
  state.gallery = data.entries;
  els.galleryAdaptations.textContent = data.stats.adaptations;
  els.galleryContributors.textContent = data.stats.contributors;
  els.galleryContracts.textContent = data.stats.contracts;
  renderTrustLadder(data.trust_model.levels);
  addGalleryOptions(els.galleryTrust, data.trust_model.levels);
  addGalleryOptions(els.galleryContract, [...new Set(state.gallery.map((item) => item.contract.name))].sort());
  addGalleryOptions(els.galleryIndustry, [...new Set(state.gallery.map((item) => item.industry))].sort());
  addGalleryOptions(els.galleryModel, [...new Set(state.gallery.flatMap((item) => item.evidence.models))].sort());
  const patterns = new Map(state.gallery.flatMap((item) => (item.failure_patterns || []).map((pattern) => [pattern.id, pattern.name])));
  for (const [id, label] of [...patterns.entries()].sort((a, b) => a[1].localeCompare(b[1]))) {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = label;
    els.galleryFailure.append(option);
  }
  els.gallerySearch.addEventListener("input", () => { state.galleryQuery = els.gallerySearch.value; renderGallery(); });
  for (const [control, key] of [
    [els.galleryTrust, "galleryTrust"],
    [els.galleryContract, "galleryContract"],
    [els.galleryIndustry, "galleryIndustry"],
    [els.galleryModel, "galleryModel"],
    [els.galleryFailure, "galleryFailure"],
  ]) control.addEventListener("change", () => { state[key] = control.value; renderGallery(); });
  renderGallery();
}

function medianValue(values) {
  const clean = values.filter((value) => Number.isFinite(value)).sort((a, b) => a - b);
  if (!clean.length) return null;
  const middle = Math.floor(clean.length / 2);
  return clean.length % 2 ? clean[middle] : (clean[middle - 1] + clean[middle]) / 2;
}

function formatScore(value) {
  return Number.isFinite(value) ? value.toFixed(3) : "—";
}

function formatMoney(value) {
  if (!Number.isFinite(value)) return "—";
  if (value >= 1) return `$${value.toFixed(2)}`;
  if (value >= 0.01) return `$${value.toFixed(3)}`;
  return `$${value.toFixed(6)}`;
}

function formatCount(value) {
  return Number(value).toLocaleString("en-US");
}

function reliabilityMetricValue(item, metric = state.reliabilityMetric) {
  if (["exact", "completion", "safety"].includes(metric)) return item.dimensions[metric]?.value ?? null;
  if (metric === "cost") return item.mean_cost_usd;
  return item.p50_latency_s;
}

function filteredReliability() {
  if (!state.reliability) return [];
  return state.reliability.evaluations.filter((item) => (
    (state.reliabilityModel === "all" || item.model === state.reliabilityModel)
    && (state.reliabilityIndustry === "all" || item.industry === state.reliabilityIndustry)
    && (state.reliabilityContract === "all" || item.contract === state.reliabilityContract)
  ));
}

function reliabilityColor(metric) {
  return {
    exact: "#d9ff67",
    completion: "#48d9ff",
    safety: "#c0a3ff",
    cost: "#ff6e9f",
    latency: "#ffb45f",
  }[metric];
}

function reliabilityMetricLabel(metric) {
  return {
    exact: "Exact task success",
    completion: "Completion",
    safety: "Safety / boundary preservation",
    cost: "Cost per scenario",
    latency: "P50 latency",
  }[metric];
}

function syncReliabilityUrl() {
  const params = new URLSearchParams(location.search);
  for (const key of ["rmetric", "rmodel", "rindustry", "rcontract"]) params.delete(key);
  if (state.reliabilityMetric !== "exact") params.set("rmetric", state.reliabilityMetric);
  if (state.reliabilityModel !== "all") params.set("rmodel", state.reliabilityModel);
  if (state.reliabilityIndustry !== "all") params.set("rindustry", state.reliabilityIndustry);
  if (state.reliabilityContract !== "all") params.set("rcontract", state.reliabilityContract);
  history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}#reliability`);
}

function reliabilityBar(item, value, maximum) {
  const metric = state.reliabilityMetric;
  const scoreView = ["exact", "completion", "safety"].includes(metric);
  const endpoint = scoreView ? item.dimensions[metric] : null;
  const width = maximum > 0 ? Math.max(0, Math.min(100, (value / maximum) * 100)) : 0;
  const link = document.createElement("a");
  link.className = "reliability-bar-row";
  link.href = item.result_url;
  link.style.setProperty("--bar-color", reliabilityColor(metric));
  link.setAttribute("aria-label", `Open source result for ${item.title}, ${item.model_display}`);

  const label = document.createElement("span");
  label.className = "reliability-bar-label";
  const title = document.createElement("b");
  title.textContent = item.title;
  const detail = document.createElement("small");
  const metricName = endpoint ? `${endpoint.inverted ? "1 − " : ""}${endpoint.metric}` : metric;
  detail.textContent = `${item.model_display} · ${item.arm} · ${metricName}`;
  label.append(title, detail);

  const track = document.createElement("span");
  track.className = "reliability-bar-track";
  const fill = document.createElement("i");
  fill.className = "reliability-bar-fill";
  fill.style.setProperty("--bar-width", `${width}%`);
  track.append(fill);
  if (endpoint?.ci95) {
    const interval = document.createElement("i");
    interval.className = "reliability-bar-ci";
    interval.style.setProperty("--ci-left", `${endpoint.ci95[0] * 100}%`);
    interval.style.setProperty("--ci-width", `${Math.max(0.3, (endpoint.ci95[1] - endpoint.ci95[0]) * 100)}%`);
    track.append(interval);
  }

  const shown = document.createElement("b");
  shown.className = "reliability-bar-value";
  shown.textContent = scoreView ? formatScore(value) : metric === "cost" ? formatMoney(value) : `${value.toFixed(2)}s`;
  link.append(label, track, shown);
  return link;
}

function ledgerCell(label, value) {
  const cell = document.createElement("div");
  cell.className = "ledger-cell";
  const small = document.createElement("small");
  small.textContent = label;
  const bold = document.createElement("b");
  bold.textContent = value;
  cell.append(small, bold);
  return cell;
}

function renderReliabilityLedger(items) {
  const values = (dimension) => items
    .map((item) => item.dimensions[dimension]?.value)
    .filter((value) => Number.isFinite(value));
  const paired = items.filter((item) => item.dimensions.exact && item.dimensions.completion);
  const gap = paired.length ? paired.reduce((total, item) => (
    total + item.dimensions.completion.value - item.dimensions.exact.value
  ), 0) / paired.length : null;
  els.reliabilityLedger.replaceChildren(
    ledgerCell("Result artifacts", formatCount(items.length)),
    ledgerCell("Labs represented", formatCount(new Set(items.map((item) => item.lab_path)).size)),
    ledgerCell("Median exact", formatScore(medianValue(values("exact")))),
    ledgerCell("Median completion", formatScore(medianValue(values("completion")))),
    ledgerCell("Completion − exact", gap === null ? "—" : `${(gap * 100).toFixed(1)} pt`),
    ledgerCell("Median cost / case", formatMoney(medianValue(items.map((item) => item.mean_cost_usd)))),
    ledgerCell("Median p50", `${(medianValue(items.map((item) => item.p50_latency_s)) ?? 0).toFixed(2)}s`),
  );
}

function renderReliabilityChart(items) {
  const metric = state.reliabilityMetric;
  const scoreView = ["exact", "completion", "safety"].includes(metric);
  const available = items
    .map((item) => ({ item, value: reliabilityMetricValue(item) }))
    .filter(({ value }) => Number.isFinite(value))
    .sort((a, b) => (scoreView ? a.value - b.value : b.value - a.value) || a.item.title.localeCompare(b.item.title));
  const maximum = scoreView ? 1 : Math.max(...available.map(({ value }) => value), 0);
  const shown = available.slice(0, 18);
  els.reliabilityViewLabel.textContent = reliabilityMetricLabel(metric).toLocaleUpperCase();
  els.reliabilityResultCount.textContent = `Showing ${shown.length} ${scoreView ? "lowest" : "highest"} of ${available.length} source-linked artifacts`;
  els.reliabilityScaleMid.textContent = scoreView ? ".50" : metric === "cost" ? formatMoney(maximum / 2) : `${(maximum / 2).toFixed(1)}s`;
  els.reliabilityScaleMax.textContent = scoreView ? "1.00" : metric === "cost" ? formatMoney(maximum) : `${maximum.toFixed(1)}s`;
  els.reliabilityChartCaveat.textContent = scoreView
    ? "Selected endpoints remain lab-specific. White whiskers show committed 95% intervals; open any row to audit the source metric and trace."
    : "Observed values are not normalized for provider, region, cache behavior, pricing changes, or task length. Open any row to audit the artifact.";
  if (!shown.length) {
    const empty = document.createElement("div");
    empty.className = "reliability-empty";
    empty.textContent = "No committed artifact in this filter reports the selected view. Missing coverage stays missing—it is never rendered as zero.";
    els.reliabilityChart.replaceChildren(empty);
    return;
  }
  els.reliabilityChart.replaceChildren(...shown.map(({ item, value }) => reliabilityBar(item, value, maximum)));
}

function modelCard(model, items, index) {
  const colors = ["#d9ff67", "#48d9ff", "#ff6e9f", "#c0a3ff", "#ffb45f", "#56e49c", "#7eb0ff", "#f6e27f"];
  const article = document.createElement("article");
  article.className = "reliability-model-card";
  article.style.setProperty("--model-color", colors[index % colors.length]);
  const coverage = document.createElement("span");
  const labCount = new Set(items.map((item) => item.lab_path)).size;
  coverage.textContent = `${items.length} EVAL${items.length === 1 ? "" : "S"} / ${labCount} LAB${labCount === 1 ? "" : "S"}`;
  const heading = document.createElement("h4");
  heading.textContent = items[0].model_display;
  const metricValues = items.map((item) => reliabilityMetricValue(item)).filter((value) => Number.isFinite(value));
  const score = medianValue(metricValues);
  const scoreWrap = document.createElement("div");
  scoreWrap.className = "model-card-score";
  const scoreValue = document.createElement("b");
  scoreValue.textContent = ["exact", "completion", "safety"].includes(state.reliabilityMetric)
    ? formatScore(score)
    : state.reliabilityMetric === "cost" ? formatMoney(score) : score === null ? "—" : `${score.toFixed(2)}s`;
  const scoreLabel = document.createElement("small");
  scoreLabel.textContent = `median ${reliabilityMetricLabel(state.reliabilityMetric)} · n=${metricValues.length}`;
  scoreWrap.append(scoreValue, scoreLabel);
  const proof = document.createElement("div");
  proof.className = "model-card-proof";
  for (const [value, label] of [
    [formatCount(items.reduce((total, item) => total + item.scenario_trials, 0)), "scenario trials"],
    [formatMoney(medianValue(items.map((item) => item.mean_cost_usd))), "median cost / case"],
    [`${(medianValue(items.map((item) => item.p50_latency_s)) ?? 0).toFixed(2)}s`, "median p50"],
    [String(new Set(items.map((item) => item.industry)).size), "industries"],
  ]) {
    const cell = document.createElement("span");
    cell.innerHTML = `<b>${value}</b><small>${label}</small>`;
    proof.append(cell);
  }
  const link = document.createElement("a");
  link.className = "model-card-link";
  const params = new URLSearchParams();
  params.set("rmodel", model);
  if (state.reliabilityMetric !== "exact") params.set("rmetric", state.reliabilityMetric);
  link.href = `?${params}#reliability`;
  link.textContent = "Open report card →";
  article.append(coverage, heading, scoreWrap, proof, link);
  return article;
}

function renderReliabilityModels(items) {
  const groups = new Map();
  for (const item of items) {
    if (!groups.has(item.model)) groups.set(item.model, []);
    groups.get(item.model).push(item);
  }
  const models = [...groups.entries()].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]));
  if (!models.length) {
    const empty = document.createElement("div");
    empty.className = "reliability-empty";
    empty.textContent = "No models match this evidence slice.";
    els.reliabilityModels.replaceChildren(empty);
    return;
  }
  els.reliabilityModels.replaceChildren(...models.map(([model, group], index) => modelCard(model, group, index)));
}

function renderReliabilityPatterns() {
  const patterns = state.reliability.failure_patterns.filter((pattern) => (
    (state.reliabilityIndustry === "all" || pattern.industries.includes(state.reliabilityIndustry))
    && (state.reliabilityContract === "all" || pattern.contracts.includes(state.reliabilityContract))
  )).slice(0, 6);
  const cards = patterns.map((pattern, index) => {
    const link = document.createElement("a");
    link.className = "reliability-pattern-card";
    link.href = pattern.url;
    const top = document.createElement("span");
    top.innerHTML = `<i>0${index + 1}</i><b>${pattern.use_case_count}</b>`;
    const heading = document.createElement("h4");
    heading.textContent = pattern.name;
    const copy = document.createElement("p");
    copy.textContent = pattern.one_liner;
    link.append(top, heading, copy);
    return link;
  });
  if (!cards.length) {
    const empty = document.createElement("div");
    empty.className = "reliability-empty";
    empty.textContent = "No cross-lab taxonomy pattern is assigned to this filter yet. Inspect the source artifacts for case-specific failures.";
    els.reliabilityPatterns.replaceChildren(empty);
    return;
  }
  els.reliabilityPatterns.replaceChildren(...cards);
}

function renderReliability() {
  const items = filteredReliability();
  renderReliabilityChart(items);
  renderReliabilityLedger(items);
  renderReliabilityModels(items);
  renderReliabilityPatterns();
}

function addReliabilityOptions(select, values, display = (value) => value) {
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = display(value);
    select.append(option);
  }
}

async function loadReliability() {
  const response = await fetch("reliability-data.json?v=1");
  if (!response.ok) throw new Error(`Reliability evidence failed to load (${response.status})`);
  state.reliability = await response.json();
  const { stats } = state.reliability;
  els.reliabilityEvals.textContent = formatCount(stats.evaluations);
  els.reliabilityTrials.textContent = formatCount(stats.scenario_trials);
  els.reliabilityLabs.textContent = formatCount(stats.labs);
  els.reliabilityFailures.textContent = formatCount(stats.failure_modes);
  els.reliabilitySpend.textContent = `$${stats.recorded_spend_usd.toFixed(2)}`;
  els.reliabilityGap.textContent = stats.mean_completion_exact_gap_points.toFixed(1);
  els.reliabilityGapNote.textContent = `${stats.high_completion_low_exact} artifacts finish ≥95% while exact success stays <70%`;
  els.reliabilityCi.textContent = stats.median_exact_ci_width_points.toFixed(1);
  const exceptionPattern = state.reliability.failure_patterns.find((pattern) => pattern.id === "rule-transfer");
  els.reliabilityExceptionLabs.textContent = exceptionPattern?.use_case_count ?? "—";
  els.reliabilityPinned.textContent = `${stats.model_pinned}/${stats.evaluations}`;
  els.reliabilityAliasNote.textContent = `${stats.served_alias_mismatches} served-model alias mismatches are recorded`;

  addReliabilityOptions(
    els.reliabilityModel,
    [...new Set(state.reliability.evaluations.map((item) => item.model))].sort(),
    (model) => state.reliability.evaluations.find((item) => item.model === model).model_display,
  );
  addReliabilityOptions(els.reliabilityIndustry, [...new Set(state.reliability.evaluations.map((item) => item.industry))].sort());
  addReliabilityOptions(els.reliabilityContract, [...new Set(state.reliability.evaluations.map((item) => item.contract))].sort());

  const params = new URLSearchParams(location.search);
  const metric = params.get("rmetric");
  if (["exact", "completion", "safety", "cost", "latency"].includes(metric)) state.reliabilityMetric = metric;
  const model = params.get("rmodel");
  const industry = params.get("rindustry");
  const contract = params.get("rcontract");
  if ([...els.reliabilityModel.options].some((option) => option.value === model)) state.reliabilityModel = model;
  if ([...els.reliabilityIndustry.options].some((option) => option.value === industry)) state.reliabilityIndustry = industry;
  if ([...els.reliabilityContract.options].some((option) => option.value === contract)) state.reliabilityContract = contract;
  els.reliabilityMetric.value = state.reliabilityMetric;
  els.reliabilityModel.value = state.reliabilityModel;
  els.reliabilityIndustry.value = state.reliabilityIndustry;
  els.reliabilityContract.value = state.reliabilityContract;

  for (const [control, key] of [
    [els.reliabilityMetric, "reliabilityMetric"],
    [els.reliabilityModel, "reliabilityModel"],
    [els.reliabilityIndustry, "reliabilityIndustry"],
    [els.reliabilityContract, "reliabilityContract"],
  ]) control.addEventListener("change", () => {
    state[key] = control.value;
    syncReliabilityUrl();
    renderReliability();
  });
  els.reliabilityReset.addEventListener("click", () => {
    state.reliabilityMetric = "exact";
    state.reliabilityModel = "all";
    state.reliabilityIndustry = "all";
    state.reliabilityContract = "all";
    els.reliabilityMetric.value = "exact";
    els.reliabilityModel.value = "all";
    els.reliabilityIndustry.value = "all";
    els.reliabilityContract.value = "all";
    syncReliabilityUrl();
    renderReliability();
  });
  els.copyReliabilityLink.addEventListener("click", () => copyText(location.href, els.copyReliabilityLink, "Copy report link"));
  renderReliability();
}

async function copyText(text, control, defaultLabel) {
  try {
    await navigator.clipboard.writeText(text);
    control.textContent = "Copied";
  } catch {
    control.textContent = text;
  }
  setTimeout(() => { control.textContent = defaultLabel; }, 1800);
}

function isCompared(path) {
  return state.compare.includes(path);
}

function toggleCompare(item, button) {
  if (isCompared(item.path)) {
    state.compare = state.compare.filter((path) => path !== item.path);
  } else if (state.compare.length < 3) {
    state.compare.push(item.path);
  } else {
    button.textContent = "Limit: 3";
    setTimeout(() => { button.textContent = "+ Compare"; }, 1400);
    return;
  }
  renderCompareTray();
  render();
  if (!els.studioResults.hidden) renderStudioResults(state.studioMatches, false);
}

function compareButton(item) {
  const button = document.createElement("button");
  button.className = `compare-toggle${isCompared(item.path) ? " selected" : ""}`;
  button.type = "button";
  button.textContent = isCompared(item.path) ? "✓ Selected" : "+ Compare";
  button.setAttribute("aria-pressed", String(isCompared(item.path)));
  button.setAttribute("aria-label", `${isCompared(item.path) ? "Remove" : "Add"} ${item.title} ${isCompared(item.path) ? "from" : "to"} comparison`);
  button.addEventListener("click", () => toggleCompare(item, button));
  return button;
}

function card(item) {
  const article = document.createElement("article");
  article.className = "card";
  article.style.setProperty("--card-accent", cardAccent(item));

  const top = document.createElement("div");
  top.className = "card-top";
  const icon = document.createElement("span");
  icon.className = "icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = item.icon;
  const kind = document.createElement("span");
  kind.className = "kind";
  kind.textContent = item.kind;
  top.append(icon, kind);

  const heading = document.createElement("h2");
  heading.textContent = item.title;
  const industry = document.createElement("div");
  industry.className = "industry";
  industry.textContent = item.industry;
  const question = document.createElement("p");
  question.className = "question";
  question.textContent = item.question;
  const tags = document.createElement("div");
  tags.className = "tags";
  for (const capability of item.capabilities.slice(0, 5)) tags.append(makeBadge(capability, "tag"));

  const proofs = document.createElement("div");
  proofs.className = "card-proofs";
  for (const [, label] of proofBadges(item, true)) proofs.append(makeBadge(label));

  const link = document.createElement("a");
  link.className = "card-link";
  link.href = `${REPO}/tree/main/${item.path}`;
  link.textContent = "Open case →";
  link.setAttribute("aria-label", `Open ${item.title} on GitHub`);

  const copy = document.createElement("button");
  copy.className = "copy";
  copy.type = "button";
  copy.textContent = "Copy run";
  copy.setAttribute("aria-label", `Copy the zero-cost run command for ${item.title}`);
  copy.addEventListener("click", () => copyText(item.commands.evaluate, copy, "Copy run"));

  const actions = document.createElement("div");
  actions.className = "card-actions";
  const utility = document.createElement("div");
  utility.className = "card-utility";
  utility.append(compareButton(item), copy);
  actions.append(link, utility);
  article.append(top, heading, industry, question, tags, proofs, actions);
  return article;
}

function render() {
  const items = filteredCases();
  els.grid.replaceChildren();
  els.count.innerHTML = `<strong>${items.length}</strong> of ${state.cases.length} verified use cases`;
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No use case matches those filters. Try the Studio above, or search a consequence such as deadline, security, receipt, evidence, or accessibility.";
    els.grid.append(empty);
    return;
  }
  els.grid.append(...items.map(card));
}

function syncUrl() {
  const params = new URLSearchParams();
  if (state.search) params.set("q", state.search);
  if (state.industry !== "all") params.set("industry", state.industry);
  history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}${location.hash}`);
}

function selectedRisks() {
  return [...document.querySelectorAll('[name="studio-risk"]:checked')].map((input) => input.value);
}

function rankStudioCases(input) {
  const workflowTerms = terms(input.workflow);
  const shapeTerms = input.shape === "auto" ? [] : terms(input.shape);
  const riskTerms = terms(input.risks.join(" "));
  return state.cases.map((item) => {
    const haystack = searchable(item);
    let raw = 0;
    const reasons = [];
    const exactIndustry = input.industry !== "all" && item.industry === input.industry;
    const partialIndustry = input.industry !== "all" && (
      normalize(item.industry).includes(normalize(input.industry)) || normalize(input.industry).includes(normalize(item.industry))
    );
    if (exactIndustry) { raw += 42; reasons.push("same industry"); }
    else if (partialIndustry) { raw += 25; reasons.push("related industry"); }

    const workflowHits = workflowTerms.filter((term) => haystack.includes(term));
    const shapeHits = shapeTerms.filter((term) => haystack.includes(term));
    const riskHits = riskTerms.filter((term) => haystack.includes(term));
    raw += Math.min(36, workflowHits.length * 6);
    raw += Math.min(24, shapeHits.length * 8);
    raw += Math.min(30, riskHits.length * 6);
    if (workflowHits.length) reasons.push(`${workflowHits.slice(0, 3).join(", ")} signal${workflowHits.length > 1 ? "s" : ""}`);
    if (shapeHits.length) reasons.push(`${item.kind} shape`);
    if (riskHits.length) reasons.push(`${riskHits.slice(0, 2).join(" + ")} risk`);
    if (item.featured) raw += 2;
    if (item.evidence.official_sources && /regulated|deadline|rights|safety|compliance|medical|public/.test(normalize(`${input.workflow} ${input.risks.join(" ")}`))) raw += 4;
    if (item.failure_patterns.length) raw += Math.min(4, item.failure_patterns.length);

    return { item, raw, reasons: reasons.slice(0, 4) };
  }).sort((a, b) => b.raw - a.raw || b.item.evidence.real_result_artifacts - a.item.evidence.real_result_artifacts || a.item.title.localeCompare(b.item.title))
    .slice(0, 5)
    .map((match, index, matches) => ({
      ...match,
      score: Math.max(32, Math.min(98, Math.round(58 + (match.raw - matches[matches.length - 1].raw) * 1.45 - index * 3))),
    }));
}

function studioMatchCard(match, index) {
  const { item, score, reasons } = match;
  const article = document.createElement("article");
  article.className = `studio-match${index === 0 ? " best" : ""}`;
  article.style.setProperty("--card-accent", cardAccent(item));

  const rank = document.createElement("div");
  rank.className = "studio-match-rank";
  rank.innerHTML = `<span>${index === 0 ? "STRONGEST START" : `MATCH 0${index + 1}`}</span><b>${score}<small>/100 fit</small></b>`;
  const heading = document.createElement("h3");
  heading.textContent = `${item.icon} ${item.title}`;
  const meta = document.createElement("p");
  meta.className = "studio-match-meta";
  meta.textContent = `${item.industry} · ${item.contract.name}`;
  const question = document.createElement("p");
  question.className = "studio-match-question";
  question.textContent = item.question;

  const why = document.createElement("div");
  why.className = "studio-why";
  const whyLabel = document.createElement("b");
  whyLabel.textContent = "Why it matched";
  why.append(whyLabel, ...((reasons.length ? reasons : ["closest verified architecture"]).map((reason) => makeBadge(reason, "studio-reason"))));

  const proofs = document.createElement("div");
  proofs.className = "studio-proofs";
  for (const [, label] of proofBadges(item)) proofs.append(makeBadge(label));

  const actions = document.createElement("div");
  actions.className = "studio-match-actions";
  const open = document.createElement("a");
  open.href = `${REPO}/tree/main/${item.path}`;
  open.className = "button primary";
  open.textContent = "Inspect the lab ↗";
  const use = document.createElement("button");
  use.type = "button";
  use.className = "button secondary";
  use.textContent = "Use as starter";
  use.addEventListener("click", () => selectStudioStarter(match));
  actions.append(open, use, compareButton(item));
  article.append(rank, heading, meta, question, why, proofs, actions);
  return article;
}

function renderStudioResults(matches, shouldScroll = true) {
  state.studioMatches = matches;
  els.studioMatchGrid.replaceChildren(...matches.slice(0, 3).map(studioMatchCard));
  const strongest = matches[0];
  els.studioResultTitle.textContent = `Best verified matches for ${state.studioInput.industry === "all" ? "this workflow" : state.studioInput.industry}`;
  els.studioResultSummary.textContent = `${strongest.item.title} is the strongest starting architecture. Fit scores explain catalog similarity; they do not certify a real deployment.`;
  els.studioResults.hidden = false;
  selectStudioStarter(strongest);
  if (shouldScroll) els.studioResults.scrollIntoView({ behavior: "smooth", block: "start" });
}

function buildIssueUrl(match) {
  const input = state.studioInput;
  const title = `[request] ${input.industry === "all" ? "new industry" : input.industry}: ${input.workflow.slice(0, 72)}`;
  const body = [
    "## Workflow from AAU Studio",
    input.workflow,
    "",
    `**Industry:** ${input.industry === "all" ? "Not selected" : input.industry}`,
    `**Agent shape:** ${input.shape}`,
    `**Consequences:** ${input.risks.join("; ") || "Not selected"}`,
    `**Closest verified lab:** ${match.item.title} (${match.item.path})`,
    `**Closest contract:** ${match.item.contract.name}`,
    "",
    "## Gap to verify",
    "Describe why the closest lab cannot represent the deciding facts, authority boundary, or harmful failure in this workflow.",
  ].join("\n");
  const params = new URLSearchParams({ title, body });
  return `${REPO}/issues/new?${params}`;
}

function selectStudioStarter(match) {
  const { item, score } = match;
  els.studioKit.hidden = false;
  els.studioKitTitle.textContent = `Fork ${item.title}`;
  els.studioKitCopy.textContent = `Reuse its ${item.contract.name} architecture, ${item.evidence.scenario_count} seeded scenarios, and observed failure shape. Replace domain rules before treating it as evidence for your workflow.`;
  els.studioCommand.textContent = `git clone ${REPO}.git\ncd awesome-agentic-usecases\n${item.commands.install}\n${item.commands.evaluate}`;
  els.studioRequest.href = buildIssueUrl(match);
  els.studioKit.dataset.path = item.path;
  els.studioKit.dataset.score = String(score);
  const forgeName = `${slugifyStudio(item.title.replace(/coordinator|navigator|agent|gate/gi, "")) || "my-workflow"}-eval`;
  els.forgeCommand.textContent = `aau forge <downloaded-brief.json> --name ${forgeName}\naau forge doctor <generated-lab>`;
}

function slugifyStudio(text) {
  return normalize(text).replace(/\s+/g, "-").replace(/^-|-$/g, "");
}

function studioSpec() {
  const path = els.studioKit.dataset.path;
  const match = state.studioMatches.find((candidate) => candidate.item.path === path) || state.studioMatches[0];
  return {
    contract_version: "aau-studio/1.0",
    created_at: new Date().toISOString(),
    workflow: {
      description: state.studioInput.workflow,
      industry: state.studioInput.industry === "all" ? "unspecified" : state.studioInput.industry,
      agent_shape: state.studioInput.shape,
      risks: state.studioInput.risks,
    },
    recommended_case: {
      path: match.item.path,
      title: match.item.title,
      cli: match.item.cli,
      contract: match.item.contract.name,
      fit_score: match.score,
    },
    verification_plan: {
      minimum_scenarios: Math.max(20, match.item.evidence.scenario_count),
      minimum_repeats: 3,
      required_proofs: [
        "programmatic ground truth shared by generation and scoring",
        "at least one deceptive or transfer-failure scenario",
        "exact action trace and truthful completion record",
        "protected human authority boundary",
        "observed failures linked to scenario IDs",
        "cost, latency, completion, and task metrics reported together",
      ],
    },
    commands: match.item.commands,
  };
}

function downloadStudioSpec() {
  const spec = studioSpec();
  const slug = spec.recommended_case.path.split("/").pop();
  const blob = new Blob([`${JSON.stringify(spec, null, 2)}\n`], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `aau-evaluation-brief-${slug}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(link.href), 0);
}

function renderCompareTray() {
  const items = state.compare.map((path) => state.cases.find((item) => item.path === path)).filter(Boolean);
  els.compareTray.hidden = !items.length;
  els.compareCount.textContent = `${items.length} selected`;
  els.compareNames.textContent = items.length ? items.map((item) => item.title).join(" · ") : "Choose up to three use cases";
  els.openCompare.disabled = items.length < 2;
}

function compareCell(label, value, link = "") {
  const div = document.createElement(link ? "a" : "div");
  div.className = "compare-cell";
  if (link) div.href = link;
  const small = document.createElement("small");
  small.textContent = label;
  const content = document.createElement("b");
  content.textContent = value;
  div.append(small, content);
  return div;
}

function renderComparison() {
  const items = state.compare.map((path) => state.cases.find((item) => item.path === path)).filter(Boolean);
  if (items.length < 2) return;
  els.compareTable.replaceChildren();
  els.compareTable.style.setProperty("--compare-columns", String(items.length));
  for (const item of items) {
    const column = document.createElement("article");
    column.className = "compare-column";
    column.style.setProperty("--card-accent", cardAccent(item));
    const heading = document.createElement("h3");
    heading.textContent = `${item.icon} ${item.title}`;
    column.append(
      heading,
      compareCell("Industry", item.industry),
      compareCell("Evaluation shape", item.kind),
      compareCell("Reusable contract", item.contract.name, `${REPO}/blob/main/${item.contract.path}`),
      compareCell("Seeded scenarios", String(item.evidence.scenario_count)),
      compareCell("Real result artifacts", String(item.evidence.real_result_artifacts)),
      compareCell("Measured model IDs", String(item.evidence.model_count)),
      compareCell("Observed failures", String(item.evidence.observed_failure_modes)),
      compareCell("Failure patterns", item.failure_patterns.map((pattern) => pattern.name).slice(0, 3).join(" · ") || "Case-specific only"),
      compareCell("Zero-cost entry", item.evidence.mock_available ? "Deterministic mock included" : "Not available"),
      compareCell("Open", "Inspect repository evidence ↗", `${REPO}/tree/main/${item.path}`),
    );
    els.compareTable.append(column);
  }
  els.compareDialog.showModal();
}

async function init() {
  const response = await fetch("studio-data.json?v=1");
  if (!response.ok) throw new Error(`Evidence index failed to load (${response.status})`);
  const data = await response.json();
  state.cases = data.cases;

  const params = new URLSearchParams(location.search);
  state.search = params.get("q") || "";
  state.industry = params.get("industry") || "all";
  els.search.value = state.search;

  const industries = [...new Set(state.cases.map((item) => item.industry))].sort();
  for (const name of industries) {
    for (const select of [els.industry, els.studioIndustry]) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      select.append(option);
    }
  }
  if (industries.includes(state.industry)) els.industry.value = state.industry;
  else state.industry = "all";

  els.search.addEventListener("input", () => {
    state.search = els.search.value;
    syncUrl();
    render();
  });
  els.industry.addEventListener("change", () => {
    state.industry = els.industry.value;
    syncUrl();
    render();
  });
  els.clear.addEventListener("click", () => {
    state.search = "";
    state.industry = "all";
    els.search.value = "";
    els.industry.value = "all";
    syncUrl();
    render();
    els.search.focus();
  });
  for (const goal of els.goals) {
    goal.addEventListener("click", () => {
      state.search = goal.dataset.query;
      state.industry = "all";
      els.search.value = state.search;
      els.industry.value = "all";
      syncUrl();
      render();
    });
  }

  els.studioForm.addEventListener("submit", (event) => {
    event.preventDefault();
    state.studioInput = {
      workflow: els.studioWorkflow.value.trim(),
      industry: els.studioIndustry.value,
      shape: els.studioShape.value,
      risks: selectedRisks(),
    };
    if (!state.studioInput.workflow) return els.studioWorkflow.focus();
    renderStudioResults(rankStudioCases(state.studioInput));
  });
  els.studioExample.addEventListener("click", () => {
    els.studioWorkflow.value = "An agent receives a chemical release report, coordinates emergency response, preserves every regulator notification clock, and must not claim a draft was filed.";
    els.studioIndustry.value = "Pipeline Safety & Emergency Reporting";
    els.studioShape.value = "deadline obligation rights";
    document.querySelectorAll('[name="studio-risk"]').forEach((input) => {
      input.checked = /deadline|receipt/.test(input.value);
    });
    els.studioForm.requestSubmit();
  });
  els.copyStudioCommand.addEventListener("click", () => copyText(els.studioCommand.textContent, els.copyStudioCommand, "Copy zero-cost run"));
  els.downloadStudioSpec.addEventListener("click", downloadStudioSpec);
  els.copyForgeCommand.addEventListener("click", () => copyText(els.forgeCommand.textContent, els.copyForgeCommand, "Copy Forge command"));
  els.clearCompare.addEventListener("click", () => {
    state.compare = [];
    renderCompareTray();
    render();
    if (!els.studioResults.hidden) renderStudioResults(state.studioMatches, false);
  });
  els.openCompare.addEventListener("click", renderComparison);
  render();
  loadReliability().catch((error) => {
    els.reliabilityResultCount.textContent = "Reliability evidence unavailable";
    const empty = document.createElement("div");
    empty.className = "reliability-empty";
    empty.textContent = `${error.message}. Open STATE_OF_AGENT_RELIABILITY_2026.md on GitHub instead.`;
    els.reliabilityChart.replaceChildren(empty);
  });
  loadGallery().catch((error) => {
    els.galleryCount.textContent = "Gallery evidence unavailable";
    const empty = document.createElement("div");
    empty.className = "gallery-empty";
    empty.textContent = `${error.message}. Inspect gallery/README.md on GitHub instead.`;
    els.galleryGrid.replaceChildren(empty);
  });
}

init().catch((error) => {
  els.grid.innerHTML = `<div class="empty">${error.message}. Open the repository catalog on GitHub instead.</div>`;
});
