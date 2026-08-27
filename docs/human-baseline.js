(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const state = { data: null, index: -1, choice: null, started: 0, results: [] };
  const labels = {
    route_current_official_source: "Route to the current official source",
    route_accessible_human_help: "Route to accessible staffed help",
    stop_stale_or_unauthorized: "Stop: stale source or unauthorized action",
    __abstain__: "Need more information / abstain",
  };

  function cleanLabel(value) {
    return String(value).replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function median(values) {
    const sorted = [...values].sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  }

  function downloadJson(filename, value) {
    const blob = new Blob([`${JSON.stringify(value, null, 2)}\n`], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = filename; document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function renderSources() {
    byId("human-source-list").innerHTML = state.data.sources.map((source) => `<article><span>OFFICIAL SOURCE</span><b>${source.title}</b><small>${source.supports}</small><a href="${source.url}">Inspect source ↗</a></article>`).join("");
  }

  function updateProgress() {
    const total = state.data.study.cases.length;
    const completed = state.results.length;
    byId("human-progress-copy").textContent = `${completed ? "In progress" : "Ready"} · ${completed} of ${total}`;
    byId("human-progress-bar").style.width = `${(completed / total) * 100}%`;
    byId("human-live-abstain").textContent = state.results.filter((result) => result.outcome === "__abstain__").length;
    if (completed) {
      byId("human-live-time").textContent = `${(median(state.results.map((result) => result.elapsed_ms)) / 1000).toFixed(1)}s`;
      byId("human-live-confidence").textContent = `${Math.round(state.results.reduce((sum, result) => sum + result.confidence, 0) / completed)}%`;
    }
  }

  function renderCase() {
    const study = state.data.study;
    const current = study.cases[state.index];
    state.choice = null;
    state.started = performance.now();
    byId("human-task-id").textContent = current.scenario_id.toUpperCase();
    byId("human-task-number").textContent = `${String(state.index + 1).padStart(2, "0")} / ${String(study.cases.length).padStart(2, "0")}`;
    byId("human-task-question").textContent = current.input.request || "Choose the safest exact route.";
    byId("human-task-facts").innerHTML = Object.entries(current.input).filter(([key]) => key !== "request").map(([key, value]) => `<div><span>${cleanLabel(key)}</span>${typeof value === "boolean" ? (value ? "Yes" : "No") : cleanLabel(value)}</div>`).join("");
    const outcomes = [...study.outcomes, "__abstain__"];
    byId("human-outcomes").innerHTML = `<legend>Choose the safest exact route</legend>${outcomes.map((outcome) => `<button type="button" data-human-outcome="${outcome}">${labels[outcome] || cleanLabel(outcome)}</button>`).join("")}`;
    byId("human-outcomes").disabled = false;
    byId("human-outcomes").querySelectorAll("button").forEach((button) => button.addEventListener("click", () => {
      state.choice = button.dataset.humanOutcome;
      byId("human-outcomes").querySelectorAll("button").forEach((item) => item.classList.toggle("is-selected", item === button));
      byId("human-next").disabled = false;
    }));
    byId("human-confidence").disabled = false;
    byId("human-next").disabled = true;
    byId("human-next").textContent = state.index === study.cases.length - 1 ? "Finish and reveal →" : "Record and continue →";
    byId("human-status").textContent = "The oracle remains hidden. Your answer stays in this tab.";
    byId("human-timer").textContent = "Task timer running locally";
  }

  function startStudy() {
    state.index = 0; state.choice = null; state.results = [];
    byId("human-result").hidden = true;
    byId("human-live-exact").textContent = "—";
    byId("human-live-time").textContent = "—";
    byId("human-live-confidence").textContent = "—";
    updateProgress(); renderCase();
    byId("human-workbench").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function finishStudy() {
    const answers = state.data.practice_answer_key;
    const exact = state.results.filter((result) => result.outcome === answers[result.scenario_id]).length;
    const abstains = state.results.filter((result) => result.outcome === "__abstain__").length;
    const exactRate = exact / state.results.length;
    const meanConfidence = state.results.reduce((sum, result) => sum + result.confidence, 0) / state.results.length;
    const calibrationGap = Math.abs(meanConfidence / 100 - exactRate);
    const referenceRate = state.data.reference.report_metrics.outcome_exact_rate;
    const agentRate = state.data.reference.agent_comparison.agent_exact_rate;
    byId("human-live-exact").textContent = `${Math.round(exactRate * 100)}%`;
    byId("human-result-exact").textContent = `${Math.round(exactRate * 100)}%`;
    byId("human-result-detail").textContent = `${exact}/${state.results.length} exact · ${abstains} abstain · ${Math.round(calibrationGap * 100)}-point calibration gap`;
    byId("human-reference-exact").textContent = `${Math.round(referenceRate * 100)}%`;
    byId("human-agent-exact").textContent = `${Math.round(agentRate * 100)}%`;
    byId("human-user-bar").style.width = `${exactRate * 100}%`;
    byId("human-reference-bar").style.width = `${referenceRate * 100}%`;
    byId("human-agent-bar").style.width = `${agentRate * 100}%`;
    byId("human-result-interpretation").textContent = "This comparison demonstrates the measurement contract only. Your one practice run is not a human baseline; the five reference sessions are generated, and the agent receipt contains deliberate misses. A decision needs reviewed tasks, an appropriate institutional determination, enough representative participants, uncertainty, and operational evidence.";
    byId("human-result").hidden = false;
    byId("human-outcomes").disabled = true; byId("human-confidence").disabled = true; byId("human-next").disabled = true;
    byId("human-timer").textContent = "Practice complete · timer stopped";
    byId("human-progress-copy").textContent = `Complete · ${state.results.length} of ${state.results.length}`;
    byId("human-progress-bar").style.width = "100%";
    byId("human-result").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function recordAndContinue() {
    if (!state.choice) return;
    const current = state.data.study.cases[state.index];
    state.results.push({ scenario_id: current.scenario_id, outcome: state.choice, confidence: Number(byId("human-confidence").value), elapsed_ms: Math.max(1, Math.round(performance.now() - state.started)) });
    updateProgress();
    if (state.index === state.data.study.cases.length - 1) finishStudy();
    else { state.index += 1; renderCase(); }
  }

  function practiceReceipt() {
    const answers = state.data.practice_answer_key;
    const exact = state.results.filter((result) => result.outcome === answers[result.scenario_id]).length;
    const abstains = state.results.filter((result) => result.outcome === "__abstain__").length;
    return {
      receipt_version: "aau-human-baseline-practice/1.0",
      study_id: state.data.study.study_id,
      practice_only: true,
      metrics: {
        response_count: state.results.length,
        outcome_exact_rate: Number((exact / state.results.length).toFixed(4)),
        abstain_rate: Number((abstains / state.results.length).toFixed(4)),
        median_task_time_ms: Math.round(median(state.results.map((result) => result.elapsed_ms))),
        mean_confidence: Number((state.results.reduce((sum, result) => sum + result.confidence, 0) / state.results.length).toFixed(2)),
      },
      privacy: { raw_responses_included: false, participant_identifier_included: false, uploaded: false },
      boundary: "Individual synthetic practice only. Not a participant session, human baseline, research result, workforce measure, production validation, or deployment decision.",
    };
  }

  async function copyCli() {
    const command = 'aau baseline prepare suite.json --id my-human-baseline --title "My Human Baseline" --purpose "Compare the reviewed task with the existing process" --out human-baseline-pack';
    try { await navigator.clipboard.writeText(command); byId("human-status").textContent = "CLI study command copied."; }
    catch { byId("human-status").textContent = command; }
  }

  async function start() {
    try {
      state.data = await fetch("human-baseline-data.json").then((response) => { if (!response.ok) throw new Error("data unavailable"); return response.json(); });
      byId("human-case-count").textContent = state.data.study.cases.length;
      byId("human-task-number").textContent = `00 / ${String(state.data.study.cases.length).padStart(2, "0")}`;
      renderSources();
    } catch {
      byId("human-status").textContent = "The reference study could not load. The repository CLI kit remains available.";
      return;
    }
    byId("human-start").addEventListener("click", startStudy);
    byId("human-next").addEventListener("click", recordAndContinue);
    byId("human-restart").addEventListener("click", startStudy);
    byId("human-confidence").addEventListener("input", () => { byId("human-confidence-value").textContent = `${byId("human-confidence").value}%`; });
    byId("human-download-practice").addEventListener("click", () => downloadJson("aau-human-baseline-practice-receipt.json", practiceReceipt()));
    byId("human-copy-cli").addEventListener("click", copyCli);
  }

  document.addEventListener("DOMContentLoaded", start);
})();
