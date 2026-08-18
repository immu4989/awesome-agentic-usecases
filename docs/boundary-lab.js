(() => {
  "use strict";

  const STORAGE_KEY = "aau-boundary-lab-progress-v1";
  const LIVE_URL = "https://immu4989.github.io/awesome-agentic-usecases/";
  const REPO_URL = "https://github.com/immu4989/awesome-agentic-usecases";
  const ACTIONS = ["trust", "verify", "block"];
  const state = { data: null, pairIndex: 0, sessions: {} };

  const els = {
    section: document.querySelector("#boundary-lab"),
    room: document.querySelector("#boundary-room"),
    begin: document.querySelector("#boundary-begin"),
    copyLink: document.querySelector("#boundary-copy-link"),
    copyStatus: document.querySelector("#boundary-copy-status"),
    reset: document.querySelector("#boundary-reset"),
    nav: document.querySelector("#boundary-nav"),
    reviewed: document.querySelector("#boundary-reviewed"),
    score: document.querySelector("#boundary-score"),
    pairCount: document.querySelector("#boundary-pair-count"),
    industryCount: document.querySelector("#boundary-industry-count"),
    contractCount: document.querySelector("#boundary-contract-count"),
    sourceCount: document.querySelector("#boundary-source-count"),
    number: document.querySelector("#boundary-number"),
    industry: document.querySelector("#boundary-industry"),
    contract: document.querySelector("#boundary-contract"),
    title: document.querySelector("#boundary-pair-title"),
    before: document.querySelector("#boundary-before"),
    label: document.querySelector("#boundary-label"),
    after: document.querySelector("#boundary-after"),
    choiceStatus: document.querySelector("#boundary-choice-status"),
    revealButton: document.querySelector("#boundary-reveal-button"),
    reveal: document.querySelector("#boundary-reveal"),
    revealStatus: document.querySelector("#boundary-reveal-status"),
    revealTitle: document.querySelector("#boundary-reveal-title"),
    baselineAction: document.querySelector("#boundary-baseline-action"),
    changedAction: document.querySelector("#boundary-changed-action"),
    why: document.querySelector("#boundary-why"),
    stake: document.querySelector("#boundary-stake"),
    sources: document.querySelector("#boundary-sources"),
    next: document.querySelector("#boundary-next"),
    downloadJson: document.querySelector("#boundary-download-json"),
    downloadPytest: document.querySelector("#boundary-download-pytest"),
    downloadCard: document.querySelector("#boundary-download-card"),
    shareX: document.querySelector("#boundary-share-x"),
    labLink: document.querySelector("#boundary-lab-link"),
    codespaceLink: document.querySelector("#boundary-codespace-link"),
    challengeLink: document.querySelector("#boundary-challenge-link"),
    actionStatus: document.querySelector("#boundary-action-status"),
    finish: document.querySelector("#boundary-finish"),
    exactPairs: document.querySelector("#boundary-exact-pairs"),
    finishNote: document.querySelector("#boundary-finish-note"),
    copyResult: document.querySelector("#boundary-copy-result"),
    canvas: document.querySelector("#boundary-card-canvas"),
  };

  if (!els.section) return;

  function currentPair() {
    return state.data.pairs[state.pairIndex];
  }

  function sessionFor(pair) {
    if (!state.sessions[pair.id]) state.sessions[pair.id] = { left: null, right: null, revealed: false };
    return state.sessions[pair.id];
  }

  function sidesFor(pair) {
    const baseline = {
      kind: "baseline",
      data: pair.baseline,
      expected: pair.expected_reviews.baseline,
      boundaryValue: pair.boundary.before,
    };
    const changed = {
      kind: "changed",
      data: pair.changed,
      expected: pair.expected_reviews.changed,
      boundaryValue: pair.boundary.after,
    };
    return pair.presentation === "changed-first" ? [changed, baseline] : [baseline, changed];
  }

  function humanize(value) {
    return String(value ?? "").replaceAll("_", " ");
  }

  function actionLabel(action) {
    return state.data.review_actions[action]?.label || humanize(action);
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
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.sessions));
    } catch {
      // Local persistence is optional; every lab action still works without it.
    }
  }

  function sanitizedSessions() {
    const stored = loadProgress();
    const valid = {};
    for (const pair of state.data.pairs) {
      const item = stored[pair.id];
      if (!item || typeof item !== "object") continue;
      valid[pair.id] = {
        left: ACTIONS.includes(item.left) ? item.left : null,
        right: ACTIONS.includes(item.right) ? item.right : null,
        revealed: Boolean(item.revealed && ACTIONS.includes(item.left) && ACTIONS.includes(item.right)),
      };
    }
    return valid;
  }

  function syncUrl(pair, mode = "replace") {
    const params = new URLSearchParams(location.search);
    params.delete("case");
    params.set("boundary", pair.id);
    const query = params.toString();
    const url = `${location.pathname}${query ? `?${query}` : ""}#boundary-lab`;
    history[mode === "push" ? "pushState" : "replaceState"](null, "", url);
  }

  function shareUrl(pair) {
    return pair.links.share || `${LIVE_URL}?boundary=${encodeURIComponent(pair.id)}#boundary-lab`;
  }

  function summary() {
    let reviewed = 0;
    let exactDecisions = 0;
    let exactPairs = 0;
    for (const pair of state.data.pairs) {
      const session = state.sessions[pair.id];
      if (!session?.revealed) continue;
      reviewed += 1;
      const [left, right] = sidesFor(pair);
      const leftCorrect = session.left === left.expected;
      const rightCorrect = session.right === right.expected;
      exactDecisions += Number(leftCorrect) + Number(rightCorrect);
      exactPairs += Number(leftCorrect && rightCorrect);
    }
    return { reviewed, exactDecisions, exactPairs };
  }

  function setStatus(message) {
    els.actionStatus.textContent = message;
  }

  async function copyText(value, confirmation, target = els.actionStatus) {
    try {
      await navigator.clipboard.writeText(value);
      target.textContent = confirmation;
    } catch {
      const area = document.createElement("textarea");
      area.value = value;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.append(area);
      area.select();
      document.execCommand("copy");
      area.remove();
      target.textContent = confirmation;
    }
  }

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function renderFacts(target, facts) {
    target.replaceChildren(...facts.map((fact) => {
      const row = make("div", "boundary-fact");
      row.append(make("span", "", fact.label), make("b", "", fact.value));
      return row;
    }));
  }

  function renderGates(target, gates) {
    target.replaceChildren(...gates.map((gate) => {
      const row = make("div", `boundary-gate is-${gate.state}`);
      row.append(make("i", "", gate.state === "satisfied" ? "✓" : gate.state === "failed" ? "×" : "?"));
      const copy = make("span");
      copy.append(make("b", "", gate.label), make("small", "", humanize(gate.state)));
      row.append(copy);
      return row;
    }));
  }

  function renderEvidence(target, evidence) {
    const head = make("span", "", "EVIDENCE LEDGER");
    const list = make("div", "boundary-evidence-list");
    const held = evidence.held.map((value) => ({ value, state: "held" }));
    const missing = evidence.missing.map((value) => ({ value, state: "missing" }));
    for (const item of [...held, ...missing]) {
      const chip = make("small", `is-${item.state}`, `${item.state === "held" ? "✓" : "!"} ${humanize(item.value)}`);
      list.append(chip);
    }
    if (!list.children.length) list.append(make("small", "is-empty", "No evidence ledger entries"));
    target.replaceChildren(head, list);
  }

  function renderChoiceGroup(sideName, side, session) {
    const fieldset = document.querySelector(`#boundary-${sideName}-choices`);
    for (const button of fieldset.querySelectorAll("button[data-boundary-choice]")) {
      const action = button.dataset.boundaryChoice;
      const selected = session[sideName] === action;
      button.setAttribute("aria-pressed", String(selected));
      button.classList.toggle("is-selected", selected);
      button.classList.toggle("is-correct", session.revealed && action === side.expected);
      button.classList.toggle("is-wrong", session.revealed && selected && action !== side.expected);
      button.disabled = session.revealed;
    }
  }

  function renderOracle(sideName, side, session) {
    const oracle = document.querySelector(`#boundary-${sideName}-oracle`);
    oracle.hidden = !session.revealed;
    oracle.className = `boundary-oracle${session.revealed ? ` is-${side.expected}` : ""}`;
    oracle.querySelector("b").textContent = `${actionLabel(side.expected)} · ${humanize(side.data.oracle.terminal)}`;
    oracle.querySelector("code").textContent = side.data.oracle.reason_code;
  }

  function renderSide(sideName, side, session) {
    const prefix = `#boundary-${sideName}`;
    const container = document.querySelector(`${prefix === "#boundary-left" ? "#boundary-side-left" : "#boundary-side-right"}`);
    container.dataset.kind = side.kind;
    document.querySelector(`${prefix}-archetype`).textContent = side.data.archetype;
    document.querySelector(`${prefix}-title`).textContent = side.boundaryValue;
    document.querySelector(`${prefix}-case`).textContent = side.data.case_text;
    renderFacts(document.querySelector(`${prefix}-facts`), side.data.facts);
    renderGates(document.querySelector(`${prefix}-gates`), side.data.gates);
    renderEvidence(document.querySelector(`${prefix}-evidence`), side.data.evidence);
    renderChoiceGroup(sideName, side, session);
    renderOracle(sideName, side, session);
  }

  function renderSources(pair) {
    els.sources.replaceChildren(make("span", "", "PRIMARY SOURCES"), ...pair.sources.map((source) => {
      const link = make("a", "", `${source.label} ↗`);
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      return link;
    }));
  }

  function updateLinks(pair) {
    els.labLink.href = pair.links.lab;
    els.codespaceLink.href = pair.links.codespace;
    const title = `Boundary challenge: ${pair.title}`;
    const body = [
      "## Boundary under review",
      "",
      `- Boundary ID: \`${pair.id}\``,
      `- Declared semantic change: **${pair.boundary.before} → ${pair.boundary.after}**`,
      `- Source scenarios: [inspect the committed pair](${pair.links.scenario})`,
      "",
      "## Counterevidence",
      "",
      "<!-- Link primary evidence that changes the declared ground truth. -->",
      "",
      "## Proposed regression assertion",
      "",
      "<!-- State the expected Trust / Verify / Block action on each side. -->",
      "",
      "## Reproduction notes",
      "",
      "<!-- Use synthetic or public data only. Do not include protected or confidential records. -->",
    ].join("\n");
    els.challengeLink.href = `${REPO_URL}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}&labels=evidence-challenge`;
  }

  function renderReveal(pair, session, sides) {
    els.reveal.hidden = !session.revealed;
    if (!session.revealed) return;
    const correct = Number(session.left === sides[0].expected) + Number(session.right === sides[1].expected);
    els.revealStatus.textContent = correct === 2 ? "EXACT BOUNDARY CALL" : correct === 1 ? "ONE SIDE NEEDS REVIEW" : "BOUNDARY MISSED";
    els.revealTitle.textContent = correct === 2 ? "You moved with the contract." : "The deciding fact changed more than it first appeared.";
    els.baselineAction.textContent = actionLabel(pair.expected_reviews.baseline);
    els.changedAction.textContent = actionLabel(pair.expected_reviews.changed);
    els.why.textContent = pair.why;
    els.stake.textContent = pair.stake;
    renderSources(pair);
    drawCard(pair, correct);
  }

  function updateSummary() {
    const totals = summary();
    els.reviewed.textContent = totals.reviewed;
    els.score.textContent = totals.exactDecisions;
    els.exactPairs.textContent = totals.exactPairs;
    const complete = totals.reviewed === state.data.stats.pairs;
    els.finish.hidden = !complete;
    if (complete) {
      els.finishNote.textContent = totals.exactPairs === state.data.stats.pairs
        ? "Every pair matched the committed contract. Now challenge one with stronger evidence or fork it into a new domain."
        : "Revisit the split rooms that moved unexpectedly, then turn one disagreement into an evidence challenge.";
    }
  }

  function renderNav() {
    els.nav.replaceChildren(...state.data.pairs.map((pair, index) => {
      const session = state.sessions[pair.id];
      const button = make("button", "boundary-nav-item");
      button.type = "button";
      button.dataset.index = String(index);
      button.classList.toggle("is-active", index === state.pairIndex);
      button.classList.toggle("is-revealed", Boolean(session?.revealed));
      button.setAttribute("aria-current", index === state.pairIndex ? "true" : "false");
      button.setAttribute("aria-label", `Boundary ${index + 1}: ${pair.industry}${session?.revealed ? ", revealed" : ""}`);
      button.append(make("b", "", String(index + 1).padStart(2, "0")), make("span", "", pair.industry));
      return button;
    }));
  }

  function render(push = false) {
    const pair = currentPair();
    const session = sessionFor(pair);
    const sides = sidesFor(pair);
    els.number.textContent = `BOUNDARY ${String(pair.order).padStart(2, "0")} / ${String(state.data.stats.pairs).padStart(2, "0")}`;
    els.industry.textContent = pair.industry;
    els.contract.textContent = pair.contract;
    els.title.textContent = pair.title;
    els.before.textContent = pair.boundary.before;
    els.label.textContent = pair.boundary.label;
    els.after.textContent = pair.boundary.after;
    renderSide("left", sides[0], session);
    renderSide("right", sides[1], session);
    const ready = Boolean(session.left && session.right);
    els.revealButton.disabled = !ready || session.revealed;
    els.revealButton.textContent = session.revealed ? "Boundary revealed ✓" : "Reveal the boundary →";
    els.choiceStatus.textContent = session.revealed
      ? "The source-locked oracle is visible. Download the pair or move to the next boundary."
      : ready ? "Both actions are locked in. Reveal the source-derived oracle when ready."
        : `Choose one action for each scenario. ${session.left || session.right ? "One side remains." : "The sides alternate; position is not a clue."}`;
    renderReveal(pair, session, sides);
    updateLinks(pair);
    renderNav();
    updateSummary();
    setStatus("");
    if (push || location.hash === "#boundary-lab") {
      syncUrl(pair, push ? "push" : "replace");
    }
  }

  function choose(sideName, action) {
    const pair = currentPair();
    const session = sessionFor(pair);
    if (session.revealed || !ACTIONS.includes(action)) return;
    session[sideName] = action;
    persistProgress();
    render();
  }

  function revealCurrent() {
    const pair = currentPair();
    const session = sessionFor(pair);
    if (!session.left || !session.right) return;
    session.revealed = true;
    persistProgress();
    render();
    els.reveal.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function selectPair(index, push = true) {
    if (!Number.isInteger(index) || index < 0 || index >= state.data.pairs.length) return;
    state.pairIndex = index;
    render(push);
    els.title.focus({ preventScroll: true });
  }

  function nextUnrevealed() {
    const total = state.data.pairs.length;
    for (let step = 1; step <= total; step += 1) {
      const index = (state.pairIndex + step) % total;
      if (!state.sessions[state.data.pairs[index].id]?.revealed) {
        selectPair(index);
        els.room.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
    }
    els.finish.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function download(name, type, contents) {
    const blob = contents instanceof Blob ? contents : new Blob([contents], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 500);
  }

  function regressionPackage(pair) {
    return {
      schema_version: "aau-boundary-regression/1.0",
      boundary_id: pair.id,
      contract: pair.contract,
      declared_semantic_delta: pair.boundary,
      expected_reviews: pair.expected_reviews,
      scenarios: { baseline: pair.baseline, changed: pair.changed },
      provenance: pair.provenance,
      sources: pair.sources,
      safety_note: "Synthetic evaluation fixture. Validate policy and human authority before operational use.",
    };
  }

  function pytestFixture(pair) {
    return `"""Regression test exported by AAU Boundary Lab: ${pair.id}."""\n\nimport json\nfrom pathlib import Path\n\n\ndef test_deciding_fact_changes_required_action():\n    fixture = json.loads(Path(__file__).with_name("${pair.id}.json").read_text())\n    baseline = fixture["scenarios"]["baseline"]\n    changed = fixture["scenarios"]["changed"]\n    reviews = fixture["expected_reviews"]\n\n    assert reviews["baseline"] != reviews["changed"]\n    assert baseline["oracle"]["terminal"] != changed["oracle"]["terminal"]\n    assert baseline["scenario_id"] != changed["scenario_id"]\n`;
  }

  function fitText(ctx, text, x, y, width, lineHeight, maxLines = 3) {
    const words = String(text).split(/\s+/);
    const lines = [];
    let line = "";
    for (const word of words) {
      const candidate = line ? `${line} ${word}` : word;
      if (!line || ctx.measureText(candidate).width <= width) line = candidate;
      else { lines.push(line); line = word; }
    }
    if (line) lines.push(line);
    const visible = lines.slice(0, maxLines);
    if (lines.length > maxLines) visible[maxLines - 1] = `${visible[maxLines - 1].replace(/[.,;:]?$/, "")}…`;
    visible.forEach((value, index) => ctx.fillText(value, x, y + index * lineHeight));
  }

  function drawCard(pair, correct) {
    const ctx = els.canvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#090c0f";
    ctx.fillRect(0, 0, 1200, 630);
    ctx.strokeStyle = "rgba(217,255,98,.08)";
    for (let x = 0; x <= 1200; x += 42) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, 630); ctx.stroke(); }
    for (let y = 0; y <= 630; y += 42) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(1200, y); ctx.stroke(); }
    ctx.fillStyle = "#d9ff62";
    ctx.fillRect(0, 0, 18, 630);
    ctx.fillStyle = "#ff5ccf";
    ctx.fillRect(18, 0, 8, 630);
    ctx.font = "800 18px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.fillStyle = "#d9ff62";
    ctx.fillText("AAU / BOUNDARY LAB / SOURCE-LOCKED", 68, 66);
    ctx.fillStyle = "#f7f4e8";
    ctx.font = "850 60px system-ui, -apple-system, sans-serif";
    fitText(ctx, pair.title, 68, 145, 970, 66, 2);
    ctx.fillStyle = "#9fa9a1";
    ctx.font = "700 16px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.fillText(`${pair.industry.toUpperCase()} / ${pair.contract.toUpperCase()}`, 70, 286);
    ctx.strokeStyle = "#364038";
    ctx.strokeRect(68, 322, 480, 154);
    ctx.strokeRect(652, 322, 480, 154);
    ctx.fillStyle = "#9fa9a1";
    ctx.font = "800 13px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.fillText("BEFORE", 94, 356);
    ctx.fillText("AFTER", 678, 356);
    ctx.fillStyle = "#f7f4e8";
    ctx.font = "750 27px system-ui, -apple-system, sans-serif";
    fitText(ctx, pair.boundary.before, 94, 400, 420, 34, 2);
    fitText(ctx, pair.boundary.after, 678, 400, 420, 34, 2);
    ctx.fillStyle = "#ff5ccf";
    ctx.font = "900 52px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.fillText("Δ", 578, 412);
    ctx.fillStyle = "#d9ff62";
    ctx.font = "900 23px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.fillText(`${actionLabel(pair.expected_reviews.baseline).toUpperCase()}  →  ${actionLabel(pair.expected_reviews.changed).toUpperCase()}`, 70, 536);
    ctx.fillStyle = "#9fa9a1";
    ctx.font = "700 15px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.fillText(`${correct}/2 EXACT · ${pair.id}`, 70, 576);
    ctx.fillStyle = "#f7f4e8";
    ctx.textAlign = "right";
    ctx.fillText("immu4989.github.io/awesome-agentic-usecases", 1130, 576);
    ctx.textAlign = "left";
  }

  function resultText() {
    const totals = summary();
    return `I mapped ${totals.exactPairs}/${state.data.stats.pairs} source-locked AI-agent boundaries exactly in AAU Boundary Lab (${totals.exactDecisions}/${state.data.stats.pairs * 2} decisions). Change one fact. Does your agent change its action? ${shareUrl(currentPair())}`;
  }

  function bindEvents() {
    els.begin.addEventListener("click", () => els.room.scrollIntoView({ behavior: "smooth", block: "start" }));
    els.copyLink.addEventListener("click", () => copyText(shareUrl(currentPair()), "Boundary link copied.", els.copyStatus));
    els.reset.addEventListener("click", () => {
      state.sessions = {};
      try { localStorage.removeItem(STORAGE_KEY); } catch { /* Optional storage. */ }
      render();
      setStatus("Local Boundary Lab progress reset.");
    });
    els.nav.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-index]");
      if (button) selectPair(Number(button.dataset.index));
    });
    for (const sideName of ["left", "right"]) {
      document.querySelector(`#boundary-${sideName}-choices`).addEventListener("click", (event) => {
        const button = event.target.closest("button[data-boundary-choice]");
        if (button) choose(sideName, button.dataset.boundaryChoice);
      });
    }
    els.revealButton.addEventListener("click", revealCurrent);
    els.next.addEventListener("click", nextUnrevealed);
    els.downloadJson.addEventListener("click", () => {
      const pair = currentPair();
      download(`${pair.id}.json`, "application/json", `${JSON.stringify(regressionPackage(pair), null, 2)}\n`);
      setStatus("Regression JSON generated locally.");
    });
    els.downloadPytest.addEventListener("click", () => {
      const pair = currentPair();
      download(`test_${pair.id.replaceAll("-", "_")}.py`, "text/x-python", pytestFixture(pair));
      setStatus("Pytest assertion generated locally. Keep it beside the downloaded JSON fixture.");
    });
    els.downloadCard.addEventListener("click", () => {
      const pair = currentPair();
      const session = sessionFor(pair);
      const sides = sidesFor(pair);
      const correct = Number(session.left === sides[0].expected) + Number(session.right === sides[1].expected);
      drawCard(pair, correct);
      els.canvas.toBlob((blob) => {
        if (blob) download(`${pair.id}-boundary-card.png`, "image/png", blob);
      }, "image/png");
      setStatus("Visual boundary card generated locally.");
    });
    els.shareX.addEventListener("click", () => {
      const pair = currentPair();
      const text = `One deciding fact moved an AI agent from ${actionLabel(pair.expected_reviews.baseline)} to ${actionLabel(pair.expected_reviews.changed)}. Can your system find the boundary?`;
      window.open(`https://x.com/intent/post?text=${encodeURIComponent(text)}&url=${encodeURIComponent(shareUrl(pair))}`, "_blank", "noopener,noreferrer");
    });
    els.copyResult.addEventListener("click", () => copyText(resultText(), "Result and challenge link copied."));
    window.addEventListener("popstate", () => {
      const id = new URLSearchParams(location.search).get("boundary");
      const index = state.data.pairs.findIndex((pair) => pair.id === id);
      if (index >= 0) { state.pairIndex = index; render(false); }
    });
  }

  async function init() {
    try {
      const response = await fetch("boundary-data.json?v=1");
      if (!response.ok) throw new Error(`Boundary data returned ${response.status}`);
      state.data = await response.json();
      state.sessions = sanitizedSessions();
      const requested = new URLSearchParams(location.search).get("boundary");
      const index = state.data.pairs.findIndex((pair) => pair.id === requested);
      state.pairIndex = index >= 0 ? index : 0;
      els.pairCount.textContent = state.data.stats.pairs;
      els.industryCount.textContent = state.data.stats.industries;
      els.contractCount.textContent = state.data.stats.contracts;
      els.sourceCount.textContent = state.data.stats.source_scenarios;
      els.reviewed.parentElement.lastChild.textContent = `/${state.data.stats.pairs} revealed`;
      els.score.parentElement.lastChild.textContent = `/${state.data.stats.pairs * 2} exact calls`;
      bindEvents();
      render();
    } catch (error) {
      els.title.textContent = "Boundary evidence could not be loaded.";
      els.choiceStatus.textContent = `${error.message}. Refresh the page or inspect the source contract on GitHub.`;
      els.revealButton.disabled = true;
    }
  }

  init();
})();
