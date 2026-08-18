(() => {
  "use strict";

  const section = document.querySelector("#federal-mission");
  if (!section) return;

  const state = { data: null, checks: [], findings: [] };
  const byId = (id) => document.querySelector(`#${id}`);
  const fieldIds = {
    title: "federal-mission-title",
    agency_context: "federal-agency-context",
    problem: "federal-problem",
    affected: "federal-affected",
    baseline: "federal-baseline",
    benefit_metric: "federal-benefit-metric",
    benefit_target: "federal-benefit-target",
    benefit_measurement: "federal-benefit-measurement",
    high_impact: "federal-high-impact",
    impact_rationale: "federal-impact-rationale",
    decision_effects: "federal-decision-effects",
    rights_impacts: "federal-rights-impacts",
    accountable_owner: "federal-accountable-owner",
    human_owner: "federal-human-owner",
    risk_owner: "federal-risk-owner",
    prohibited: "federal-prohibited",
    data_classification: "federal-data-classification",
    contains_pii: "federal-contains-pii",
    synthetic_only: "federal-synthetic-only",
    training_use: "federal-training-use",
    retention: "federal-retention",
    provenance: "federal-provenance",
    vendor: "federal-vendor",
    performance_metrics: "federal-performance-metrics",
    thresholds: "federal-thresholds",
    data_rights: "federal-data-rights",
    portability: "federal-portability",
    pricing: "federal-pricing",
    exit_plan: "federal-exit-plan",
    test_environment: "federal-test-environment",
    independent_reviewer: "federal-independent-reviewer",
    transfer_traps: "federal-transfer-traps",
    review_point: "federal-review-point",
    intervention: "federal-intervention",
    failsafe: "federal-failsafe",
    appeal: "federal-appeal",
    operator_training: "federal-operator-training",
    monitoring_metrics: "federal-monitoring-metrics",
    cadence: "federal-cadence",
    feedback: "federal-feedback",
    incident: "federal-incident",
    cease_use: "federal-cease-use",
    reassessment: "federal-reassessment",
  };
  const fields = Object.fromEntries(Object.entries(fieldIds).map(([name, id]) => [name, byId(id)]));
  const els = {
    begin: byId("federal-begin"),
    loadExample: byId("federal-load-example"),
    form: byId("federal-form"),
    workbench: byId("federal-workbench"),
    controlCount: byId("federal-control-count"),
    sourceCount: byId("federal-source-count"),
    packCount: byId("federal-pack-count"),
    completeCount: byId("federal-complete-count"),
    completeCopy: byId("federal-complete-copy"),
    scoreBar: byId("federal-score-bar"),
    readiness: byId("federal-readiness-list"),
    sources: byId("federal-source-list"),
    downloadPack: byId("federal-download-pack"),
    downloadProfile: byId("federal-download-profile"),
    exportStatus: byId("federal-export-status"),
  };

  function text(value) { return String(value || "").trim(); }
  function splitList(value) { return [...new Set(String(value || "").split(/[\n,]/).map((item) => item.trim()).filter(Boolean))]; }
  function slugify(value) {
    return text(value).toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 64) || "federal-mission-draft";
  }
  function value(name) { return fields[name]?.type === "checkbox" ? fields[name].checked : text(fields[name]?.value); }
  function list(name) { return splitList(value(name)); }
  function fill(name, input) {
    if (!fields[name]) return;
    if (fields[name].type === "checkbox") fields[name].checked = Boolean(input);
    else fields[name].value = Array.isArray(input) ? input.join("\n") : (input ?? "");
  }
  function isoDate(valueToCheck) { return /^\d{4}-\d{2}-\d{2}$/.test(String(valueToCheck || "")); }

  function sensitiveFindings() {
    const corpus = Object.keys(fields).filter((name) => !["contains_pii", "synthetic_only", "vendor"].includes(name))
      .map((name) => `${name}: ${value(name)}`).join("\n");
    const patterns = [
      ["possible API or access key", /\b(?:sk-[a-z0-9_-]{12,}|ghp_[a-z0-9]{12,}|github_pat_[a-z0-9_]{12,}|AKIA[A-Z0-9]{12,}|AIza[a-zA-Z0-9_-]{12,})\b/i],
      ["possible password, token, or credential", /\b(?:password|passwd|access[_ -]?token|api[_ -]?key|client[_ -]?secret)\s*[:=]\s*[^\s,;]{6,}/i],
      ["possible Social Security number", /\b\d{3}-\d{2}-\d{4}\b/],
      ["possible email address", /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i],
      ["possible telephone number", /\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b/],
      ["possible payment-card number", /\b(?:\d[ -]*?){13,19}\b/],
    ];
    return patterns.filter(([, pattern]) => pattern.test(corpus)).map(([label]) => label);
  }

  function validate() {
    state.findings = sensitiveFindings();
    const checks = [
      { id: "identity", label: "Mission, context, and affected groups are explicit", valid: value("title").length >= 6 && list("affected").length > 0 },
      { id: "problem", label: "Problem and current baseline describe the operational need", valid: value("problem").length >= 40 && value("baseline").length >= 20 },
      { id: "benefit", label: "Expected benefit has a metric, target, and measurement", valid: value("benefit_metric").length >= 4 && value("benefit_target").length >= 4 && value("benefit_measurement").length >= 20 },
      { id: "impact", label: "High-impact rationale, decision effects, and rights or safety impacts are recorded", valid: value("impact_rationale").length >= 30 && list("decision_effects").length > 0 && list("rights_impacts").length > 0 },
      { id: "authority", label: "Accountable, human-decision, risk, and prohibited-action owners are bounded", valid: value("accountable_owner").length >= 6 && value("human_owner").length >= 8 && value("risk_owner").length >= 8 && list("prohibited").length > 0 },
      { id: "data", label: "Training use, retention, provenance, and data classification are explicit", valid: value("training_use").length >= 20 && value("retention").length >= 15 && list("provenance").length > 0 },
      { id: "acquisition", label: "Performance, data rights, portability, pricing, and exit are specified", valid: list("performance_metrics").length > 0 && value("data_rights").length >= 25 && value("portability").length >= 15 && value("pricing").length >= 15 && value("exit_plan").length >= 20 },
      { id: "testing", label: "Intended environment and independent reviewer are named", valid: value("test_environment").length >= 30 && value("independent_reviewer").length >= 8 },
      { id: "thresholds", label: "Acceptance thresholds and transfer traps are testable", valid: list("thresholds").length > 0 && list("transfer_traps").length > 0 },
      { id: "oversight", label: "Human review, intervention, failsafe, remedy, and training are usable", valid: value("review_point").length >= 15 && value("intervention").length >= 15 && value("failsafe").length >= 15 && value("appeal").length >= 15 && value("operator_training").length >= 15 },
      { id: "monitoring", label: "Monitoring, feedback, incident, cease-use, and reassessment paths are explicit", valid: list("monitoring_metrics").length > 0 && value("cadence").length >= 5 && value("feedback").length >= 10 && value("incident").length >= 20 && value("cease_use").length >= 20 && value("reassessment").length >= 20 },
      { id: "privacy", label: "Local sensitive-data scan is clear and public-site data is suitable", valid: state.findings.length === 0 && value("synthetic_only") === true && value("data_classification") === "public" && value("contains_pii") === false },
    ];
    state.checks = checks;
    return checks;
  }

  function check(id) { return state.checks.find((item) => item.id === id)?.valid || false; }
  function controlCategory(controlId) {
    if (/IMPACT|MAP/.test(controlId)) return "impact";
    if (/TEST|MEASURE|PERFORMANCE/.test(controlId)) return "testing";
    if (/INDEPENDENT/.test(controlId)) return "testing";
    if (/HUMAN|APPEAL/.test(controlId)) return "oversight";
    if (/MONITOR|MANAGE/.test(controlId)) return "monitoring";
    if (/DATA-RIGHTS|PORTABILITY|PRICING|CROSS-FUNCTION/.test(controlId)) return "acquisition";
    if (/GOVERN/.test(controlId)) return "authority";
    if (/LESSONS/.test(controlId)) return "monitoring";
    return "problem";
  }
  function controlState(control) {
    if (control.framework === "OMB-M-25-22" && !value("vendor")) return "not_applicable";
    return check(controlCategory(control.control_id)) ? "planned" : "gap";
  }

  function ownerFor(control) {
    if (/DATA-RIGHTS|PORTABILITY/.test(control.control_id)) return "Acquisition, counsel, privacy, and data owners";
    if (/PRICING/.test(control.control_id)) return "Cost and price analyst";
    if (/TEST|MEASURE|PERFORMANCE|INDEPENDENT/.test(control.control_id)) return value("independent_reviewer") || "Test and evaluation owner";
    if (/HUMAN|APPEAL/.test(control.control_id)) return value("human_owner") || "Accountable human decision owner";
    if (/IMPACT|MAP/.test(control.control_id)) return value("accountable_owner") || "Program and impact-assessment owner";
    if (/MONITOR|MANAGE|LESSONS/.test(control.control_id)) return value("accountable_owner") || "Program monitoring owner";
    return value("accountable_owner") || "Accountable program owner";
  }

  function evidenceFor(controlId) {
    if (/IMPACT/.test(controlId)) return ["02-high-impact-determination.md", "03-impact-assessment.md"];
    if (/TEST|MEASURE|PERFORMANCE|INDEPENDENT/.test(controlId)) return ["04-tev-test-plan.md"];
    if (/HUMAN|APPEAL/.test(controlId)) return ["06-human-oversight-and-appeals.md"];
    if (/DATA-RIGHTS/.test(controlId)) return ["07-data-model-provenance.md", "08-acquisition-acceptance.md"];
    if (/PORTABILITY|PRICING|CROSS-FUNCTION/.test(controlId)) return ["08-acquisition-acceptance.md"];
    if (/MONITOR|MANAGE/.test(controlId)) return ["09-monitoring-notice-and-cease-use.md"];
    if (/LESSONS/.test(controlId)) return ["README.md", "05-risk-register.md"];
    return ["federal-profile.json"];
  }

  function profile() {
    const controls = state.data.controls.map((control) => {
      const status = controlState(control);
      return {
        control_id: control.control_id,
        framework: control.framework,
        title: control.title,
        applicability: status === "not_applicable" ? "not_applicable" : control.default_applicability,
        status,
        owner: ownerFor(control),
        evidence_refs: status === "gap" ? [] : evidenceFor(control.control_id),
        source_ids: control.source_ids,
      };
    });
    return {
      profile_version: state.data.profile_version,
      profile_id: slugify(value("title")),
      created_at: new Date().toISOString(),
      status: "draft",
      mission: {
        title: value("title"), agency_context: value("agency_context"), problem: value("problem"),
        affected_groups: list("affected"), baseline: value("baseline"),
        expected_benefits: [{ metric: value("benefit_metric"), target: value("benefit_target"), measurement: value("benefit_measurement") }],
      },
      impact: {
        high_impact_determination: value("high_impact"), rationale: value("impact_rationale"),
        decision_effects: list("decision_effects"), rights_safety_impacts: list("rights_impacts"),
      },
      authority: {
        accountable_owner: value("accountable_owner"), human_decision_owner: value("human_owner"),
        risk_acceptance_owner: value("risk_owner"), prohibited_agent_actions: list("prohibited"),
      },
      data: {
        classification: value("data_classification"), contains_pii: value("contains_pii"), synthetic_or_public_only: value("synthetic_only"),
        training_use: value("training_use"), retention: value("retention"), provenance: list("provenance"),
      },
      acquisition: {
        vendor_involved: value("vendor"), performance_metrics: list("performance_metrics"), data_rights: value("data_rights"),
        portability: value("portability"), pricing: value("pricing"), exit_plan: value("exit_plan"),
      },
      testing: {
        intended_environment: value("test_environment"), minimum_scenarios: 32, minimum_repeats: 3,
        acceptance_thresholds: list("thresholds"), independent_reviewer: value("independent_reviewer"), transfer_traps: list("transfer_traps"),
      },
      oversight: {
        review_point: value("review_point"), intervention: value("intervention"), failsafe: value("failsafe"),
        appeal_or_remedy: value("appeal"), operator_training: value("operator_training"),
      },
      monitoring: {
        metrics: list("monitoring_metrics"), cadence: value("cadence"), feedback_channel: value("feedback"),
        incident_route: value("incident"), cease_use_trigger: value("cease_use"), reassessment_trigger: value("reassessment"),
      },
      controls,
      sources: state.data.sources,
      artifacts: state.data.pack_files.filter((name) => name !== "manifest.json").map((name) => ({
        artifact_id: slugify(name.replace(/\.[^.]+$/, "")), path: name, status: "planned", sha256: null,
      })),
      disclaimers: [
        "This independent open-source profile is not an official United States Government standard or endorsement.",
        "The profile is not a certification, FedRAMP authorization, FISMA determination, Authority to Operate, source-selection decision, or legal conclusion.",
        "Accountable officials must verify current sources, applicability, agency procedures, evidence quality, and every protected decision.",
      ],
    };
  }

  function bullet(items) { return (Array.isArray(items) ? items : [items]).filter(Boolean).map((item) => `- ${item}`).join("\n") || "- Not yet documented"; }
  function front(data, title) {
    return `# ${title}\n\nProfile: \`${data.profile_id}\` · Version: \`${data.profile_version}\` · Status: \`${data.status}\`\n\n> Draft evidence aid. Not an official government standard, certification, authorization, acquisition decision, or legal conclusion.\n\n`;
  }
  function packFiles(data) {
    const mission = data.mission, impact = data.impact, authority = data.authority, record = data.data;
    const acquisition = data.acquisition, testing = data.testing, oversight = data.oversight, monitoring = data.monitoring;
    const counts = { evidenced: 0, planned: 0, gap: 0, not_applicable: 0 };
    data.controls.forEach((control) => { counts[control.status] += 1; });
    const files = {};
    files["README.md"] = front(data, `Assurance pack — ${mission.title}`) + `## Mission\n\n${mission.problem}\n\n## Evidence state\n\n- ${counts.evidenced} evidenced\n- ${counts.planned} planned\n- ${counts.gap} visible gaps\n- ${counts.not_applicable} not applicable\n\nNo aggregate compliance score is produced. Inspect every required control, source, and artifact.\n\n## Contents\n\n${bullet(state.data.pack_files.slice(1, -1))}\n`;
    files["federal-profile.json"] = JSON.stringify(data, null, 2) + "\n";
    files["01-use-case-inventory.md"] = front(data, "01 — AI use-case inventory draft") + `## Mission title\n\n${mission.title}\n\n## Agency context\n\n\`${mission.agency_context}\`\n\n## Problem\n\n${mission.problem}\n\n## Affected groups\n\n${bullet(mission.affected_groups)}\n\n## Current baseline\n\n${mission.baseline}\n\n## Expected benefits and measures\n\n${mission.expected_benefits.map((item) => `- **${item.metric}** — target: ${item.target}; measure: ${item.measurement}`).join("\n")}\n`;
    files["02-high-impact-determination.md"] = front(data, "02 — High-impact AI determination draft") + `## Determination\n\n\`${impact.high_impact_determination}\`\n\n## Rationale\n\n${impact.rationale}\n\n## Decision effects\n\n${bullet(impact.decision_effects)}\n\n## Rights and safety impacts\n\n${bullet(impact.rights_safety_impacts)}\n`;
    files["03-impact-assessment.md"] = front(data, "03 — AI impact assessment draft") + `## Intended benefit\n\n${bullet(mission.expected_benefits.map((item) => `${item.metric}: ${item.target}`))}\n\n## Affected groups\n\n${bullet(mission.affected_groups)}\n\n## Rights and safety\n\n${bullet(impact.rights_safety_impacts)}\n\n## Accountable owner\n\n${authority.accountable_owner}\n\n## Reassessment trigger\n\n${monitoring.reassessment_trigger}\n`;
    files["04-tev-test-plan.md"] = front(data, "04 — Test, evaluation, verification, and validation plan") + `## Intended environment\n\n${testing.intended_environment}\n\n## Minimum design\n\n- Scenarios: ${testing.minimum_scenarios}\n- Repeats: ${testing.minimum_repeats}\n- Independent reviewer: ${testing.independent_reviewer}\n\n## Acceptance thresholds\n\n${bullet(testing.acceptance_thresholds)}\n\n## Transfer traps\n\n${bullet(testing.transfer_traps)}\n`;
    files["05-risk-register.md"] = front(data, "05 — Open risk and evidence register") + `| Control | Framework | State | Owner | Evidence |\n|---|---|---|---|---|\n${data.controls.map((item) => `| \`${item.control_id}\` | ${item.framework} | **${item.status}** | ${item.owner} | ${item.evidence_refs.join(", ") || "none"} |`).join("\n")}\n`;
    files["06-human-oversight-and-appeals.md"] = front(data, "06 — Human oversight, failsafe, and remedy plan") + `## Human decision owner\n\n${authority.human_decision_owner}\n\n## Review point\n\n${oversight.review_point}\n\n## Intervention\n\n${oversight.intervention}\n\n## Failsafe\n\n${oversight.failsafe}\n\n## Appeal or remedy\n\n${oversight.appeal_or_remedy}\n\n## Operator training\n\n${oversight.operator_training}\n\n## Prohibited agent actions\n\n${bullet(authority.prohibited_agent_actions)}\n`;
    files["07-data-model-provenance.md"] = front(data, "07 — Data and model provenance card") + `## Classification\n\n\`${record.classification}\`\n\n- Contains PII: \`${record.contains_pii}\`\n- Synthetic or public only: \`${record.synthetic_or_public_only}\`\n\n## Training use\n\n${record.training_use}\n\n## Retention\n\n${record.retention}\n\n## Provenance\n\n${bullet(record.provenance)}\n`;
    files["08-acquisition-acceptance.md"] = front(data, "08 — Acquisition performance and acceptance plan") + `- Vendor involved: \`${acquisition.vendor_involved}\`\n\n## Performance metrics\n\n${bullet(acquisition.performance_metrics)}\n\n## Government data and intellectual-property rights\n\n${acquisition.data_rights}\n\n## Portability\n\n${acquisition.portability}\n\n## Pricing and lifecycle costs\n\n${acquisition.pricing}\n\n## Exit\n\n${acquisition.exit_plan}\n`;
    files["09-monitoring-notice-and-cease-use.md"] = front(data, "09 — Monitoring, public feedback, incident, and cease-use plan") + `## Metrics\n\n${bullet(monitoring.metrics)}\n\n## Cadence\n\n${monitoring.cadence}\n\n## Plain-language purpose\n\n${mission.problem}\n\n## Affected groups\n\n${bullet(mission.affected_groups)}\n\n## Feedback channel\n\n${monitoring.feedback_channel}\n\n## Human review and remedy\n\n${oversight.appeal_or_remedy}\n\n## Incident route\n\n${monitoring.incident_route}\n\n## Cease-use trigger\n\n${monitoring.cease_use_trigger}\n\n## Reassessment trigger\n\n${monitoring.reassessment_trigger}\n\nPublication remains an agency decision. Remove procurement-sensitive, controlled, classified, and personally identifiable information before publication.\n`;
    return files;
  }

  async function digest(contents) {
    const bytes = new TextEncoder().encode(contents);
    const hash = await crypto.subtle.digest("SHA-256", bytes);
    return { sha256: [...new Uint8Array(hash)].map((byte) => byte.toString(16).padStart(2, "0")).join(""), bytes: bytes.length };
  }
  async function addManifest(data, files) {
    const rows = [];
    for (const name of Object.keys(files).sort()) rows.push({ path: name, ...(await digest(files[name])) });
    files["manifest.json"] = JSON.stringify({
      manifest_version: "aau-federal-pack-manifest/0.1", profile_id: data.profile_id,
      created_at: data.created_at, hash_algorithm: "sha256", files: rows,
      claims: { byte_integrity_only: true, authorship_proved: false, independent_reproduction_proved: false, government_approval_proved: false, compliance_proved: false },
    }, null, 2) + "\n";
    return files;
  }
  function download(name, contents, type) {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([contents], { type }));
    link.download = name;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 250);
  }

  function loadExample() {
    const data = state.data.example;
    fill("title", data.mission.title); fill("agency_context", data.mission.agency_context); fill("problem", data.mission.problem);
    fill("affected", data.mission.affected_groups); fill("baseline", data.mission.baseline);
    fill("benefit_metric", data.mission.expected_benefits[0].metric); fill("benefit_target", data.mission.expected_benefits[0].target); fill("benefit_measurement", data.mission.expected_benefits[0].measurement);
    fill("high_impact", data.impact.high_impact_determination); fill("impact_rationale", data.impact.rationale); fill("decision_effects", data.impact.decision_effects); fill("rights_impacts", data.impact.rights_safety_impacts);
    fill("accountable_owner", data.authority.accountable_owner); fill("human_owner", data.authority.human_decision_owner); fill("risk_owner", data.authority.risk_acceptance_owner); fill("prohibited", data.authority.prohibited_agent_actions);
    fill("data_classification", data.data.classification); fill("contains_pii", data.data.contains_pii); fill("synthetic_only", data.data.synthetic_or_public_only); fill("training_use", data.data.training_use); fill("retention", data.data.retention); fill("provenance", data.data.provenance);
    fill("vendor", data.acquisition.vendor_involved); fill("performance_metrics", data.acquisition.performance_metrics); fill("data_rights", data.acquisition.data_rights); fill("portability", data.acquisition.portability); fill("pricing", data.acquisition.pricing); fill("exit_plan", data.acquisition.exit_plan);
    fill("test_environment", data.testing.intended_environment); fill("thresholds", data.testing.acceptance_thresholds); fill("independent_reviewer", data.testing.independent_reviewer); fill("transfer_traps", data.testing.transfer_traps);
    fill("review_point", data.oversight.review_point); fill("intervention", data.oversight.intervention); fill("failsafe", data.oversight.failsafe); fill("appeal", data.oversight.appeal_or_remedy); fill("operator_training", data.oversight.operator_training);
    fill("monitoring_metrics", data.monitoring.metrics); fill("cadence", data.monitoring.cadence); fill("feedback", data.monitoring.feedback_channel); fill("incident", data.monitoring.incident_route); fill("cease_use", data.monitoring.cease_use_trigger); fill("reassessment", data.monitoring.reassessment_trigger);
    update();
    els.workbench.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  }

  function renderControls() {
    const fragments = state.data.controls.map((control) => {
      const card = document.createElement("div");
      const status = controlState(control);
      card.className = `federal-control ${status === "gap" ? "is-gap" : ""}`;
      const marker = document.createElement("span"); marker.textContent = status.replace("_", " ");
      const copy = document.createElement("div");
      const title = document.createElement("b"); title.textContent = control.title;
      const detail = document.createElement("small"); detail.textContent = `${control.control_id} · ${control.framework}`;
      copy.append(title, detail); card.append(marker, copy); return card;
    });
    els.readiness.replaceChildren(...fragments);
  }

  function renderSources() {
    const today = new Date().toISOString().slice(0, 10);
    els.sources.replaceChildren(...state.data.sources.map((source) => {
      const row = document.createElement("div");
      const due = isoDate(source.review_due) && source.review_due < today;
      row.className = `federal-source ${due ? "is-due" : ""}`;
      const copy = document.createElement("div");
      const link = document.createElement("a"); link.href = source.url; link.target = "_blank"; link.rel = "noopener"; link.textContent = source.title;
      const detail = document.createElement("small"); detail.textContent = `${source.authority} · verified ${source.last_verified} · review ${source.review_due}`;
      const status = document.createElement("span"); status.textContent = due ? "REVIEW DUE" : "DATED";
      copy.append(link, detail); row.append(copy, status); return row;
    }));
  }

  function update() {
    const checks = validate();
    const complete = checks.filter((item) => item.valid).length;
    const ready = complete === checks.length;
    els.completeCount.textContent = complete;
    els.scoreBar.style.width = `${Math.round(100 * complete / checks.length)}%`;
    const next = checks.find((item) => !item.valid);
    els.completeCopy.textContent = ready ? "Profile fields are structurally complete. Inspect every generated control and artifact before use." : `Next unresolved gate: ${next.label}.`;
    renderControls();
    els.downloadPack.disabled = !ready;
    els.downloadProfile.disabled = !ready;
    els.exportStatus.textContent = state.findings.length
      ? `Export blocked by local scan: ${state.findings.join(", ")}. Remove sensitive values and use synthetic or public information.`
      : ready
        ? "Ready to export. Controls remain planned or not applicable until accountable reviewers inspect real evidence."
        : `${complete}/${checks.length} structural gates complete. Missing fields remain visible; no score claims compliance.`;
  }

  async function init() {
    try {
      const response = await fetch("federal-mission-data.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`data request failed (${response.status})`);
      state.data = await response.json();
      els.controlCount.textContent = state.data.controls.length;
      els.sourceCount.textContent = state.data.sources.length;
      els.packCount.textContent = state.data.pack_files.length;
      renderSources();
      update();
    } catch (error) {
      els.exportStatus.textContent = `Federal Mission Studio could not load its source-bound contract: ${error.message}`;
      els.loadExample.disabled = true;
    }
  }

  els.begin.addEventListener("click", () => els.workbench.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" }));
  els.loadExample.addEventListener("click", loadExample);
  els.form.addEventListener("input", update);
  els.form.addEventListener("change", update);
  els.downloadProfile.addEventListener("click", () => download(`${slugify(value("title"))}-federal-profile.json`, JSON.stringify(profile(), null, 2) + "\n", "application/json"));
  els.downloadPack.addEventListener("click", async () => {
    els.downloadPack.disabled = true;
    els.exportStatus.textContent = "Hashing eleven artifacts and assembling the local ZIP…";
    try {
      const data = profile();
      const files = await addManifest(data, packFiles(data));
      const archive = globalThis.AAUBoundaryZip.archive(files);
      download(`${data.profile_id}-assurance-pack.zip`, archive, "application/zip");
      els.exportStatus.textContent = "Downloaded 12 files. SHA-256 proves byte integrity only—not authorship, compliance, certification, or approval.";
    } catch (error) {
      els.exportStatus.textContent = `Pack export failed: ${error.message}`;
    } finally {
      els.downloadPack.disabled = state.checks.some((item) => !item.valid);
    }
  });

  init();
})();
