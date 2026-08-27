(() => {
  "use strict";
  const state = { data: null, selected: null };
  const byId = (id) => document.getElementById(id);
  const github = "https://github.com/immu4989/awesome-agentic-usecases";
  const text = (id, value) => { byId(id).textContent = value; };
  const percent = (value) => `${Math.round(value * 100)}%`;
  const label = (value) => String(value).replaceAll("_", " ");

  function list(id, values) {
    const target = byId(id);
    target.replaceChildren(...values.map((value) => {
      const item = document.createElement("li");
      item.textContent = value;
      return item;
    }));
  }

  function renderCards() {
    const target = byId("commons-card-list");
    target.replaceChildren(...state.data.capsules.map((capsule, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "commons-card";
      button.dataset.capsuleId = capsule.id;
      button.setAttribute("aria-pressed", String(capsule.id === state.selected));
      const number = document.createElement("span");
      number.textContent = `CAPSULE ${String(index + 1).padStart(2, "0")} / ${label(capsule.status)}`;
      const title = document.createElement("b"); title.textContent = capsule.title;
      const area = document.createElement("small"); area.textContent = capsule.service_area;
      button.append(number, title, area);
      button.addEventListener("click", () => select(capsule.id));
      return button;
    }));
  }

  function renderMeasures(capsule) {
    const target = byId("commons-measure-grid");
    target.replaceChildren(...capsule.measurement_plan.map((measure) => {
      const card = document.createElement("article");
      const title = document.createElement("b"); title.textContent = measure.name;
      const detail = document.createElement("small"); detail.textContent = `${measure.affected_group} · ${measure.measurement_window}`;
      const direction = document.createElement("i"); direction.textContent = `${label(measure.direction)} · ${measure.unit}`;
      card.append(title, detail, direction);
      return card;
    }));
  }

  function renderSources(capsule) {
    const target = byId("commons-source-row");
    target.replaceChildren(...capsule.sources.map((source) => {
      const link = document.createElement("a");
      link.href = source.url; link.target = "_blank"; link.rel = "noopener";
      link.textContent = `${source.publisher} ↗`;
      link.title = `${source.title} — reviewed ${source.reviewed_at}`;
      return link;
    }));
  }

  function select(id) {
    const capsule = state.data.capsules.find((item) => item.id === id);
    if (!capsule) return;
    state.selected = id;
    document.querySelectorAll(".commons-card").forEach((button) => {
      const chosen = button.dataset.capsuleId === id;
      button.classList.toggle("is-selected", chosen);
      button.setAttribute("aria-pressed", String(chosen));
    });
    text("commons-detail-kicker", `${capsule.service_area} / ${label(capsule.status)}`);
    text("commons-detail-title", capsule.title);
    text("commons-detail-mission", capsule.mission);
    text("commons-detail-status", label(capsule.status));
    text("commons-agent-rate", percent(capsule.agent.value));
    text("commons-agent-detail", `${capsule.agent.observation_count} synthetic observations · ${capsule.agent.name}`);
    text("commons-human-rate", capsule.human_comparator ? percent(capsule.human_comparator.exact_rate) : "OPEN");
    text("commons-human-detail", capsule.human_comparator ? "aggregate comparator published" : "no observed comparator");
    text("commons-impact-rate", capsule.public_value_observed ? "BOUND" : "OPEN");
    text("commons-impact-detail", capsule.public_value_observed ? "bounded observation present" : "no public-value observation");
    text("commons-authority-role", capsule.human_authority.accountable_role);
    list("commons-beneficiaries", capsule.beneficiaries);
    list("commons-protected", capsule.human_authority.protected_decisions);
    list("commons-gaps-list", capsule.missing_evidence);
    renderMeasures(capsule);
    renderSources(capsule);
    byId("commons-capsule-link").href = `${github}/blob/main/${capsule.capsule_path}`;
    byId("commons-partner-link").href = capsule.partner_call.contact_url;
    text("commons-status-line", `First honest next step: ${capsule.next_evidence}.`);
  }

  async function copyCommand() {
    const capsule = state.data.capsules.find((item) => item.id === state.selected);
    const command = `aau evidence compare ${capsule.capsule_path} --json`;
    try {
      await navigator.clipboard.writeText(command);
      text("commons-status-line", "Inspection command copied. It derives status and shows every missing link.");
    } catch {
      text("commons-status-line", command);
    }
  }

  async function start() {
    try {
      const response = await fetch("evidence-commons-data.json");
      if (!response.ok) throw new Error("data unavailable");
      state.data = await response.json();
      state.selected = state.data.capsules[0].id;
      text("commons-capsule-count", state.data.stats.capsules);
      text("commons-gap-count", state.data.stats.visible_gaps);
      text("commons-partner-count", state.data.stats.open_partner_calls);
      renderCards(); select(state.selected);
      byId("commons-copy-cli").addEventListener("click", copyCommand);
    } catch {
      text("commons-status-line", "The live evidence index could not load. The repository capsules and CLI remain available.");
    }
  }
  document.addEventListener("DOMContentLoaded", start);
})();
