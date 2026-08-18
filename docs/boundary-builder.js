(() => {
  "use strict";

  const STORAGE_KEY = "aau-boundary-builder-draft-v1";
  const REPO_URL = "https://github.com/immu4989/awesome-agentic-usecases";
  const ACTIONS = ["trust", "verify", "block"];
  const state = { data: null, step: 1, draft: {}, validations: [] };

  const els = {
    section: document.querySelector("#boundary-builder"),
    begin: document.querySelector("#builder-begin"),
    loadExample: document.querySelector("#builder-load-example"),
    contractCount: document.querySelector("#builder-contract-count"),
    gateCount: document.querySelector("#builder-gate-count"),
    fileCount: document.querySelector("#builder-file-count"),
    workbench: document.querySelector("#builder-workbench"),
    reset: document.querySelector("#builder-reset"),
    saveState: document.querySelector("#builder-save-state"),
    steps: document.querySelector("#builder-steps"),
    form: document.querySelector("#builder-form"),
    contractOptions: document.querySelector("#builder-contract-options"),
    contractNote: document.querySelector("#builder-contract-note"),
    descriptionCount: document.querySelector("#builder-description-count"),
    privacyScan: document.querySelector("#builder-privacy-scan"),
    privacyResult: document.querySelector("#builder-privacy-result"),
    previous: document.querySelector("#builder-previous"),
    next: document.querySelector("#builder-next"),
    currentStep: document.querySelector("#builder-current-step"),
    validCount: document.querySelector("#builder-valid-count"),
    validationList: document.querySelector("#builder-validation-list"),
    releaseGate: document.querySelector(".builder-release-gate"),
    releaseCopy: document.querySelector("#builder-release-copy"),
    downloadBundle: document.querySelector("#builder-download-bundle"),
    downloadBrief: document.querySelector("#builder-download-brief"),
    downloadPair: document.querySelector("#builder-download-pair"),
    downloadCard: document.querySelector("#builder-download-card"),
    copyCommand: document.querySelector("#builder-copy-command"),
    proposalLink: document.querySelector("#builder-proposal-link"),
    actionStatus: document.querySelector("#builder-action-status"),
    previewContract: document.querySelector("#builder-preview-contract"),
    previewTitle: document.querySelector("#builder-preview-title"),
    previewDescription: document.querySelector("#builder-preview-description"),
    previewBefore: document.querySelector("#builder-preview-before"),
    previewAfter: document.querySelector("#builder-preview-after"),
    previewBaselineAction: document.querySelector("#builder-preview-baseline-action"),
    previewChangedAction: document.querySelector("#builder-preview-changed-action"),
    previewWhy: document.querySelector("#builder-preview-why"),
    previewAuthority: document.querySelector("#builder-preview-authority"),
    previewValid: document.querySelector("#builder-preview-valid"),
    previewBar: document.querySelector("#builder-preview-bar"),
    previewStatus: document.querySelector("#builder-preview-status"),
  };

  if (!els.section) return;

  const fields = {
    industry: document.querySelector("#builder-industry"),
    title: document.querySelector("#builder-workflow-title"),
    description: document.querySelector("#builder-description"),
    authority_owner: document.querySelector("#builder-authority"),
    protected_action: document.querySelector("#builder-protected-action"),
    domain_reviewer: document.querySelector("#builder-reviewer"),
    boundary_label: document.querySelector("#builder-boundary-label"),
    before: document.querySelector("#builder-before"),
    after: document.querySelector("#builder-after"),
    why: document.querySelector("#builder-why"),
    stake: document.querySelector("#builder-stake"),
    baseline_evidence: document.querySelector("#builder-baseline-evidence"),
    changed_evidence: document.querySelector("#builder-changed-evidence"),
    changed_missing: document.querySelector("#builder-changed-missing"),
    source_one: document.querySelector("#builder-source-one"),
    source_two: document.querySelector("#builder-source-two"),
  };

  function text(value) {
    return String(value || "").trim();
  }

  function slugify(value) {
    return text(value).toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 64) || "my-boundary";
  }

  function splitList(value) {
    return [...new Set(String(value || "").split(/[\n,]/).map((item) => item.trim()).filter(Boolean))];
  }

  function actionLabel(value) {
    return value ? value.charAt(0).toUpperCase() + value.slice(1) : "—";
  }

  function selectedValue(name) {
    return document.querySelector(`input[name="${name}"]:checked`)?.value || "";
  }

  function currentContract() {
    return state.data?.contracts.find((contract) => contract.id === state.draft.contract_id) || null;
  }

  function readDraft() {
    const draft = {};
    for (const [name, input] of Object.entries(fields)) draft[name] = text(input.value);
    draft.contract_id = selectedValue("contract_id");
    draft.baseline_review = selectedValue("baseline_review");
    draft.changed_review = selectedValue("changed_review");
    draft.baseline_evidence = splitList(draft.baseline_evidence);
    draft.changed_evidence = splitList(draft.changed_evidence);
    draft.changed_missing = splitList(draft.changed_missing);
    draft.sources = [draft.source_one, draft.source_two].filter(Boolean);
    return draft;
  }

  function fillDraft(draft) {
    for (const [name, input] of Object.entries(fields)) {
      const value = draft[name];
      input.value = Array.isArray(value) ? value.join("\n") : (value || "");
    }
    for (const name of ["contract_id", "baseline_review", "changed_review"]) {
      for (const input of document.querySelectorAll(`input[name="${name}"]`)) input.checked = input.value === draft[name];
    }
    state.draft = readDraft();
  }

  function hasMeaningfulDraft() {
    const draft = readDraft();
    return Boolean(draft.title || draft.description || draft.before || draft.after || draft.source_one);
  }

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.draft));
      els.saveState.textContent = "Saved locally";
      els.saveState.classList.add("is-saved");
    } catch {
      els.saveState.textContent = "Browser storage unavailable";
      els.saveState.classList.remove("is-saved");
    }
  }

  function restore() {
    try {
      const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      return value && typeof value === "object" ? value : null;
    } catch {
      return null;
    }
  }

  function isHttps(value) {
    try { return new URL(value).protocol === "https:"; } catch { return false; }
  }

  function sensitiveFindings(draft) {
    const corpus = Object.entries(draft)
      .filter(([key]) => key !== "contract_id")
      .flatMap(([key, value]) => Array.isArray(value) ? value.map((item) => `${key}: ${item}`) : [`${key}: ${value}`])
      .join("\n");
    const patterns = [
      ["possible API or access key", /\b(?:sk-[a-z0-9_-]{12,}|ghp_[a-z0-9]{12,}|github_pat_[a-z0-9_]{12,}|AKIA[A-Z0-9]{12,}|AIza[a-zA-Z0-9_-]{12,})\b/i],
      ["possible password, token, or credential value", /\b(?:password|passwd|access[_ -]?token|api[_ -]?key|client[_ -]?secret)\s*[:=]\s*[^\s,;]{6,}/i],
      ["possible US Social Security number", /\b\d{3}-\d{2}-\d{4}\b/],
      ["possible email address", /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i],
      ["possible telephone number", /\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b/],
      ["possible payment-card number", /\b(?:\d[ -]*?){13,19}\b/],
    ];
    return patterns.filter(([, pattern]) => pattern.test(corpus)).map(([label]) => label);
  }

  function validate(draft) {
    const findings = sensitiveFindings(draft);
    const actionsValid = ACTIONS.includes(draft.baseline_review) && ACTIONS.includes(draft.changed_review);
    return [
      { id: "identity", label: "Industry and boundary title are named", valid: draft.industry.length >= 3 && draft.title.length >= 6 },
      { id: "workflow", label: "Workflow description states the operational work", valid: draft.description.length >= 40 },
      { id: "contract", label: "A repository-backed contract shape is selected", valid: Boolean(currentContract()) },
      { id: "authority", label: "Accountable authority and domain reviewer are explicit", valid: draft.authority_owner.length >= 8 && draft.domain_reviewer.length >= 8 },
      { id: "protected", label: "The protected action the agent cannot claim is explicit", valid: draft.protected_action.length >= 12 },
      { id: "boundary", label: "Boundary label, before state, and after state are complete", valid: draft.boundary_label.length >= 4 && draft.before.length >= 6 && draft.after.length >= 6 },
      { id: "delta", label: "Before and after describe different semantic states", valid: draft.before.toLowerCase() !== draft.after.toLowerCase() && draft.before.length >= 6 && draft.after.length >= 6 },
      { id: "actions", label: "Both reviewer actions are chosen and they change", valid: actionsValid && draft.baseline_review !== draft.changed_review },
      { id: "causal", label: "The causal reason for the action change is explained", valid: draft.why.length >= 30 },
      { id: "stake", label: "The concrete cost of an incorrect transfer is named", valid: draft.stake.length >= 20 },
      { id: "evidence", label: "Both sides declare an evidence ledger", valid: draft.baseline_evidence.length > 0 && draft.changed_evidence.length > 0 },
      { id: "source-safety", label: "HTTPS source declared and local sensitive-data scan is clear", valid: isHttps(draft.source_one) && (!draft.source_two || isHttps(draft.source_two)) && findings.length === 0 },
    ];
  }

  function stepComplete(step) {
    const ids = {
      1: ["identity", "workflow", "contract", "authority", "protected"],
      2: ["boundary", "delta", "actions", "causal", "stake"],
      3: ["evidence", "source-safety"],
      4: state.validations.map((item) => item.id),
    }[step];
    return ids.every((id) => state.validations.find((item) => item.id === id)?.valid);
  }

  function renderContracts() {
    els.contractOptions.replaceChildren(...state.data.contracts.map((contract) => {
      const label = document.createElement("label");
      label.className = "builder-contract-card";
      const input = document.createElement("input");
      input.type = "radio";
      input.name = "contract_id";
      input.value = contract.id;
      const top = document.createElement("span");
      const name = document.createElement("b");
      name.textContent = contract.name;
      const mode = document.createElement("i");
      mode.textContent = contract.forge_mode;
      top.append(name, mode);
      const summary = document.createElement("p");
      summary.textContent = contract.question;
      const source = document.createElement("small");
      source.textContent = `inherits ${contract.recommended_case.title}`;
      label.append(input, top, summary, source);
      return label;
    }));
  }

  function renderContractState() {
    const contract = currentContract();
    for (const card of els.contractOptions.querySelectorAll(".builder-contract-card")) {
      card.classList.toggle("is-selected", card.querySelector("input").checked);
    }
    if (!contract) {
      els.contractNote.hidden = true;
      return;
    }
    els.contractNote.hidden = false;
    els.contractNote.classList.toggle("is-fallback", contract.forge_mode === "generic-fallback");
    els.contractNote.replaceChildren();
    const lead = document.createElement("b");
    lead.textContent = contract.forge_mode === "contract-aware" ? "Contract-aware Forge path. " : "Generic Forge fallback. ";
    const copy = document.createTextNode(contract.forge_mode === "contract-aware"
      ? "Forge compiles a specialized topology for this contract. The domain rules still require qualified review. "
      : "Forge can create runnable generic infrastructure, but it will not claim this contract has a specialized compiler. ");
    const link = document.createElement("a");
    link.href = contract.source_url;
    link.textContent = "Inspect the source contract ↗";
    els.contractNote.append(lead, copy, link);
  }

  function renderPrivacy() {
    const findings = sensitiveFindings(state.draft);
    els.privacyScan.classList.toggle("is-alert", findings.length > 0);
    els.privacyResult.textContent = findings.length
      ? `Export blocked: ${findings.join("; ")}. Remove the value and use a synthetic label instead.`
      : "No likely credential, email, phone, SSN, or payment-card pattern detected. This is a narrow screen—not a privacy guarantee.";
  }

  function renderPreview() {
    const draft = state.draft;
    const contract = currentContract();
    els.previewContract.textContent = contract ? `${contract.name} / ${contract.forge_mode}` : "Choose a contract";
    els.previewTitle.textContent = draft.title || "Your boundary appears here.";
    els.previewDescription.textContent = draft.description || "Describe the work and the preview will become a portable counterfactual case.";
    els.previewBefore.textContent = draft.before || "Baseline deciding fact";
    els.previewAfter.textContent = draft.after || "Changed deciding fact";
    els.previewBaselineAction.textContent = actionLabel(draft.baseline_review);
    els.previewChangedAction.textContent = actionLabel(draft.changed_review);
    els.previewWhy.textContent = draft.why || "Explain why the required action should move.";
    els.previewAuthority.textContent = draft.authority_owner && draft.protected_action
      ? `${draft.authority_owner} retains: ${draft.protected_action}.`
      : "Name the accountable owner and action.";
    const passed = state.validations.filter((item) => item.valid).length;
    const ready = passed === state.data.validation_gate_count;
    els.previewValid.textContent = passed;
    els.previewBar.style.width = `${(passed / state.data.validation_gate_count) * 100}%`;
    els.previewStatus.textContent = ready ? "Structurally ready · domain review still required" : `${state.data.validation_gate_count - passed} structural gate${state.data.validation_gate_count - passed === 1 ? "" : "s"} remaining`;
  }

  function renderValidation() {
    const passed = state.validations.filter((item) => item.valid).length;
    const ready = passed === state.data.validation_gate_count;
    els.validCount.textContent = passed;
    els.releaseGate.classList.toggle("is-ready", ready);
    els.releaseCopy.textContent = ready
      ? "Structural checks passed. The exported draft remains adaptation_required until qualified domain review and repeated evidence exist."
      : `Complete ${state.data.validation_gate_count - passed} remaining structural gate${state.data.validation_gate_count - passed === 1 ? "" : "s"} to unlock local exports.`;
    els.validationList.replaceChildren(...state.validations.map((validation) => {
      const item = document.createElement("li");
      item.className = validation.valid ? "is-valid" : "";
      item.textContent = validation.label;
      return item;
    }));
    for (const button of [els.downloadBundle, els.downloadBrief, els.downloadPair, els.downloadCard, els.copyCommand]) button.disabled = !ready;
    els.proposalLink.classList.toggle("is-disabled", !ready);
    els.proposalLink.setAttribute("aria-disabled", String(!ready));
  }

  function renderStep() {
    for (const panel of els.form.querySelectorAll("[data-builder-panel]")) panel.hidden = Number(panel.dataset.builderPanel) !== state.step;
    for (const button of els.steps.querySelectorAll("button[data-builder-step]")) {
      const step = Number(button.dataset.builderStep);
      if (step === state.step) button.setAttribute("aria-current", "step");
      else button.removeAttribute("aria-current");
      button.classList.toggle("is-complete", stepComplete(step));
    }
    els.previous.disabled = state.step === 1;
    els.next.hidden = state.step === 4;
    els.currentStep.textContent = state.step;
    els.next.textContent = state.step === 1 ? "Continue to deciding fact →" : state.step === 2 ? "Continue to evidence →" : "Validate and export →";
  }

  function proposalUrl() {
    const draft = state.draft;
    const contract = currentContract();
    if (!contract) return `${REPO_URL}/issues/new/choose`;
    const issueTitle = `[boundary proposal] ${draft.title}`;
    const body = [
      "## Boundary proposal",
      "",
      `- Industry or service: **${draft.industry}**`,
      `- Evaluation shape: **${contract.name}**`,
      `- Declared action change: **${actionLabel(draft.baseline_review)} → ${actionLabel(draft.changed_review)}**`,
      `- Accountable authority role: **${draft.authority_owner}**`,
      "",
      "> This issue intentionally omits scenario text, evidence, and source URLs. Review the locally generated bundle for sensitive information before adding details.",
      "",
      "## What help is needed?",
      "",
      "<!-- Domain review, contract selection, implementation, evaluation, or reproduction? -->",
    ].join("\n");
    return `${REPO_URL}/issues/new?title=${encodeURIComponent(issueTitle)}&body=${encodeURIComponent(body)}&labels=use-case-proposal`;
  }

  function updateAll({ save = true } = {}) {
    state.draft = readDraft();
    state.validations = validate(state.draft);
    els.descriptionCount.textContent = state.draft.description.length;
    renderContractState();
    renderPrivacy();
    renderPreview();
    renderValidation();
    renderStep();
    els.proposalLink.href = proposalUrl();
    if (save) persist();
  }

  function goToStep(step, scroll = false) {
    state.step = Math.max(1, Math.min(4, step));
    renderStep();
    if (scroll) els.workbench.scrollIntoView({ behavior: "smooth", block: "start" });
    const heading = document.querySelector(`[data-builder-panel="${state.step}"] h3`);
    if (heading) heading.setAttribute("tabindex", "-1");
    if (heading && scroll) heading.focus({ preventScroll: true });
  }

  function safeMarkdown(value) {
    return text(value).replace(/[<>]/g, "").replaceAll("|", "&#124;");
  }

  function mermaidText(value) {
    return safeMarkdown(value).replace(/["\[\]{}]/g, "'").slice(0, 110);
  }

  function xml(value) {
    return String(value || "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&apos;");
  }

  function cardExcerpt(value, limit = 34) {
    const clean = text(value);
    return clean.length > limit ? `${clean.slice(0, limit - 1).trim()}…` : clean;
  }

  function sourceObjects() {
    return state.draft.sources.map((url, index) => ({ label: `Declared primary source ${index + 1}`, url, verification_status: "review_required" }));
  }

  function makePair() {
    const draft = state.draft;
    const contract = currentContract();
    const id = slugify(draft.title);
    return {
      schema_version: "aau-boundary-draft/1.0",
      status: "adaptation_required",
      id,
      industry: draft.industry,
      title: draft.title,
      workflow_description: draft.description,
      contract: { id: contract.id, name: contract.name, forge_mode: contract.forge_mode, source: contract.source_document },
      human_authority: { accountable_owner: draft.authority_owner, protected_action: draft.protected_action, required_domain_reviewer: draft.domain_reviewer },
      boundary: { label: draft.boundary_label, before: draft.before, after: draft.after },
      expected_reviews: { baseline: draft.baseline_review, changed: draft.changed_review },
      why: draft.why,
      stake: draft.stake,
      evidence: { baseline_held: draft.baseline_evidence, changed_held: draft.changed_evidence, changed_missing: draft.changed_missing },
      sources: sourceObjects(),
      limitations: [
        "Builder validation covers structure, not domain correctness.",
        "Source URLs are declared by the author and have not been verified by this tool.",
        "Synthetic scenarios must replace any private, personal, regulated, or confidential records.",
        "The agent may prepare evidence but may not claim the protected human action.",
      ],
    };
  }

  function makeScenarios(pair) {
    const required = [...new Set([...pair.evidence.baseline_held, ...pair.evidence.changed_held, ...pair.evidence.changed_missing])];
    const changedMissing = required.filter((item) => !pair.evidence.changed_held.includes(item));
    const factKey = slugify(pair.boundary.label).replaceAll("-", "_");
    const base = {
      schema_version: "aau-boundary-scenario/1.0",
      case_text: `Synthetic ${pair.industry} case for ${pair.title}. Replace with a domain-reviewed fictional case.`,
      gate_states: { domain_truth_reviewed: "unknown", protected_authority_preserved: "satisfied" },
      policy_snapshot: { status: "TODO(domain)", declared_sources: pair.sources.map((source) => source.url) },
    };
    const baseline = {
      ...base,
      scenario_id: `${pair.id}-baseline`,
      archetype: "baseline_clean_twin",
      record: { domain_facts: { [factKey]: pair.boundary.before } },
      evidence_registry: { required_evidence: required, held_evidence: pair.evidence.baseline_held, missing_evidence: required.filter((item) => !pair.evidence.baseline_held.includes(item)) },
      draft_oracle: { expected_review: pair.expected_reviews.baseline, reason: "TODO(domain): encode the source-grounded baseline rule" },
    };
    const changed = {
      ...base,
      scenario_id: `${pair.id}-changed`,
      archetype: "single_semantic_boundary_changed",
      record: { domain_facts: { [factKey]: pair.boundary.after } },
      evidence_registry: { required_evidence: required, held_evidence: pair.evidence.changed_held, missing_evidence: changedMissing },
      draft_oracle: { expected_review: pair.expected_reviews.changed, reason: "TODO(domain): encode why the declared boundary changes the action" },
    };
    return [baseline, changed];
  }

  function makeBrief(pair) {
    const contract = currentContract();
    return {
      contract_version: "aau-studio/1.0",
      created_at: new Date().toISOString(),
      boundary_draft: { schema_version: pair.schema_version, id: pair.id, status: pair.status },
      workflow: {
        description: pair.workflow_description,
        industry: pair.industry,
        agent_shape: contract.agent_shape,
        risks: [pair.stake, `Protected action: ${pair.human_authority.protected_action}`],
      },
      recommended_case: { ...contract.recommended_case, contract: contract.name, fit_score: 100 },
      verification_plan: {
        minimum_scenarios: 32,
        minimum_repeats: 3,
        required_proofs: [
          "programmatic ground truth shared by generation and scoring",
          "the declared semantic boundary changes the expected reviewer action",
          "at least one clean twin and one deceptive transfer-failure scenario",
          "protected human authority is explicit and never claimed by the agent",
          "primary sources are verified for scope, jurisdiction, and effective date",
          "observed failures link to scenario IDs and committed repeated runs",
        ],
      },
      commands: {
        discover: `aau start ${contract.recommended_case.cli}`,
        install: `python -m pip install -e harness -e ${contract.recommended_case.path}`,
        evaluate: `${contract.recommended_case.cli} eval --backend mock --repeats 3`,
      },
    };
  }

  function makeReadme(pair) {
    const contract = currentContract();
    return `# ${safeMarkdown(pair.title)}\n\n> [!CAUTION]\n> **Adaptation required.** Boundary Builder validated this draft's structure, not its domain\n> truth, sources, policy interpretation, or production safety. A qualified reviewer must replace\n> every \`TODO(domain)\` and verify the protected authority before real-world use.\n\n## Declared boundary\n\n\`\`\`mermaid\nflowchart LR\n  A["BEFORE: ${mermaidText(pair.boundary.before)}"] -->|"${mermaidText(pair.boundary.label)}"| B["AFTER: ${mermaidText(pair.boundary.after)}"]\n  A --> C["${actionLabel(pair.expected_reviews.baseline)}"]\n  B --> D["${actionLabel(pair.expected_reviews.changed)}"]\n  C -. "agent prepares evidence" .-> H["${mermaidText(pair.human_authority.accountable_owner)}"]\n  D -. "exception routes to" .-> H\n\`\`\`\n\n| Draft field | Declared value |\n|---|---|\n| Industry or service | ${safeMarkdown(pair.industry)} |\n| Evaluation contract | [${safeMarkdown(contract.name)}](../../${contract.source_document}) |\n| Forge mode | \`${contract.forge_mode}\` |\n| Protected action | ${safeMarkdown(pair.human_authority.protected_action)} |\n| Required reviewer | ${safeMarkdown(pair.human_authority.required_domain_reviewer)} |\n| Expected action change | **${actionLabel(pair.expected_reviews.baseline)} → ${actionLabel(pair.expected_reviews.changed)}** |\n\n## Why the action moves\n\n${safeMarkdown(pair.why)}\n\n**What is at stake:** ${safeMarkdown(pair.stake)}\n\n## Evidence ledger\n\n- Baseline held: ${pair.evidence.baseline_held.map((item) => `\`${safeMarkdown(item)}\``).join(", ")}\n- Changed held: ${pair.evidence.changed_held.map((item) => `\`${safeMarkdown(item)}\``).join(", ")}\n- Changed missing: ${pair.evidence.changed_missing.length ? pair.evidence.changed_missing.map((item) => `\`${safeMarkdown(item)}\``).join(", ") : "none declared"}\n\n## Start the runnable adaptation\n\n\`\`\`bash\npython -m pip install -e harness[dev]\naau forge evaluation-brief.json --name ${pair.id}\naau forge doctor ${pair.id}\n\`\`\`\n\nForge inherits evaluation structure from [${safeMarkdown(contract.recommended_case.title)}](../../${contract.recommended_case.path}/), not that lab's domain rules. The source declarations and review work remain in [\`evidence/PRIMARY_SOURCES.md\`](evidence/PRIMARY_SOURCES.md) and [\`CONTRIBUTION_CHECKLIST.md\`](CONTRIBUTION_CHECKLIST.md).\n\n## Draft limitations\n\n${pair.limitations.map((item) => `- ${safeMarkdown(item)}`).join("\n")}\n`;
  }

  function makeTest(pair) {
    return `"""Structural regression checks exported by AAU Boundary Builder."""\n\nimport json\nfrom pathlib import Path\n\n\nROOT = Path(__file__).resolve().parents[1]\nPAIR = json.loads((ROOT / "boundary-pair.json").read_text())\nSCENARIOS = [json.loads(line) for line in (ROOT / "evals" / "scenarios.jsonl").read_text().splitlines() if line.strip()]\n\n\ndef test_declared_semantic_boundary_changes_action():\n    assert PAIR["status"] == "adaptation_required"\n    assert PAIR["boundary"]["before"] != PAIR["boundary"]["after"]\n    assert PAIR["expected_reviews"]["baseline"] != PAIR["expected_reviews"]["changed"]\n\n\ndef test_synthetic_twin_is_explicit_and_source_declared():\n    assert len(SCENARIOS) == 2\n    assert {item["archetype"] for item in SCENARIOS} == {"baseline_clean_twin", "single_semantic_boundary_changed"}\n    assert all(item["policy_snapshot"]["declared_sources"] for item in SCENARIOS)\n    assert PAIR["human_authority"]["protected_action"]\n`;
  }

  function makeSources(pair) {
    return `# Primary-source review ledger\n\n> These URLs were declared in a browser draft. Boundary Builder did not fetch, quote, or\n> verify them. A qualified reviewer must complete every field below.\n\n${pair.sources.map((source, index) => `## Source ${index + 1}\n\n- URL: ${source.url}\n- Controlling authority: TODO(domain)\n- Jurisdiction and scope: TODO(domain)\n- Effective date checked: TODO(domain)\n- Exact deciding passage: TODO(domain)\n- Reviewer and review date: TODO(domain)\n`).join("\n")}\n## Boundary claim under review\n\n- Before: ${safeMarkdown(pair.boundary.before)}\n- After: ${safeMarkdown(pair.boundary.after)}\n- Expected action change: ${actionLabel(pair.expected_reviews.baseline)} → ${actionLabel(pair.expected_reviews.changed)}\n`;
  }

  function makeChecklist(pair) {
    return `# Contribution checklist\n\nThis ZIP is a **draft handoff**, not an AAU-verified use case. Complete these items before requesting review.\n\n## Domain truth\n\n- [ ] Confirm the accountable authority: ${safeMarkdown(pair.human_authority.accountable_owner)}.\n- [ ] Verify that the agent never claims: ${safeMarkdown(pair.human_authority.protected_action)}.\n- [ ] Have ${safeMarkdown(pair.human_authority.required_domain_reviewer)} review every deciding rule.\n- [ ] Replace every \`TODO(domain)\` with source-grounded rules and dated citations.\n- [ ] Use synthetic data only; remove private, personal, regulated, and confidential information.\n\n## Evaluation\n\n- [ ] Create at least 32 deterministic scenarios from one shared gold function.\n- [ ] Include a clean twin and a deceptive transfer-failure pair.\n- [ ] Test evidence absence, conflicting records, stale rules, and protected authority.\n- [ ] Run at least two real models with at least three repeats each.\n- [ ] Report exact task success, completion, cost, latency, uncertainty, and provenance together.\n- [ ] Link every observed failure to a scenario ID and committed result.\n\n## Repository path\n\n- [ ] Run \`aau forge evaluation-brief.json --name ${pair.id}\`.\n- [ ] Run \`aau forge doctor ${pair.id}\` and resolve every adaptation gap.\n- [ ] Open a use-case proposal before a pull request.\n- [ ] Add the verified package to the catalog, CI matrix, and visual generator only after review.\n`;
  }

  function makeCard(pair) {
    const contract = currentContract();
    pair = { ...pair, boundary: { ...pair.boundary, before: cardExcerpt(pair.boundary.before), after: cardExcerpt(pair.boundary.after) } };
    return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-labelledby="title desc">\n  <title id="title">${xml(pair.title)} — AAU Boundary Builder draft</title>\n  <desc id="desc">An unverified counterfactual draft changing ${xml(pair.boundary.label)} from ${xml(pair.boundary.before)} to ${xml(pair.boundary.after)}.</desc>\n  <defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#090b11"/><stop offset=".62" stop-color="#141b22"/><stop offset="1" stop-color="#0a0c12"/></linearGradient><pattern id="grid" width="36" height="36" patternUnits="userSpaceOnUse"><path d="M36 0H0V36" fill="none" stroke="#6df5d2" stroke-opacity=".06"/></pattern></defs>\n  <rect width="1200" height="630" fill="url(#bg)"/><rect width="1200" height="630" fill="url(#grid)"/><rect x="30" y="30" width="1140" height="570" fill="none" stroke="#4a5962"/><rect x="30" y="30" width="10" height="570" fill="#ffde59"/>\n  <text x="72" y="78" class="micro mint">AAU / BOUNDARY BUILDER / ADAPTATION REQUIRED</text>\n  <text x="72" y="157" class="headline">${xml(pair.title.slice(0, 46))}</text>\n  <text x="72" y="197" class="meta">${xml(pair.industry.toUpperCase())} / ${xml(contract.name.toUpperCase())}</text>\n  <g transform="translate(72 244)"><rect width="450" height="168" fill="#0b1015" stroke="#43515a"/><text x="24" y="35" class="micro">BEFORE</text><text x="24" y="78" class="fact">${xml(pair.boundary.before.slice(0, 56))}</text><text x="24" y="137" class="action mint">${xml(actionLabel(pair.expected_reviews.baseline).toUpperCase())}</text></g>\n  <g transform="translate(678 244)"><rect width="450" height="168" fill="#0b1015" stroke="#43515a"/><text x="24" y="35" class="micro">AFTER</text><text x="24" y="78" class="fact">${xml(pair.boundary.after.slice(0, 56))}</text><text x="24" y="137" class="action pink">${xml(actionLabel(pair.expected_reviews.changed_review || pair.expected_reviews.changed).toUpperCase())}</text></g>\n  <circle cx="600" cy="328" r="43" fill="#ffde59" stroke="#ff7ac8" stroke-width="4"/><text x="600" y="344" class="delta" text-anchor="middle">Δ</text>\n  <text x="72" y="480" class="micro">DECLARED SEMANTIC BOUNDARY</text><text x="72" y="520" class="boundary">${xml(pair.boundary.label)}</text>\n  <text x="72" y="565" class="small">STRUCTURE CHECKED LOCALLY · SOURCES NOT VERIFIED · HUMAN AUTHORITY PROTECTED</text><text x="1128" y="565" class="small" text-anchor="end">awesome-agentic-usecases</text>\n  <style>text{font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;fill:#f5f3ea}.micro{font:800 13px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:1.4px;fill:#9facb5}.mint{fill:#6df5d2}.pink{fill:#ff7ac8}.headline{font-size:51px;font-weight:900;letter-spacing:-2.7px}.meta{font:800 14px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:1px;fill:#9facb5}.fact{font-size:22px;font-weight:800}.action{font:900 31px ui-monospace,SFMono-Regular,Menlo,monospace}.delta{font:900 42px ui-monospace,SFMono-Regular,Menlo,monospace;fill:#090b11}.boundary{font-size:29px;font-weight:850}.small{font:750 10px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.8px;fill:#9facb5}</style>\n</svg>\n`;
  }

  function makeFiles() {
    const pair = makePair();
    const brief = makeBrief(pair);
    const scenarios = makeScenarios(pair);
    const root = `boundary-draft-${pair.id}`;
    return {
      [`${root}/README.md`]: makeReadme(pair),
      [`${root}/boundary-pair.json`]: `${JSON.stringify(pair, null, 2)}\n`,
      [`${root}/evals/scenarios.jsonl`]: `${scenarios.map((scenario) => JSON.stringify(scenario)).join("\n")}\n`,
      [`${root}/tests/test_boundary.py`]: makeTest(pair),
      [`${root}/evidence/PRIMARY_SOURCES.md`]: makeSources(pair),
      [`${root}/evaluation-brief.json`]: `${JSON.stringify(brief, null, 2)}\n`,
      [`${root}/CONTRIBUTION_CHECKLIST.md`]: makeChecklist(pair),
      [`${root}/assets/boundary-card.svg`]: makeCard(pair),
    };
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
    setTimeout(() => URL.revokeObjectURL(url), 750);
  }

  function ready() {
    return state.validations.length === state.data.validation_gate_count && state.validations.every((item) => item.valid);
  }

  function status(message) {
    els.actionStatus.textContent = message;
  }

  async function copyText(value, message) {
    try {
      await navigator.clipboard.writeText(value);
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
    }
    status(message);
  }

  function bindEvents() {
    els.begin.addEventListener("click", () => els.workbench.scrollIntoView({ behavior: "smooth", block: "start" }));
    els.loadExample.addEventListener("click", () => {
      if (hasMeaningfulDraft() && !window.confirm("Replace the current local draft with the source-derived grid example?")) return;
      fillDraft(state.data.worked_example);
      state.step = 1;
      updateAll();
      els.workbench.scrollIntoView({ behavior: "smooth", block: "start" });
      els.saveState.textContent = "Verified example loaded locally";
    });
    els.form.addEventListener("input", () => updateAll());
    els.form.addEventListener("change", () => updateAll());
    els.steps.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-builder-step]");
      if (button) goToStep(Number(button.dataset.builderStep), true);
    });
    els.previous.addEventListener("click", () => goToStep(state.step - 1, true));
    els.next.addEventListener("click", () => goToStep(state.step + 1, true));
    els.reset.addEventListener("click", () => {
      if (hasMeaningfulDraft() && !window.confirm("Delete this locally saved Boundary Builder draft?")) return;
      els.form.reset();
      state.draft = {};
      state.step = 1;
      try { localStorage.removeItem(STORAGE_KEY); } catch { /* Local storage is optional. */ }
      updateAll({ save: false });
      els.saveState.textContent = "Local draft cleared";
      els.saveState.classList.remove("is-saved");
    });
    els.downloadBundle.addEventListener("click", () => {
      if (!ready()) return;
      const files = makeFiles();
      const bytes = globalThis.AAUBoundaryZip.archive(files);
      const id = slugify(state.draft.title);
      download(`aau-boundary-${id}.zip`, "application/zip", new Blob([bytes], { type: "application/zip" }));
      status(`Eight-file contribution ZIP generated locally for ${id}.`);
    });
    els.downloadBrief.addEventListener("click", () => {
      if (!ready()) return;
      const pair = makePair();
      download(`${pair.id}-evaluation-brief.json`, "application/json", `${JSON.stringify(makeBrief(pair), null, 2)}\n`);
      status("Forge-compatible evaluation brief generated locally.");
    });
    els.downloadPair.addEventListener("click", () => {
      if (!ready()) return;
      const pair = makePair();
      download(`${pair.id}-boundary-pair.json`, "application/json", `${JSON.stringify(pair, null, 2)}\n`);
      status("Boundary pair contract generated locally.");
    });
    els.downloadCard.addEventListener("click", () => {
      if (!ready()) return;
      const pair = makePair();
      download(`${pair.id}-boundary-card.svg`, "image/svg+xml", makeCard(pair));
      status("Original SVG boundary card generated locally.");
    });
    els.copyCommand.addEventListener("click", () => {
      if (!ready()) return;
      const id = slugify(state.draft.title);
      copyText(`aau forge ~/Downloads/${id}-evaluation-brief.json --name ${id}\naau forge doctor ${id}`, "Forge and Doctor commands copied.");
    });
    els.proposalLink.addEventListener("click", (event) => {
      if (!ready()) event.preventDefault();
    });
  }

  async function init() {
    try {
      const response = await fetch("boundary-builder-data.json?v=1");
      if (!response.ok) throw new Error(`Boundary Builder data returned ${response.status}`);
      state.data = await response.json();
      els.contractCount.textContent = state.data.contract_count;
      els.gateCount.textContent = state.data.validation_gate_count;
      els.fileCount.textContent = state.data.bundle_file_count;
      renderContracts();
      fillDraft(restore() || {});
      bindEvents();
      updateAll({ save: false });
      els.saveState.textContent = restore() ? "Draft restored locally" : "Nothing entered yet";
    } catch (error) {
      document.querySelector("#builder-step-one-title").textContent = "Boundary Builder could not load.";
      document.querySelector(".builder-panel-heading p").textContent = `${error.message}. Refresh the page or inspect the builder contract on GitHub.`;
      els.next.disabled = true;
    }
  }

  init();
})();
