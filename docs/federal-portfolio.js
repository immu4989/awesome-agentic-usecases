(() => {
  "use strict";

  const root = document.querySelector("#portfolio-observatory");
  if (!root) return;

  const byId = (id) => document.getElementById(id);
  const node = (tag, className, text) => {
    const value = document.createElement(tag);
    if (className) value.className = className;
    if (text !== undefined) value.textContent = String(text);
    return value;
  };
  const formatName = (value) => String(value || "").replaceAll("_", " ");
  const titleName = (value) => formatName(value).replace(/\b\w/g, (letter) => letter.toUpperCase());
  const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  const repoTree = ["https:", "", "github.com", "immu4989", "awesome-agentic-usecases", "tree", "main"].join("/");
  let publicData = null;
  let selectedId = null;
  let localReceipt = null;

  const renderCaseDetail = (entry) => {
    const item = publicData.inventory.use_cases.find((candidate) => candidate.use_case_id === entry.use_case_id);
    byId("portfolio-selected-state").textContent = entry.quality_state;
    byId("portfolio-selected-state").dataset.state = entry.quality_state;
    byId("portfolio-selected-lifecycle").textContent = `${item.lifecycle} · ${item.high_impact_status}`;
    byId("portfolio-selected-title").textContent = entry.title;
    byId("portfolio-selected-mission").textContent = item.mission;
    const issues = byId("portfolio-selected-issues");
    issues.replaceChildren();
    if (!entry.issues.length) {
      issues.append(node("p", "portfolio-no-issue", "No structural quality gap was found in the declared fields. This is not validation of performance or approval."));
    } else {
      entry.issues.forEach((issue) => {
        const card = node("article", "portfolio-issue");
        card.append(node("b", "", `${issue.severity} / ${titleName(issue.code)}`), node("p", "", issue.remedy));
        issues.append(card);
      });
    }
    const labs = byId("portfolio-selected-labs");
    labs.replaceChildren();
    if (!entry.candidate_aau_labs.length) {
      labs.append(node("p", "portfolio-no-issue", "No catalog match cleared the simple lexical threshold. Search the full Explorer before building a new lab."));
    } else {
      entry.candidate_aau_labs.forEach((match) => {
        const card = node("article", "portfolio-lab");
        const copy = node("div");
        const link = node("a", "", match.title);
        link.href = `${repoTree}/${match.path}`;
        copy.append(link, node("p", "", "Candidate evaluation contract only—domain fit still requires human review."));
        card.append(copy, node("small", "", `fit ${match.fit_score.toFixed(3)}`));
        labs.append(card);
      });
    }
  };

  const renderCases = () => {
    const query = byId("portfolio-search").value.trim().toLowerCase();
    const entries = publicData.analysis.entries.filter((entry) => {
      const item = publicData.inventory.use_cases.find((candidate) => candidate.use_case_id === entry.use_case_id);
      const terms = [entry.title, entry.quality_state, entry.lifecycle, item.mission, item.high_impact_status, ...entry.issues.map((issue) => issue.code)].join(" ").toLowerCase();
      return terms.includes(query);
    });
    byId("portfolio-match-count").textContent = `${entries.length} / ${publicData.analysis.entries.length} entries`;
    const list = byId("portfolio-case-list");
    list.replaceChildren();
    entries.forEach((entry) => {
      const button = node("button", `portfolio-case ${entry.quality_state}`);
      button.type = "button";
      button.dataset.id = entry.use_case_id;
      if (entry.use_case_id === selectedId) button.classList.add("is-active");
      const state = node("span", "", entry.quality_state);
      const copy = node("div");
      copy.append(node("b", "", entry.title), node("p", "", entry.issues.length ? `${entry.issues.length} open evidence question${entry.issues.length === 1 ? "" : "s"}` : "Declared fields structurally documented"), node("small", "", `${entry.lifecycle} · human decision required`));
      button.append(state, copy);
      button.addEventListener("click", () => {
        selectedId = entry.use_case_id;
        renderCases();
        renderCaseDetail(entry);
      });
      list.append(button);
    });
    if (!entries.length) list.append(node("p", "portfolio-no-issue", "No entries match this filter."));
    if (entries.length) {
      const selected = entries.find((entry) => entry.use_case_id === selectedId) || entries[0];
      selectedId = selected.use_case_id;
      list.querySelectorAll("button").forEach((button) => button.classList.toggle("is-active", button.dataset.id === selectedId));
      renderCaseDetail(selected);
    }
  };

  const renderOverlap = () => {
    const list = byId("portfolio-overlap-list");
    list.replaceChildren();
    publicData.analysis.possible_overlaps.forEach((overlap) => {
      const left = publicData.inventory.use_cases.find((item) => item.use_case_id === overlap.left_use_case_id);
      const right = publicData.inventory.use_cases.find((item) => item.use_case_id === overlap.right_use_case_id);
      const card = node("article", "portfolio-overlap-card");
      card.append(node("b", "", `${left.title} ↔ ${right.title}`), node("p", "", overlap.boundary), node("small", "", `${Math.round(overlap.similarity * 100)}% lexical similarity · ${overlap.shared_capabilities.join(" · ")}`));
      list.append(card);
    });
  };

  const renderPublicValue = () => {
    const assessment = publicData.public_value.assessment;
    byId("portfolio-value-summary").textContent = `${assessment.summary.measured} measured · ${assessment.summary.baseline_only} baseline only · ${money.format(assessment.summary.pilot_cost_usd)} pilot cost`;
    const list = byId("portfolio-value-records");
    list.replaceChildren();
    assessment.records.forEach((record) => {
      const source = publicData.public_value.ledger.records.find((item) => item.record_id === record.record_id);
      const item = publicData.inventory.use_cases.find((candidate) => candidate.use_case_id === record.use_case_id);
      const card = node("article", "portfolio-value-card");
      card.append(node("span", "", record.measurement_state), node("h5", "", item.title));
      const metrics = node("div", "portfolio-value-metrics");
      const time = node("div");
      time.append(node("b", "", record.minutes_per_case_change === null ? "—" : `${record.minutes_per_case_change} min`), node("small", "", "minutes / case change"));
      const errors = node("div");
      errors.append(node("b", "", record.error_rate_change === null ? "—" : `${(record.error_rate_change * 100).toFixed(1)} pp`), node("small", "", "error-rate change"));
      metrics.append(time, errors);
      card.append(metrics, node("p", "", source.measurement.limitations), node("p", "", "Verified savings claim: NO · observed change remains bounded to the declared method."));
      list.append(card);
    });
  };

  const renderContracts = () => {
    const layers = byId("portfolio-tev-v-layers");
    layers.replaceChildren();
    publicData.tev_v.coverage.layers.forEach((layer, index) => {
      const source = publicData.tev_v.plan.layers.find((item) => item.layer === layer.layer);
      const row = node("article", "portfolio-layer");
      const copy = node("div");
      copy.append(node("b", "", titleName(layer.layer)), node("small", "", source.objective));
      row.append(node("span", "", `0${index + 1}`), copy, node("i", "", `${layer.methods} methods · ${layer.stop_conditions} stops`));
      layers.append(row);
    });
    const clauses = byId("portfolio-clause-list");
    clauses.replaceChildren();
    publicData.clauses.coverage.clauses.forEach((clause, index) => {
      const row = node("article", "portfolio-clause");
      const copy = node("div");
      copy.append(node("b", "", titleName(clause.area)), node("small", "", `${clause.human_owner_role} owns the evidence path`));
      row.append(node("span", "", String(index + 1).padStart(2, "0")), copy, node("i", "", `${clause.tests} test · ${clause.required_evidence} evidence`));
      clauses.append(row);
    });
  };

  const renderSources = () => {
    byId("portfolio-source-state").textContent = `${publicData.policy_drift.current} current · ${publicData.policy_drift.review_due} review due`;
    const list = byId("portfolio-source-list");
    list.replaceChildren();
    publicData.sources.sources.forEach((source) => {
      const card = node("article", "portfolio-source");
      const link = node("a", "", "Open official source ↗");
      link.href = source.url;
      const description = source.use || source.relevance || source.notes || "Official dependency recorded in the canonical source ledger.";
      card.append(node("b", "", source.title), node("p", "", description), link, node("small", "", `verified ${source.last_verified} · review ${source.review_due}`));
      list.append(card);
    });
  };

  const words = (value) => new Set(String(Array.isArray(value) ? value.join(" ") : value || "").toLowerCase().replaceAll("_", " ").match(/[a-z0-9]{3,}/g) || []);
  const possibleOverlap = (left, right) => {
    const leftWords = words([left.title, left.mission, ...(left.capabilities || [])]);
    const rightWords = words([right.title, right.mission, ...(right.capabilities || [])]);
    const union = new Set([...leftWords, ...rightWords]);
    const shared = [...leftWords].filter((word) => rightWords.has(word));
    const capabilities = (left.capabilities || []).filter((capability) => (right.capabilities || []).includes(capability));
    const similarity = union.size ? shared.length / union.size : 0;
    if (similarity < .28 || capabilities.length < 2) return null;
    return { left_use_case_id: left.use_case_id, right_use_case_id: right.use_case_id, similarity: Number(similarity.toFixed(3)), shared_capabilities: capabilities, disposition: "human-review-required" };
  };

  const qualityIssues = (item) => {
    const required = [
      ["owner_role", "missing-owner", "critical"], ["expected_benefit", "missing-benefit", "critical"],
      ["system_boundary", "missing-boundary", "critical"], ["human_authority", "missing-human-authority", "critical"],
    ];
    const issues = required.filter(([field]) => !String(item[field] || "").trim()).map(([field, code, severity]) => ({ field, code, severity }));
    if (!Array.isArray(item.performance_metrics) || !item.performance_metrics.length) issues.push({ field: "performance_metrics", code: "missing-performance-metric", severity: "critical" });
    if (!Array.isArray(item.strategic_goal_ids) || !item.strategic_goal_ids.length) issues.push({ field: "strategic_goal_ids", code: "unmapped-strategic-goal", severity: "important" });
    if (item.high_impact_status === "uncertain_requires_review") issues.push({ field: "high_impact_status", code: "impact-review-open", severity: "critical" });
    if (item.estimated_annual_cost_usd === null || item.estimated_annual_cost_usd === undefined) issues.push({ field: "estimated_annual_cost_usd", code: "cost-unknown", severity: "important" });
    return issues;
  };

  const assertPublicInventory = (inventory) => {
    if (!inventory || inventory.profile_version !== "aau-federal-ai-portfolio/0.5" || !Array.isArray(inventory.use_cases) || !inventory.use_cases.length) throw new Error("Expected a non-empty aau-federal-ai-portfolio/0.5 inventory.");
    const sharing = inventory.sharing || {};
    if (!["public", "synthetic", "public_synthetic"].includes(sharing.classification) || sharing.human_review_complete !== true) throw new Error("Public/synthetic classification and completed human review are required.");
    const forbidden = ["contains_personally_identifiable_information", "contains_procurement_sensitive_information", "contains_controlled_unclassified_information", "contains_classified_information", "contains_secrets_or_credentials"];
    if (forbidden.some((field) => sharing[field] !== false)) throw new Error("All five public-sharing exclusions must be explicitly false.");
    const raw = JSON.stringify(inventory);
    if (/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i.test(raw) || /\b\d{3}-\d{2}-\d{4}\b/.test(raw) || /BEGIN [A-Z ]*PRIVATE KEY/.test(raw) || /\bgh[pousr]_[A-Za-z0-9]{20,}\b/.test(raw)) throw new Error("A narrow sensitive-data pattern blocked local analysis. Review the file outside this public tool.");
  };

  const analyzeLocalInventory = (inventory) => {
    assertPublicInventory(inventory);
    const entries = inventory.use_cases.map((item) => {
      const issues = qualityIssues(item);
      return { use_case_id: item.use_case_id, title: item.title, quality_state: issues.length ? "needs-evidence" : "documented", issues };
    });
    const possible_overlap = [];
    inventory.use_cases.forEach((left, index) => inventory.use_cases.slice(index + 1).forEach((right) => {
      const match = possibleOverlap(left, right);
      if (match) possible_overlap.push(match);
    }));
    return {
      analysis_version: "aau-federal-portfolio-browser-analysis/0.5",
      portfolio_id: inventory.portfolio_id,
      as_of: inventory.as_of,
      summary: {
        use_cases: entries.length,
        documented: entries.filter((entry) => !entry.issues.length).length,
        needs_evidence: entries.filter((entry) => entry.issues.length).length,
        critical_gaps: entries.flatMap((entry) => entry.issues).filter((issue) => issue.severity === "critical").length,
        important_gaps: entries.flatMap((entry) => entry.issues).filter((issue) => issue.severity === "important").length,
        possible_overlaps: possible_overlap.length,
      },
      entries,
      possible_overlap,
      privacy: { inputs_included: false, matched_values_included: false, credentials_included: false },
      decisions: { investment: "not-produced", award: "not-produced", deployment: "not-produced", cancellation: "not-produced" },
      boundary: "Local structural analysis is not portfolio ranking, proof of duplication, disclosure authorization, certification, legal advice, or a protected decision.",
    };
  };

  const downloadReceipt = () => {
    if (!localReceipt) return;
    const blob = new Blob([`${JSON.stringify(localReceipt, null, 2)}\n`], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = node("a");
    link.href = url;
    link.download = `${localReceipt.portfolio_id || "portfolio"}-public-analysis.json`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const handleLocalFile = async (event) => {
    const status = byId("portfolio-local-status");
    status.className = "";
    localReceipt = null;
    byId("portfolio-download").disabled = true;
    const file = event.target.files[0];
    if (!file) {
      status.textContent = "No local inventory selected.";
      return;
    }
    try {
      if (file.size > 1_000_000) throw new Error("Inventory exceeds the 1 MB browser limit.");
      const inventory = JSON.parse(await file.text());
      localReceipt = analyzeLocalInventory(inventory);
      const summary = localReceipt.summary;
      status.textContent = `Ready: ${summary.use_cases} entries · ${summary.documented} documented · ${summary.critical_gaps} critical gaps · ${summary.possible_overlaps} possible overlaps. No investment decision was produced.`;
      status.className = "is-ready";
      byId("portfolio-download").disabled = false;
    } catch (error) {
      status.textContent = `Blocked: ${error.message}`;
      status.className = "is-blocked";
    }
  };

  fetch("federal-portfolio-data.json")
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((data) => {
      publicData = data;
      const summary = data.analysis.summary;
      byId("portfolio-count").textContent = summary.use_cases;
      byId("portfolio-documented").textContent = summary.documented;
      byId("portfolio-critical").textContent = summary.critical_gaps;
      byId("portfolio-overlap-count").textContent = summary.possible_overlaps;
      selectedId = data.analysis.entries[0].use_case_id;
      renderCases();
      renderOverlap();
      renderPublicValue();
      renderContracts();
      renderSources();
    })
    .catch((error) => {
      byId("portfolio-match-count").textContent = `Could not load: ${error.message}`;
    });

  byId("portfolio-search").addEventListener("input", () => publicData && renderCases());
  byId("portfolio-local-file").addEventListener("change", handleLocalFile);
  byId("portfolio-download").addEventListener("click", downloadReceipt);
})();
