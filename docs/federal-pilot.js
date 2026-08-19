(() => {
  "use strict";

  const section = document.querySelector("#federal-pilot");
  if (!section) return;

  const byId = (id) => document.querySelector(`#${id}`);
  const JSON_LIMITS = { bytes: 2_000_000, depth: 32, nodes: 50_000, stringLength: 256_000 };
  const state = { data: null, selected: null, local: { agency: null, vendor: null, tests: null } };
  const els = {
    open: byId("pilot-open-desk"),
    desk: byId("pilot-desk"),
    cards: byId("pilot-example-cards"),
    roleTabs: [...document.querySelectorAll("[data-pilot-role]")],
    rolePanels: [...document.querySelectorAll("[data-pilot-role-panel]")],
    roleStep: byId("pilot-role-step"),
    roleTitle: byId("pilot-role-title"),
    roleCopy: byId("pilot-role-copy"),
    requirements: byId("pilot-requirements"),
    tests: byId("pilot-tests"),
    title: byId("pilot-selected-title"),
    pilotId: byId("pilot-selected-id"),
    tested: byId("pilot-tested-count"),
    exact: byId("pilot-exact-count"),
    gaps: byId("pilot-gap-count"),
    authority: byId("pilot-authority-count"),
    status: byId("pilot-local-status"),
    download: byId("pilot-download-assessment"),
    reset: byId("pilot-reset-local"),
    prompts: byId("pilot-review-prompts"),
    pilotCount: byId("pilot-reference-count"),
    gateCount: byId("pilot-gate-total"),
    caseCount: byId("pilot-case-total"),
    visibleCount: byId("pilot-visible-total"),
  };

  const roles = {
    agency: {
      step: "01 / AGENCY",
      title: "Publish the outcome and the stop line.",
      copy: "Define the mission, intended environment, measurable gates, protected decisions, allowed data, pricing scenarios, exit, and monitoring before evaluating a response.",
    },
    responder: {
      step: "02 / RESPONDER",
      title: "Bind every claim to evidence and a limitation.",
      copy: "Answer every requirement. Declare unsupported and partial capabilities honestly. Link artifacts, disclose limits, submit exact test outputs, and make price and exit assumptions inspectable.",
    },
    reviewer: {
      step: "03 / REVIEWER",
      title: "Recompute the chain. Keep the decision human.",
      copy: "Inspect claim → evidence → test state, exact-field failures, critical authority gates, commercial terms, and lessons. This desk never ranks or selects a responder.",
    },
  };

  function text(value) { return String(value ?? "").trim(); }
  function safeArray(value) { return Array.isArray(value) ? value : []; }
  function escapeSlug(value) {
    return text(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 72) || "federal-pilot";
  }

  function enforceJsonLimits(value) {
    const stack = [[value, 1]];
    let nodes = 0;
    while (stack.length) {
      const [item, depth] = stack.pop();
      nodes += 1;
      if (nodes > JSON_LIMITS.nodes) throw new Error(`JSON exceeds the ${JSON_LIMITS.nodes.toLocaleString()}-node local limit.`);
      if (depth > JSON_LIMITS.depth) throw new Error(`JSON exceeds the ${JSON_LIMITS.depth}-level nesting limit.`);
      if (typeof item === "string" && item.length > JSON_LIMITS.stringLength) throw new Error("JSON contains an excessively long string.");
      if (Array.isArray(item)) item.forEach((child) => stack.push([child, depth + 1]));
      else if (item && typeof item === "object") Object.entries(item).forEach(([key, child]) => {
        stack.push([key, depth + 1], [child, depth + 1]);
      });
    }
  }

  function sensitiveFindings(value) {
    const raw = JSON.stringify(value);
    const findings = [];
    const patterns = [
      ["email address", /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i],
      ["U.S. Social Security number pattern", /\b\d{3}-\d{2}-\d{4}\b/],
      ["secret or credential label", /\b(api[_ -]?key|secret|password|bearer|private[_ -]?key)\b\s*[:=]/i],
      ["private key block", /BEGIN [A-Z ]*PRIVATE KEY/],
    ];
    patterns.forEach(([label, pattern]) => { if (pattern.test(raw)) findings.push(label); });
    const classification = text(value?.data?.classification || value?.data_classification).toLowerCase();
    if (classification && !["public", "synthetic", "mixed_public_synthetic"].includes(classification)) {
      findings.push(`non-public classification: ${classification}`);
    }
    return [...new Set(findings)];
  }

  function assess(agency, vendor, tests) {
    const problems = [];
    if (agency?.profile_version !== "aau-federal-pilot-agency/0.2") problems.push("agency profile version");
    if (vendor?.profile_version !== "aau-federal-pilot-vendor/0.2") problems.push("responder profile version");
    if (tests?.profile_version !== "aau-federal-pilot-tests/0.2") problems.push("test profile version");
    if (!agency?.pilot_id || agency.pilot_id !== vendor?.pilot_id || agency.pilot_id !== tests?.pilot_id) problems.push("matching pilot IDs");
    const requirements = safeArray(agency?.requirements);
    const claims = new Map(safeArray(vendor?.claims).map((item) => [item.requirement_id, item]));
    const evidence = new Set(safeArray(vendor?.evidence).map((item) => item.evidence_id));
    const results = new Map(safeArray(vendor?.test_results).map((item) => [item.case_id, item]));
    const cases = safeArray(tests?.cases);
    if (requirements.length < 3) problems.push("at least three agency requirements");
    if (claims.size !== requirements.length) problems.push("one unique response per agency requirement");
    if (results.size !== cases.length) problems.push("one unique submitted result per test case");
    if (problems.length) throw new Error(`Missing or inconsistent: ${problems.join(", ")}.`);

    const exactByRequirement = new Map(requirements.map((item) => [item.requirement_id, []]));
    const testRows = cases.map((item) => {
      const result = results.get(item.case_id);
      if (!result) throw new Error(`Missing submitted result for ${item.case_id}.`);
      const checks = {
        outcome: result.observed_outcome === item.oracle?.outcome,
        reasons: new Set(safeArray(result.reason_codes)).size === new Set(safeArray(item.oracle?.reason_codes)).size
          && safeArray(result.reason_codes).every((code) => safeArray(item.oracle?.reason_codes).includes(code)),
        authority: result.authority_owner === item.oracle?.required_authority,
        boundary: result.authority_respected === true,
        evidence: safeArray(result.evidence_refs).length > 0 && safeArray(result.evidence_refs).every((ref) => evidence.has(ref)),
      };
      const exact = Object.values(checks).every(Boolean);
      safeArray(item.linked_requirements).forEach((id) => {
        if (!exactByRequirement.has(id)) throw new Error(`Test references unknown requirement ${id}.`);
        exactByRequirement.get(id).push(exact);
      });
      return {
        case_id: item.case_id,
        dimension: item.dimension,
        critical: item.critical === true,
        exact,
        failed: Object.entries(checks).filter(([, passed]) => !passed).map(([name]) => name),
        failure_shape: item.failure_shape,
      };
    });
    const requirementRows = requirements.map((item) => {
      const claim = claims.get(item.requirement_id);
      if (!claim) throw new Error(`Missing response for ${item.requirement_id}.`);
      const refs = safeArray(claim.evidence_refs).filter((ref) => evidence.has(ref));
      const linked = exactByRequirement.get(item.requirement_id);
      let evidenceState = "tested";
      if (claim.status === "not_supported") evidenceState = "unsupported";
      else if (claim.status === "partial") evidenceState = "partial";
      else if (!refs.length) evidenceState = "claimed_without_evidence";
      else if (!linked.length) evidenceState = "evidenced_not_tested";
      else if (!linked.every(Boolean)) evidenceState = "tested_with_failures";
      return {
        requirement_id: item.requirement_id,
        outcome: item.outcome,
        criticality: item.criticality,
        state: evidenceState,
        evidence_refs: refs,
        exact_test_count: linked.filter(Boolean).length,
        linked_test_count: linked.length,
        limitations: claim.limitations,
      };
    });
    const criticalAuthority = testRows.filter((row) => row.critical && row.failed.includes("boundary"));
    return {
      assessment_version: "aau-federal-pilot-assessment/0.2",
      pilot_id: agency.pilot_id,
      response_id: vendor.response_id,
      title: agency.mission?.title,
      boundary: { vendor_ranked: false, award_recommendation_made: false, certification_made: false, accountable_decision_required: true },
      summary: {
        requirements: requirementRows.length,
        tested_requirements: requirementRows.filter((row) => row.state === "tested").length,
        visible_gaps: requirementRows.filter((row) => row.state !== "tested").length,
        cases: testRows.length,
        exact_cases: testRows.filter((row) => row.exact).length,
        critical_requirement_gaps: requirementRows.filter((row) => row.criticality === "critical" && row.state !== "tested").map((row) => row.requirement_id),
        critical_authority_failures: criticalAuthority.map((row) => row.case_id),
      },
      requirements: requirementRows,
      tests: testRows,
    };
  }

  function stateLabel(value) { return text(value).replaceAll("_", " "); }

  function renderAssessment(exchange) {
    const assessment = assess(exchange.agency, exchange.vendor, exchange.tests);
    state.selected = { ...exchange, assessment };
    els.title.textContent = exchange.agency.mission.title;
    els.pilotId.textContent = exchange.agency.pilot_id;
    els.tested.textContent = `${assessment.summary.tested_requirements}/${assessment.summary.requirements}`;
    els.exact.textContent = `${assessment.summary.exact_cases}/${assessment.summary.cases}`;
    els.gaps.textContent = String(assessment.summary.visible_gaps);
    els.authority.textContent = String(assessment.summary.critical_authority_failures.length);
    els.requirements.replaceChildren(...assessment.requirements.map((row) => {
      const item = document.createElement("article");
      item.className = `pilot-ledger-row is-${row.state}`;
      const head = document.createElement("div");
      const id = document.createElement("b");
      id.textContent = row.requirement_id;
      const badge = document.createElement("span");
      badge.textContent = stateLabel(row.state);
      head.append(id, badge);
      const outcome = document.createElement("p");
      outcome.textContent = row.outcome || exchange.agency.requirements.find((req) => req.requirement_id === row.requirement_id)?.outcome || "";
      const meta = document.createElement("small");
      meta.textContent = `${row.criticality} · ${row.evidence_refs.length} evidence ref${row.evidence_refs.length === 1 ? "" : "s"} · ${row.exact_test_count}/${row.linked_test_count} exact linked tests`;
      const limitation = document.createElement("em");
      limitation.textContent = `LIMITATION / ${row.limitations}`;
      item.append(head, outcome, meta, limitation);
      return item;
    }));
    els.tests.replaceChildren(...assessment.tests.map((row) => {
      const item = document.createElement("article");
      item.className = `pilot-test-row ${row.exact ? "is-exact" : "is-review"}`;
      const marker = document.createElement("span");
      marker.textContent = row.exact ? "✓" : "!";
      const copy = document.createElement("div");
      const title = document.createElement("b");
      title.textContent = `${row.case_id} / ${row.dimension}`;
      const detail = document.createElement("p");
      detail.textContent = row.exact ? "Exact submitted result" : `Review ${row.failed.join(", ")}`;
      const small = document.createElement("small");
      small.textContent = row.failure_shape;
      copy.append(title, detail, small);
      item.append(marker, copy);
      return item;
    }));
    const localFindings = [exchange.agency, exchange.vendor, exchange.tests].flatMap(sensitiveFindings);
    if (localFindings.length) {
      els.status.textContent = `Export blocked by local scan: ${[...new Set(localFindings)].join(", ")}. Keep protected data in an approved environment.`;
      els.status.className = "pilot-local-status is-blocked";
      els.download.disabled = true;
    } else {
      els.status.textContent = "Assessment recomputed locally. Download contains the gap ledger and aggregate test findings—not uploaded source contents.";
      els.status.className = "pilot-local-status is-ready";
      els.download.disabled = false;
    }
  }

  function renderExamples() {
    els.cards.replaceChildren(...state.data.examples.map((example, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "pilot-example-card";
      button.dataset.pilotExample = example.slug;
      const tag = document.createElement("span");
      tag.textContent = `${String(index + 1).padStart(2, "0")} / PUBLIC SYNTHETIC`;
      const title = document.createElement("b");
      title.textContent = example.agency.mission.title;
      const copy = document.createElement("p");
      copy.textContent = example.agency.mission.problem;
      const proof = document.createElement("small");
      proof.textContent = `${example.assessment.summary.requirements} gates · ${example.assessment.summary.cases} cases · ${example.assessment.summary.visible_gaps} visible gap${example.assessment.summary.visible_gaps === 1 ? "" : "s"} →`;
      button.append(tag, title, copy, proof);
      button.addEventListener("click", () => {
        document.querySelectorAll("[data-pilot-example]").forEach((item) => item.classList.toggle("is-active", item === button));
        renderAssessment(example);
        els.desk.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      return button;
    }));
  }

  function renderPrompts() {
    els.prompts.replaceChildren(...state.data.review_prompts.topics.map((topic) => {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      const id = document.createElement("span");
      id.textContent = topic.topic_id;
      const title = document.createElement("b");
      title.textContent = topic.title;
      summary.append(id, title);
      const list = document.createElement("ul");
      topic.questions.forEach((question) => {
        const item = document.createElement("li");
        item.textContent = question;
        list.append(item);
      });
      const sources = document.createElement("small");
      sources.textContent = `SOURCE MAP / ${topic.source_ids.join(" · ")}`;
      details.append(summary, list, sources);
      return details;
    }));
  }

  function setRole(name) {
    const role = roles[name];
    els.roleTabs.forEach((button) => {
      const active = button.dataset.pilotRole === name;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-selected", String(active));
    });
    els.rolePanels.forEach((panel) => panel.hidden = panel.dataset.pilotRolePanel !== name);
    els.roleStep.textContent = role.step;
    els.roleTitle.textContent = role.title;
    els.roleCopy.textContent = role.copy;
  }

  async function readFile(kind, file) {
    if (!file) return;
    if (file.size > JSON_LIMITS.bytes) throw new Error(`${kind} file exceeds the 2 MB local limit.`);
    let value;
    try { value = JSON.parse(await file.text()); }
    catch { throw new Error(`${kind} file is not valid JSON.`); }
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${kind} root must be an object.`);
    enforceJsonLimits(value);
    state.local[kind] = value;
    const ready = Object.values(state.local).every(Boolean);
    els.status.textContent = ready ? "Three local files loaded. Recomputing the exchange…" : `${kind} file loaded locally. Add the other ${Object.values(state.local).filter(Boolean).length === 1 ? "two files" : "file"}.`;
    els.status.className = "pilot-local-status";
    if (ready) renderAssessment({ ...state.local, slug: "local-exchange" });
  }

  function downloadAssessment() {
    if (!state.selected || els.download.disabled) return;
    const payload = {
      ...state.selected.assessment,
      exported_at: new Date().toISOString(),
      privacy: "Aggregate assessment only. Source documents were processed locally and are not embedded.",
      disclaimer: "Not a vendor ranking, award recommendation, certification, compliance finding, or government approval.",
    };
    const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${escapeSlug(payload.pilot_id)}-evidence-assessment.json`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function resetLocal() {
    state.local = { agency: null, vendor: null, tests: null };
    section.querySelectorAll("input[type=file]").forEach((input) => { input.value = ""; });
    const first = state.data.examples[0];
    renderAssessment(first);
    document.querySelectorAll("[data-pilot-example]").forEach((item, index) => item.classList.toggle("is-active", index === 0));
    els.status.textContent = "Local files cleared. The first public synthetic reference pilot is loaded.";
    els.status.className = "pilot-local-status is-ready";
  }

  async function init() {
    try {
      const response = await fetch("federal-pilot-data.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`data request returned ${response.status}`);
      state.data = await response.json();
      const summaries = state.data.examples.map((item) => item.assessment.summary);
      els.pilotCount.textContent = state.data.examples.length;
      els.gateCount.textContent = summaries.reduce((total, item) => total + item.requirements, 0);
      els.caseCount.textContent = summaries.reduce((total, item) => total + item.cases, 0);
      els.visibleCount.textContent = summaries.reduce((total, item) => total + item.visible_gaps, 0);
      renderExamples();
      renderPrompts();
      renderAssessment(state.data.examples[0]);
      document.querySelector("[data-pilot-example]")?.classList.add("is-active");
      setRole("agency");
    } catch (error) {
      els.status.textContent = `Pilot Desk could not initialize: ${error.message}`;
      els.status.className = "pilot-local-status is-blocked";
    }
  }

  els.open?.addEventListener("click", () => els.desk.scrollIntoView({ behavior: "smooth", block: "start" }));
  els.roleTabs.forEach((button) => button.addEventListener("click", () => setRole(button.dataset.pilotRole)));
  section.querySelectorAll("[data-pilot-file]").forEach((input) => input.addEventListener("change", async () => {
    try { await readFile(input.dataset.pilotFile, input.files?.[0]); }
    catch (error) {
      els.status.textContent = error.message;
      els.status.className = "pilot-local-status is-blocked";
      els.download.disabled = true;
    }
  }));
  els.download?.addEventListener("click", downloadAssessment);
  els.reset?.addEventListener("click", resetLocal);
  init();
})();
