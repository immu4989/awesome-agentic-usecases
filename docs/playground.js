(() => {
  "use strict";

  const STORAGE_KEY = "aau-playground-progress-v1";
  const state = {
    data: null,
    caseIndex: 0,
    answers: {},
  };

  const els = {
    section: document.querySelector("#playground"),
    room: document.querySelector("#playground-room"),
    begin: document.querySelector("#playground-begin"),
    share: document.querySelector("#playground-share"),
    reset: document.querySelector("#playground-reset"),
    next: document.querySelector("#playground-next"),
    nav: document.querySelector("#playground-case-nav"),
    verdicts: document.querySelector("#playground-verdicts"),
    reveal: document.querySelector("#playground-reveal"),
    reviewed: document.querySelector("#playground-reviewed"),
    score: document.querySelector("#playground-score"),
    caseCount: document.querySelector("#playground-case-count"),
    industryCount: document.querySelector("#playground-industry-count"),
    modelCount: document.querySelector("#playground-model-count"),
    sourceCount: document.querySelector("#playground-source-count"),
    number: document.querySelector("#playground-case-number"),
    industry: document.querySelector("#playground-case-industry"),
    shape: document.querySelector("#playground-case-shape"),
    title: document.querySelector("#playground-case-title"),
    caseText: document.querySelector("#playground-case-text"),
    facts: document.querySelector("#playground-facts"),
    untrusted: document.querySelector("#playground-untrusted"),
    evidence: document.querySelector("#playground-evidence"),
    gates: document.querySelector("#playground-gates"),
    action: document.querySelector("#playground-agent-action"),
    reason: document.querySelector("#playground-agent-reason"),
    reasoning: document.querySelector("#playground-agent-reasoning"),
    confirmed: document.querySelector("#playground-confirmed-gates"),
    model: document.querySelector("#playground-agent-model"),
    backend: document.querySelector("#playground-agent-backend"),
    run: document.querySelector("#playground-agent-run"),
    cost: document.querySelector("#playground-agent-cost"),
    latency: document.querySelector("#playground-agent-latency"),
    choiceStatus: document.querySelector("#playground-choice-status"),
    revealStatus: document.querySelector("#playground-reveal-status"),
    revealTitle: document.querySelector("#playground-reveal-title"),
    groundReason: document.querySelector("#playground-ground-reason"),
    lesson: document.querySelector("#playground-lesson"),
    failedMetrics: document.querySelector("#playground-failed-metrics"),
    resultLink: document.querySelector("#playground-result-link"),
    labLink: document.querySelector("#playground-lab-link"),
    challengeLink: document.querySelector("#playground-challenge-link"),
    stake: document.querySelector("#playground-stake"),
  };

  if (!els.section) return;

  function currentCase() {
    return state.data.cases[state.caseIndex];
  }

  function humanize(value) {
    return String(value || "").replaceAll("_", " ");
  }

  function loadProgress() {
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      return stored && typeof stored === "object" ? stored : {};
    } catch {
      return {};
    }
  }

  function persistProgress() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.answers));
    } catch {
      // Local persistence is an enhancement; the playground remains fully usable without it.
    }
  }

  function syncCaseUrl(item, mode = "replace") {
    const params = new URLSearchParams(location.search);
    params.set("case", item.id);
    const url = `${location.pathname}?${params}#playground`;
    history[mode === "push" ? "pushState" : "replaceState"](null, "", url);
  }

  function updateSession() {
    const answers = Object.entries(state.answers).filter(([id]) => state.data.cases.some((item) => item.id === id));
    els.reviewed.textContent = String(answers.length);
    els.score.textContent = String(answers.filter(([, answer]) => answer.correct).length);
  }

  function factElement(fact) {
    const item = document.createElement("div");
    item.className = "playground-fact";
    const label = document.createElement("small");
    label.textContent = fact.label;
    const value = document.createElement("b");
    value.textContent = fact.value;
    item.append(label, value);
    return item;
  }

  function evidenceColumn(label, values, className = "") {
    const column = document.createElement("div");
    column.className = `playground-evidence-column ${className}`.trim();
    const heading = document.createElement("span");
    heading.textContent = `${label} / ${values.length}`;
    column.append(heading);
    if (!values.length) {
      const empty = document.createElement("p");
      empty.className = "playground-evidence-empty";
      empty.textContent = label === "Missing" ? "Nothing absent" : "None recorded";
      column.append(empty);
      return column;
    }
    const list = document.createElement("ul");
    for (const value of values) {
      const item = document.createElement("li");
      item.textContent = humanize(value);
      list.append(item);
    }
    column.append(list);
    return column;
  }

  function renderNav() {
    els.nav.replaceChildren(...state.data.cases.map((item, index) => {
      const button = document.createElement("button");
      button.className = `playground-case-tab${state.answers[item.id] ? " completed" : ""}`;
      button.type = "button";
      button.setAttribute("aria-selected", String(index === state.caseIndex));
      button.setAttribute("aria-label", `Open case ${index + 1}: ${item.title}`);
      const number = document.createElement("span");
      number.textContent = String(index + 1).padStart(2, "0");
      const title = document.createElement("b");
      title.textContent = item.title;
      const industry = document.createElement("small");
      industry.textContent = item.industry;
      button.append(number, title, industry);
      button.addEventListener("click", () => selectCase(index, true));
      return button;
    }));
  }

  function renderReveal(item, answer) {
    const correct = answer.choice === item.verdict;
    els.reveal.hidden = false;
    els.reveal.className = `playground-reveal ${correct ? "correct" : "incorrect"}`;
    els.revealStatus.textContent = correct ? "EXACT REVIEW" : `GROUND TRUTH · ${state.data.verdicts[item.verdict].label.toLocaleUpperCase()}`;
    els.revealTitle.textContent = item.ground_truth.action;
    els.groundReason.textContent = item.ground_truth.reason_code;
    els.lesson.textContent = item.lesson;
    els.failedMetrics.replaceChildren();
    if (item.ground_truth.failed_metrics.length) {
      for (const metric of item.ground_truth.failed_metrics) {
        const label = document.createElement("span");
        label.textContent = `${humanize(metric)} failed`;
        els.failedMetrics.append(label);
      }
    } else {
      const label = document.createElement("span");
      label.className = "exact-receipt";
      label.textContent = "full contract exact";
      els.failedMetrics.append(label);
    }
    els.choiceStatus.textContent = correct
      ? "Your review matches the committed contract."
      : `You chose ${state.data.verdicts[answer.choice].label}. The committed reviewer action is ${state.data.verdicts[item.verdict].label}.`;
    els.next.disabled = false;
    els.next.textContent = state.caseIndex === state.data.cases.length - 1 ? "Review first case ↻" : "Next case →";
  }

  function renderCase() {
    const item = currentCase();
    const answer = state.answers[item.id];
    els.number.textContent = `CASE ${String(item.order).padStart(2, "0")} / ${String(state.data.cases.length).padStart(2, "0")}`;
    els.industry.textContent = item.industry;
    els.shape.textContent = item.failure_shape;
    els.title.textContent = item.title;
    els.caseText.textContent = item.scenario.case_text;
    els.facts.replaceChildren(...item.scenario.facts.map(factElement));
    els.untrusted.hidden = !item.scenario.untrusted_input;
    els.untrusted.textContent = item.scenario.untrusted_input ? `UNTRUSTED TOOL METADATA — ${item.scenario.untrusted_input}` : "";
    els.evidence.replaceChildren(
      evidenceColumn("Required", item.scenario.evidence.required),
      evidenceColumn("Held", item.scenario.evidence.held),
      evidenceColumn("Missing", item.scenario.evidence.missing, "missing"),
    );
    els.gates.replaceChildren(...item.scenario.gates.map((gate) => {
      const label = document.createElement("span");
      label.className = `playground-gate ${gate.state === "satisfied" ? "" : "failed"}`.trim();
      label.textContent = `${gate.name} · ${gate.state}`;
      return label;
    }));
    els.action.textContent = item.agent.action;
    els.reason.textContent = item.agent.reason_code;
    els.reasoning.textContent = item.agent.reasoning;
    els.confirmed.replaceChildren(...item.agent.confirmed_gates.map((gate) => {
      const label = document.createElement("span");
      label.textContent = `confirmed · ${gate}`;
      return label;
    }));
    els.model.textContent = item.agent.model;
    els.model.title = item.agent.model;
    els.backend.textContent = item.agent.backend;
    els.run.textContent = `repeat ${item.agent.repeat}`;
    els.cost.textContent = `$${Number(item.agent.cost_usd).toFixed(6)}`;
    els.latency.textContent = `${Number(item.agent.latency_s).toFixed(2)}s`;
    els.stake.textContent = item.stake;
    els.resultLink.href = item.links.result;
    els.labLink.href = item.links.lab;
    els.challengeLink.href = item.links.challenge;
    els.share.dataset.url = item.links.share;

    const buttons = [...els.verdicts.querySelectorAll("button[data-playground-verdict]")];
    for (const button of buttons) {
      button.disabled = Boolean(answer);
      button.setAttribute("aria-pressed", String(answer?.choice === button.dataset.playgroundVerdict));
    }
    els.next.disabled = !answer;
    els.reveal.hidden = !answer;
    els.reveal.className = "playground-reveal";
    els.choiceStatus.textContent = "Choose one reviewer action to unlock the contract.";
    if (answer) renderReveal(item, answer);
    renderNav();
    updateSession();
  }

  function selectCase(index, updateHistory = false) {
    state.caseIndex = Math.max(0, Math.min(index, state.data.cases.length - 1));
    const item = currentCase();
    syncCaseUrl(item, updateHistory ? "push" : "replace");
    renderCase();
  }

  function chooseVerdict(choice) {
    const item = currentCase();
    if (state.answers[item.id]) return;
    state.answers[item.id] = {
      choice,
      correct: choice === item.verdict,
    };
    persistProgress();
    renderCase();
    els.reveal.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function copyCaseLink() {
    const url = els.share.dataset.url || location.href;
    try {
      await navigator.clipboard.writeText(url);
      els.share.textContent = "Case link copied";
    } catch {
      els.share.textContent = url;
    }
    setTimeout(() => { els.share.textContent = "Copy this case link"; }, 1800);
  }

  function resetSession() {
    state.answers = {};
    persistProgress();
    renderCase();
  }

  function caseFromUrl() {
    const params = new URLSearchParams(location.search);
    const requested = params.get("case");
    const index = state.data.cases.findIndex((item) => item.id === requested);
    return index >= 0 ? index : 0;
  }

  async function init() {
    const response = await fetch("playground-data.json?v=1");
    if (!response.ok) throw new Error(`Playground evidence failed to load (${response.status})`);
    state.data = await response.json();
    state.answers = loadProgress();
    state.caseIndex = caseFromUrl();
    els.caseCount.textContent = String(state.data.stats.cases);
    els.industryCount.textContent = String(state.data.stats.industries);
    els.modelCount.textContent = String(state.data.stats.models);
    els.sourceCount.textContent = String(state.data.stats.source_artifacts);

    els.begin.addEventListener("click", () => els.room.scrollIntoView({ behavior: "smooth", block: "start" }));
    els.share.addEventListener("click", copyCaseLink);
    els.reset.addEventListener("click", resetSession);
    els.next.addEventListener("click", () => selectCase((state.caseIndex + 1) % state.data.cases.length, true));
    els.verdicts.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-playground-verdict]");
      if (button) chooseVerdict(button.dataset.playgroundVerdict);
    });
    window.addEventListener("popstate", () => {
      state.caseIndex = caseFromUrl();
      renderCase();
    });
    renderCase();
  }

  init().catch((error) => {
    els.room.innerHTML = `<div class="playground-error">${error.message}. Open the playground evidence on GitHub instead.</div>`;
  });
})();
