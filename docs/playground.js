(() => {
  "use strict";

  const STORAGE_KEY = "aau-playground-progress-v1";
  const LIVE_URL = "https://immu4989.github.io/awesome-agentic-usecases/";
  const REPO_URL = "https://github.com/immu4989/awesome-agentic-usecases";
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
    disputeLink: document.querySelector("#playground-dispute-link"),
    stake: document.querySelector("#playground-stake"),
    invitation: document.querySelector("#playground-invitation"),
    invitationScore: document.querySelector("#playground-invitation-score"),
    dismissInvitation: document.querySelector("#playground-dismiss-invitation"),
    receipt: document.querySelector("#playground-receipt"),
    profile: document.querySelector("#playground-profile"),
    profileNote: document.querySelector("#playground-profile-note"),
    finalScore: document.querySelector("#playground-final-score"),
    caught: document.querySelector("#playground-caught"),
    missed: document.querySelector("#playground-missed"),
    canvas: document.querySelector("#playground-card"),
    downloadCard: document.querySelector("#playground-download-card"),
    shareX: document.querySelector("#playground-share-x"),
    shareLinkedIn: document.querySelector("#playground-share-linkedin"),
    copyResult: document.querySelector("#playground-copy-result"),
    resultStatus: document.querySelector("#playground-result-status"),
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

  function sessionAnswers() {
    return state.data.cases
      .map((item) => ({ item, answer: state.answers[item.id] }))
      .filter(({ answer }) => Boolean(answer));
  }

  function reviewProfile(score) {
    if (score === 5) return {
      name: "Evidence Sentinel",
      note: "You matched all five committed reviewer actions across safety gates, missing evidence, transfer traps, expiring rights, and poisoned tools.",
    };
    if (score === 4) return {
      name: "Boundary Scout",
      note: "You caught most contract boundaries. Revisit the one failure shape where the committed reviewer action differed.",
    };
    if (score === 3) return {
      name: "Contract Reader",
      note: "You found several evidence boundaries. The missed traces show where plausible completion can mask a failed contract.",
    };
    return {
      name: "Fast-Path Reviewer",
      note: "This session favored plausible outputs over some committed evidence gates. Use the revisit list as a focused second pass.",
    };
  }

  function resultShareUrl(score) {
    return `${LIVE_URL}?challenge=${score}#playground`;
  }

  function resultShareText(score, profile) {
    return `I reviewed 5 real AI-agent traces and matched ${score}/5 committed evidence contracts — ${profile}. Can you beat my review?`;
  }

  function listFindings(target, values, emptyText) {
    const items = values.length ? values : [emptyText];
    target.replaceChildren(...items.map((value) => {
      const item = document.createElement("li");
      item.textContent = value;
      return item;
    }));
  }

  function fitCanvasText(ctx, text, x, y, maxWidth, lineHeight, maxLines = 3) {
    const words = String(text).split(/\s+/);
    const lines = [];
    let line = "";
    for (const word of words) {
      const test = line ? `${line} ${word}` : word;
      if (ctx.measureText(test).width <= maxWidth || !line) {
        line = test;
      } else {
        lines.push(line);
        line = word;
      }
    }
    if (line) lines.push(line);
    const visible = lines.slice(0, maxLines);
    if (lines.length > maxLines) {
      while (ctx.measureText(`${visible[maxLines - 1]}…`).width > maxWidth) {
        visible[maxLines - 1] = visible[maxLines - 1].slice(0, -1);
      }
      visible[maxLines - 1] += "…";
    }
    visible.forEach((value, index) => ctx.fillText(value, x, y + index * lineHeight));
  }

  function drawResultCard(score, profile, answers) {
    const canvas = els.canvas;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const width = canvas.width;
    const height = canvas.height;
    const gradient = ctx.createLinearGradient(0, 0, width, height);
    gradient.addColorStop(0, "#061216");
    gradient.addColorStop(0.58, "#0a1b20");
    gradient.addColorStop(1, "#071114");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);

    ctx.strokeStyle = "rgba(101,231,255,0.09)";
    ctx.lineWidth = 1;
    for (let x = 0; x <= width; x += 48) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke();
    }
    for (let y = 0; y <= height; y += 48) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
    }

    ctx.strokeStyle = "#65e7ff";
    ctx.lineWidth = 2;
    ctx.strokeRect(34, 34, width - 68, height - 68);
    ctx.fillStyle = "#65e7ff";
    ctx.font = "800 19px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.letterSpacing = "2px";
    ctx.fillText("AWESOME AGENTIC USE CASES / LOCAL REVIEW RECEIPT", 72, 85);

    ctx.fillStyle = "#eefcff";
    ctx.font = "800 58px system-ui, -apple-system, sans-serif";
    ctx.fillText("CAN YOU TRUST", 72, 164);
    ctx.fillStyle = "#65e7ff";
    ctx.font = "italic 400 62px Georgia, serif";
    ctx.fillText("THIS AGENT?", 72, 225);

    ctx.fillStyle = "#eefcff";
    ctx.font = "850 178px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.fillText(String(score), 72, 432);
    ctx.fillStyle = "#91abb1";
    ctx.font = "800 48px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.fillText("/5 EXACT", 192, 425);
    ctx.fillStyle = "#9df8bd";
    ctx.font = "800 26px system-ui, -apple-system, sans-serif";
    ctx.fillText(profile.name.toUpperCase(), 76, 486);

    const panelX = 592;
    ctx.fillStyle = "rgba(4,16,19,0.9)";
    ctx.fillRect(panelX, 116, 530, 366);
    ctx.strokeStyle = "#29434a";
    ctx.strokeRect(panelX, 116, 530, 366);
    ctx.fillStyle = "#91abb1";
    ctx.font = "800 16px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.fillText("FIVE COMMITTED TRACES", panelX + 30, 158);

    answers.forEach(({ item, answer }, index) => {
      const y = 205 + index * 50;
      ctx.fillStyle = answer.correct ? "#9df8bd" : "#ffc857";
      ctx.fillRect(panelX + 31, y - 15, 12, 12);
      ctx.fillStyle = "#eefcff";
      ctx.font = "750 18px system-ui, -apple-system, sans-serif";
      fitCanvasText(ctx, item.failure_shape, panelX + 60, y - 2, 420, 20, 1);
      ctx.fillStyle = "#78949a";
      ctx.font = "700 13px ui-monospace, SFMono-Regular, Menlo, monospace";
      ctx.fillText(answer.correct ? "MATCHED" : "REVISIT", panelX + 414, y - 2);
    });

    ctx.fillStyle = "#91abb1";
    ctx.font = "700 16px system-ui, -apple-system, sans-serif";
    ctx.fillText("One local session · not a certification", 72, 553);
    ctx.fillStyle = "#65e7ff";
    ctx.font = "800 17px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.fillText("immu4989.github.io/awesome-agentic-usecases", 592, 553);
  }

  function renderReceipt() {
    const answers = sessionAnswers();
    if (answers.length !== state.data.cases.length) {
      els.receipt.hidden = true;
      return;
    }
    const score = answers.filter(({ answer }) => answer.correct).length;
    const profile = reviewProfile(score);
    const caught = answers.filter(({ answer }) => answer.correct).map(({ item }) => item.failure_shape);
    const missed = answers.filter(({ answer }) => !answer.correct).map(({ item }) => item.failure_shape);
    const shareUrl = resultShareUrl(score);
    const shareText = resultShareText(score, profile.name);
    els.profile.textContent = profile.name;
    els.profileNote.textContent = `${profile.note} This is a session description—not a professional score, credential, or certification.`;
    els.finalScore.textContent = String(score);
    listFindings(els.caught, caught, "No exact matches yet—use each reveal as a second-pass evidence map.");
    listFindings(els.missed, missed, "No failure shapes missed in this session.");
    els.shareX.dataset.shareUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(shareUrl)}`;
    els.shareLinkedIn.dataset.shareUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`;
    els.copyResult.dataset.shareUrl = shareUrl;
    els.receipt.hidden = false;
    drawResultCard(score, profile, answers);
  }

  function updateSession() {
    const answers = Object.entries(state.answers).filter(([id]) => state.data.cases.some((item) => item.id === id));
    els.reviewed.textContent = String(answers.length);
    els.score.textContent = String(answers.filter(([, answer]) => answer.correct).length);
    renderReceipt();
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
    els.next.textContent = sessionAnswers().length === state.data.cases.length ? "See my review receipt ↓" : "Next unreviewed case →";
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
    const issueTitle = `[playground ground-truth dispute] ${item.title}`;
    const issueBody = [
      "## Ground-truth dispute",
      "",
      `**Playground case:** ${item.title} (${item.id})`,
      `**Committed reviewer action:** ${state.data.verdicts[item.verdict].label}`,
      `**Scenario source:** ${item.links.scenario}`,
      `**Model result:** ${item.links.result}`,
      "",
      "### What I dispute",
      "Describe the exact decision, premise, or expected action that should change.",
      "",
      "### Primary evidence",
      "Link the authoritative source and quote the narrow passage that supports the correction.",
      "",
      "### Proposed test change",
      "Explain the assertion or scenario update that would prevent regression.",
    ].join("\n");
    els.disputeLink.href = `${REPO_URL}/issues/new?title=${encodeURIComponent(issueTitle)}&body=${encodeURIComponent(issueBody)}`;
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
    els.resultStatus.textContent = "Session reset. No local answers remain.";
  }

  function nextStep() {
    if (sessionAnswers().length === state.data.cases.length) {
      els.receipt.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    for (let offset = 1; offset <= state.data.cases.length; offset += 1) {
      const index = (state.caseIndex + offset) % state.data.cases.length;
      if (!state.answers[state.data.cases[index].id]) {
        selectCase(index, true);
        return;
      }
    }
  }

  function downloadResultCard() {
    els.canvas.toBlob((blob) => {
      if (!blob) {
        els.resultStatus.textContent = "This browser could not generate the PNG. You can still copy the result link.";
        return;
      }
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `agent-evidence-review-${els.finalScore.textContent}-of-5.png`;
      link.click();
      URL.revokeObjectURL(url);
      els.resultStatus.textContent = "Result card downloaded. The image was generated locally.";
    }, "image/png");
  }

  function openShare(button) {
    const url = button.dataset.shareUrl;
    if (url) window.open(url, "_blank", "noopener,noreferrer");
  }

  async function copyResult() {
    const score = els.finalScore.textContent;
    const text = `${resultShareText(score, els.profile.textContent)} ${els.copyResult.dataset.shareUrl}`;
    try {
      await navigator.clipboard.writeText(text);
      els.resultStatus.textContent = "Result and challenge link copied.";
    } catch {
      els.resultStatus.textContent = text;
    }
  }

  function renderSharedInvitation() {
    const value = new URLSearchParams(location.search).get("challenge");
    const score = Number(value);
    const valid = /^\d$/.test(value || "") && score >= 0 && score <= state.data.cases.length;
    els.invitation.hidden = !valid;
    if (valid) {
      els.invitationScore.textContent = `A reviewer shared a self-reported ${score}/${state.data.cases.length}. Can you beat it?`;
    }
  }

  function dismissInvitation() {
    const params = new URLSearchParams(location.search);
    params.delete("challenge");
    const query = params.toString();
    history.replaceState(null, "", `${location.pathname}${query ? `?${query}` : ""}#playground`);
    els.invitation.hidden = true;
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
    els.next.addEventListener("click", nextStep);
    els.downloadCard.addEventListener("click", downloadResultCard);
    els.shareX.addEventListener("click", () => openShare(els.shareX));
    els.shareLinkedIn.addEventListener("click", () => openShare(els.shareLinkedIn));
    els.copyResult.addEventListener("click", copyResult);
    els.dismissInvitation.addEventListener("click", dismissInvitation);
    els.verdicts.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-playground-verdict]");
      if (button) chooseVerdict(button.dataset.playgroundVerdict);
    });
    window.addEventListener("popstate", () => {
      state.caseIndex = caseFromUrl();
      renderCase();
    });
    renderSharedInvitation();
    renderCase();
  }

  init().catch((error) => {
    els.room.innerHTML = `<div class="playground-error">${error.message}. Open the playground evidence on GitHub instead.</div>`;
  });
})();
