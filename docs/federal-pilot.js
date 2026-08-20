(() => {
  "use strict";

  const section = document.querySelector("#federal-pilot");
  if (!section) return;

  const byId = (id) => document.querySelector(`#${id}`);
  const JSON_LIMITS = { bytes: 2_000_000, depth: 32, nodes: 50_000, stringLength: 256_000 };
  const state = {
    data: null,
    selected: null,
    selectedLesson: null,
    local: { agency: null, vendor: null, tests: null },
    localLessonReceipt: null,
  };
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
    lessonCount: byId("lesson-count"),
    lessonStopCount: byId("lesson-stop-count"),
    lessonPolicyCount: byId("lesson-policy-count"),
    lessonPracticeCount: byId("lesson-practice-count"),
    lessonSearch: byId("lesson-search"),
    lessonResultFilter: byId("lesson-result-filter"),
    lessonCategoryFilter: byId("lesson-category-filter"),
    lessonReset: byId("lesson-reset"),
    lessonResults: byId("lesson-results"),
    lessonMatchCount: byId("lesson-match-count"),
    lessonSelectedResult: byId("lesson-selected-result"),
    lessonSelectedReview: byId("lesson-selected-review"),
    lessonSelectedTitle: byId("lesson-selected-title"),
    lessonSelectedSummary: byId("lesson-selected-summary"),
    lessonSelectedDecision: byId("lesson-selected-decision"),
    lessonSelectedMetrics: byId("lesson-selected-metrics"),
    lessonSelectedPractice: byId("lesson-selected-practice"),
    lessonSelectedAction: byId("lesson-selected-action"),
    lessonSelectedContexts: byId("lesson-selected-contexts"),
    lessonSelectedNontransfer: byId("lesson-selected-nontransfer"),
    lessonSelectedSources: byId("lesson-selected-sources"),
    lessonSourceList: byId("lesson-source-list"),
    lessonLocalFile: byId("lesson-local-file"),
    lessonLocalStatus: byId("lesson-local-status"),
    lessonDownloadScan: byId("lesson-download-scan"),
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
      ["telephone number pattern", /(?<!\d)(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}(?!\d)/],
      ["secret or credential label", /\b(api[_ -]?key|secret|password|bearer|private[_ -]?key)\b\s*[:=]/i],
      ["private key block", /BEGIN [A-Z ]*PRIVATE KEY/],
      ["GitHub token pattern", /\bgh[pousr]_[A-Za-z0-9]{20,}\b/],
      ["AWS access-key pattern", /\b(?:AKIA|ASIA)[A-Z0-9]{16}\b/],
      ["bearer-token pattern", /\bBearer\s+[A-Za-z0-9._~+/=-]{16,}/i],
      ["sensitive field name", /"(?:account_number|address|date_of_birth|dob|full_name|home_address|person_name|social_security_number)"\s*:\s*"[^"\s]+/i],
    ];
    patterns.forEach(([label, pattern]) => { if (pattern.test(raw)) findings.push(label); });
    const classification = text(value?.data?.classification || value?.data_classification).toLowerCase();
    if (classification && !["public", "synthetic", "mixed_public_synthetic"].includes(classification)) {
      findings.push(`non-public classification: ${classification}`);
    }
    if (value?.profile_version === "aau-federal-ai-lesson/0.4") {
      const sharing = value?.sharing || {};
      [
        "contains_personally_identifiable_information",
        "contains_procurement_sensitive_information",
        "contains_controlled_unclassified_information",
        "contains_classified_information",
        "contains_secrets_or_credentials",
      ].forEach((field) => { if (sharing[field] !== false) findings.push(`publication attestation: ${field}`); });
      if (sharing.human_review_complete !== true) findings.push("human redaction review is incomplete");
      if (!["public_synthetic", "public_record"].includes(sharing.classification)) findings.push("lesson sharing classification");
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

  function pretty(value) { return text(value).replaceAll("_", " "); }

  function replaceList(element, values) {
    element.replaceChildren(...safeArray(values).map((value) => {
      const item = document.createElement("li");
      item.textContent = value;
      return item;
    }));
  }

  function renderLessonDetail(item) {
    const lesson = item.record;
    state.selectedLesson = item;
    els.lessonSelectedResult.textContent = lesson.outcome.result;
    els.lessonSelectedResult.dataset.result = lesson.outcome.result;
    els.lessonSelectedReview.textContent = `Review by ${lesson.review_due} · ${item.drift.summary.current}/${item.drift.summary.dependencies} sources current`;
    els.lessonSelectedTitle.textContent = lesson.mission.title;
    els.lessonSelectedSummary.textContent = lesson.outcome.summary;
    els.lessonSelectedDecision.textContent = lesson.outcome.human_decision;
    els.lessonSelectedPractice.textContent = lesson.reusable_practice.title;
    els.lessonSelectedAction.textContent = lesson.reusable_practice.action;
    replaceList(els.lessonSelectedContexts, lesson.applicability.contexts);
    replaceList(els.lessonSelectedNontransfer, lesson.applicability.does_not_transfer_to);
    els.lessonSelectedMetrics.replaceChildren(...lesson.outcome.metrics.map((metric) => {
      const card = document.createElement("article");
      card.className = "lesson-metric";
      const id = document.createElement("span");
      id.textContent = metric.metric_id;
      const title = document.createElement("b");
      title.textContent = metric.measure;
      const change = document.createElement("p");
      change.textContent = `${metric.before} → ${metric.after}. ${metric.interpretation}`;
      card.append(id, title, change);
      return card;
    }));
    const sourceMap = new Map(state.data.lesson_exchange.source_ledger.sources.map((source) => [source.source_id, source]));
    els.lessonSelectedSources.replaceChildren(...lesson.policy_dependencies.map((dependency) => {
      const source = sourceMap.get(dependency.source_id);
      const link = document.createElement("a");
      link.href = source?.url || "#";
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = `${dependency.source_id} · ${source?.review_due || "source missing"} ↗`;
      link.title = dependency.dependency;
      return link;
    }));
    document.querySelectorAll("[data-lesson-id]").forEach((card) => {
      const active = card.dataset.lessonId === lesson.lesson_id;
      card.classList.toggle("is-active", active);
      card.setAttribute("aria-pressed", String(active));
    });
  }

  function filteredLessons() {
    const query = text(els.lessonSearch.value).toLowerCase();
    const result = els.lessonResultFilter.value || "all";
    const category = els.lessonCategoryFilter.value || "all";
    return state.data.lesson_exchange.lessons.filter((item) => {
      const lesson = item.record;
      const searchText = [
        lesson.lesson_id,
        lesson.mission.title,
        lesson.mission.archetype,
        lesson.mission.beneficiary,
        lesson.mission.intended_outcome,
        lesson.outcome.result,
        lesson.outcome.summary,
        lesson.outcome.human_decision,
        lesson.challenge.failure_shape,
        ...lesson.challenge.categories,
        lesson.reusable_practice.title,
        lesson.reusable_practice.action,
        ...lesson.applicability.contexts,
        ...lesson.applicability.does_not_transfer_to,
        ...lesson.applicability.prerequisites,
        ...lesson.applicability.limitations,
      ].map(text).join(" ").toLowerCase();
      const matchesQuery = !query || searchText.includes(query);
      const matchesResult = result === "all" || lesson.outcome.result === result;
      const matchesCategory = category === "all" || lesson.challenge.categories.includes(category);
      return matchesQuery && matchesResult && matchesCategory;
    });
  }

  function renderLessons() {
    const matches = filteredLessons();
    els.lessonMatchCount.textContent = `${matches.length} of ${state.data.lesson_exchange.lessons.length} lessons`;
    if (!matches.length) {
      const empty = document.createElement("p");
      empty.className = "lesson-empty";
      empty.textContent = "No lesson matches these filters. Reset the exchange or try a broader failure shape.";
      els.lessonResults.replaceChildren(empty);
      return;
    }
    els.lessonResults.replaceChildren(...matches.map((item) => {
      const lesson = item.record;
      const button = document.createElement("button");
      button.type = "button";
      button.className = `lesson-result-card is-${lesson.outcome.result}`;
      button.dataset.lessonId = lesson.lesson_id;
      button.setAttribute("aria-pressed", "false");
      const outcome = document.createElement("span");
      outcome.textContent = lesson.outcome.result;
      const body = document.createElement("div");
      const title = document.createElement("b");
      title.textContent = lesson.mission.title;
      const summary = document.createElement("p");
      summary.textContent = lesson.challenge.failure_shape;
      const meta = document.createElement("small");
      meta.textContent = `${lesson.challenge.categories.map(pretty).join(" · ")} →`;
      body.append(title, summary, meta);
      button.append(outcome, body);
      button.addEventListener("click", () => renderLessonDetail(item));
      return button;
    }));
    const selectedStillVisible = matches.find((item) => item.record.lesson_id === state.selectedLesson?.record?.lesson_id);
    renderLessonDetail(selectedStillVisible || matches[0]);
  }

  function renderLessonSources() {
    const sources = state.data.lesson_exchange.source_ledger.sources;
    els.lessonSourceList.replaceChildren(...sources.map((source) => {
      const card = document.createElement("article");
      card.className = "lesson-source-card";
      const dates = document.createElement("span");
      dates.textContent = `VERIFIED ${source.last_verified} / REVIEW ${source.review_due}`;
      const title = document.createElement("b");
      title.textContent = source.title;
      const selector = document.createElement("p");
      selector.textContent = source.selector;
      const link = document.createElement("a");
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = `${source.authority} ↗`;
      card.append(dates, title, selector, link);
      return card;
    }));
  }

  function populateLessonFilters() {
    const exchange = state.data.lesson_exchange;
    exchange.taxonomy.results.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = pretty(value);
      els.lessonResultFilter.append(option);
    });
    exchange.taxonomy.challenge_categories.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = pretty(value);
      els.lessonCategoryFilter.append(option);
    });
  }

  async function readLocalLesson(file) {
    if (!file) return;
    if (file.size > JSON_LIMITS.bytes) throw new Error("Lesson file exceeds the 2 MB local limit.");
    let lesson;
    try { lesson = JSON.parse(await file.text()); }
    catch { throw new Error("Lesson file is not valid JSON."); }
    if (!lesson || typeof lesson !== "object" || Array.isArray(lesson)) throw new Error("Lesson root must be an object.");
    enforceJsonLimits(lesson);
    const structural = [];
    if (lesson.profile_version !== "aau-federal-ai-lesson/0.4") structural.push("lesson profile version");
    if (!text(lesson.lesson_id)) structural.push("lesson id");
    if (!text(lesson.pilot_id)) structural.push("pilot id");
    if (!safeArray(lesson.applicability?.does_not_transfer_to).length) structural.push("non-transfer conditions");
    if (lesson.applicability?.transfer_test_required !== true) structural.push("transfer-test requirement");
    if (!safeArray(lesson.policy_dependencies).length) structural.push("policy dependencies");
    if (!safeArray(lesson.disclaimers).length) structural.push("disclaimers");
    const findings = sensitiveFindings(lesson);
    const safe = !structural.length && !findings.length;
    state.localLessonReceipt = {
      scan_version: "aau-browser-publication-preflight/0.4",
      lesson_id: text(lesson.lesson_id) || "unknown-lesson",
      scanned_at: new Date().toISOString(),
      structurally_ready: !structural.length,
      safe_to_package: safe,
      structural_gaps: structural,
      finding_count: findings.length,
      findings,
      boundary: "This narrow local scan is not disclosure authorization, DLP, classification review, legal advice, certification, or government approval.",
    };
    const details = [...structural.map((item) => `missing ${item}`), ...findings];
    els.lessonLocalStatus.textContent = safe
      ? "No narrow scan findings. Authorized human redaction and publication review are still required."
      : `Publication preflight blocked: ${details.join(", ")}.`;
    els.lessonLocalStatus.className = `lesson-local-status ${safe ? "is-ready" : "is-blocked"}`;
    els.lessonDownloadScan.disabled = false;
  }

  function downloadLessonScan() {
    if (!state.localLessonReceipt) return;
    const blob = new Blob([`${JSON.stringify(state.localLessonReceipt, null, 2)}\n`], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${escapeSlug(state.localLessonReceipt.lesson_id)}-publication-scan.json`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
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
      const lessonStats = state.data.lesson_exchange.stats;
      els.lessonCount.textContent = lessonStats.lessons;
      els.lessonStopCount.textContent = lessonStats.stopped;
      els.lessonPolicyCount.textContent = lessonStats.policy_dependencies;
      els.lessonPracticeCount.textContent = lessonStats.bounded_practices;
      renderExamples();
      renderPrompts();
      populateLessonFilters();
      renderLessons();
      renderLessonSources();
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
  els.lessonSearch?.addEventListener("input", renderLessons);
  els.lessonResultFilter?.addEventListener("change", renderLessons);
  els.lessonCategoryFilter?.addEventListener("change", renderLessons);
  els.lessonReset?.addEventListener("click", () => {
    els.lessonSearch.value = "";
    els.lessonResultFilter.value = "all";
    els.lessonCategoryFilter.value = "all";
    renderLessons();
  });
  els.lessonLocalFile?.addEventListener("change", async () => {
    try { await readLocalLesson(els.lessonLocalFile.files?.[0]); }
    catch (error) {
      state.localLessonReceipt = null;
      els.lessonLocalStatus.textContent = error.message;
      els.lessonLocalStatus.className = "lesson-local-status is-blocked";
      els.lessonDownloadScan.disabled = true;
    }
  });
  els.lessonDownloadScan?.addEventListener("click", downloadLessonScan);
  init();
})();
