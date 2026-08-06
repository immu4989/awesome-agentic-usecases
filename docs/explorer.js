const REPO = "https://github.com/immu4989/awesome-agentic-usecases";
const state = { cases: [], search: "", industry: "all" };

const els = {
  grid: document.querySelector("#grid"),
  count: document.querySelector("#count"),
  search: document.querySelector("#search"),
  industry: document.querySelector("#industry"),
  clear: document.querySelector("#clear"),
  goals: document.querySelectorAll("[data-query]")
};

function searchable(item) {
  return [item.title, item.industry, item.kind, item.question, ...item.capabilities]
    .join(" ").toLocaleLowerCase();
}

function filteredCases() {
  const terms = state.search.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return state.cases.filter((item) => {
    const matchesIndustry = state.industry === "all" || item.industry === state.industry;
    const haystack = searchable(item);
    return matchesIndustry && terms.every((term) => haystack.includes(term));
  });
}

function cardAccent(item) {
  const terms = `${item.kind} ${item.industry} ${item.capabilities.join(" ")}`.toLocaleLowerCase();
  if (/security|adversarial|injection|exfil|poison/.test(terms)) return "var(--red)";
  if (/guardrail|environment|tool enforcement|approval/.test(terms)) return "var(--green)";
  if (/regulated|statutory|record|compliance|financial/.test(terms)) return "var(--amber)";
  if (/memory|multi-agent|coordination|context/.test(terms)) return "var(--violet)";
  return "var(--blue)";
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
  for (const capability of item.capabilities) {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = capability;
    tags.append(tag);
  }
  const link = document.createElement("a");
  link.className = "card-link";
  link.href = `${REPO}/tree/main/${item.path}`;
  link.textContent = "Open verified use case →";
  link.setAttribute("aria-label", `Open ${item.title} on GitHub`);

  const copy = document.createElement("button");
  copy.className = "copy";
  copy.type = "button";
  copy.textContent = "Copy start command";
  copy.setAttribute("aria-label", `Copy the aau start command for ${item.title}`);
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(`aau start ${item.cli}`);
      copy.textContent = "Copied";
    } catch {
      copy.textContent = `aau start ${item.cli}`;
    }
    setTimeout(() => { copy.textContent = "Copy start command"; }, 1800);
  });

  const actions = document.createElement("div");
  actions.className = "card-actions";
  actions.append(link, copy);

  article.append(top, heading, industry, question, tags, actions);
  return article;
}

function render() {
  const items = filteredCases();
  els.grid.replaceChildren();
  els.count.innerHTML = `<strong>${items.length}</strong> of ${state.cases.length} verified use cases`;
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No use case matches those filters. Try a capability like security, act, gate, or memory.";
    els.grid.append(empty);
    return;
  }
  els.grid.append(...items.map(card));
}

function syncUrl() {
  const params = new URLSearchParams();
  if (state.search) params.set("q", state.search);
  if (state.industry !== "all") params.set("industry", state.industry);
  history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}`);
}

async function init() {
  const response = await fetch("use-cases.json");
  if (!response.ok) throw new Error(`Catalog failed to load (${response.status})`);
  state.cases = await response.json();

  const params = new URLSearchParams(location.search);
  state.search = params.get("q") || "";
  state.industry = params.get("industry") || "all";
  els.search.value = state.search;

  const industries = [...new Set(state.cases.map((item) => item.industry))].sort();
  for (const name of industries) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    els.industry.append(option);
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
  render();
}

init().catch((error) => {
  els.grid.innerHTML = `<div class="empty">${error.message}. Open the repository catalog on GitHub instead.</div>`;
});
