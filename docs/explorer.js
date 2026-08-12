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
