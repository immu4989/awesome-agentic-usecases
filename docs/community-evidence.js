(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const encoder = new TextEncoder();
  const state = { starter: null, suite: null, receipts: [], data: null, report: null };
  const LEVELS = ["Generated", "Domain reviewed", "Reproduced", "Verified"];
  const STARTER_FIELDS = ["boundary", "generated_file_sha256", "human_authority", "name", "package_version", "primary_adapter", "starter_version", "status", "template_id", "title"];
  const RECEIPT_FIELDS = ["adapter_kind", "boundary", "metrics", "privacy", "receipt_version", "results", "scenario_count", "suite_id", "suite_sha256"];
  const privacyContract = {
    adapter_responses_included: false,
    credentials_included: false,
    expected_answers_included: false,
    reasoning_included: false,
    scenario_inputs_included: false,
    suite_sharing_attested: true,
  };

  function canonical(value) {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
    return value;
  }

  function renderJson(value) { return `${JSON.stringify(canonical(value), null, 2)}\n`; }
  async function sha256(value) {
    const bytes = typeof value === "string" ? encoder.encode(value) : value;
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return [...new Uint8Array(digest)].map((item) => item.toString(16).padStart(2, "0")).join("");
  }
  function suiteText(value) { return `${JSON.stringify(canonical(value))}\n`; }
  function slug(value) { return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 63); }
  function lines(value) { return value.split("\n").map((item) => item.trim()).filter(Boolean); }
  function escapeXml(value) { return String(value).replace(/[<>&"']/g, (item) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&apos;" })[item]); }
  function text(name) { return byId(name).value.trim(); }

  function sensitiveFindings(values) {
    const joined = values.join("\n");
    return [
      ["email address", /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i],
      ["U.S. Social Security number", /\b\d{3}[- ]?\d{2}[- ]?\d{4}\b/],
      ["payment card-like number", /\b(?:\d[ -]*?){13,19}\b/],
      ["credential or private key", /(?:api[_ -]?key|access[_ -]?token|client[_ -]?secret|password)\s*[:=]|-----BEGIN [A-Z ]*PRIVATE KEY-----/i],
      ["classified or controlled marker", /\b(?:TOP SECRET|SECRET\/\/|CUI\/\/|SOURCE SELECTION INFORMATION)\b/i],
    ].filter(([, pattern]) => pattern.test(joined)).map(([name]) => name);
  }

  async function readJsonFile(file, label) {
    if (!file || file.size > 2_000_000) throw new Error(`${label} is missing or exceeds 2 MB.`);
    try { return JSON.parse(await file.text()); }
    catch { throw new Error(`${label} is not valid JSON.`); }
  }

  function metadata() {
    const tags = text("evidence-tags").split(",").map((item) => item.trim().toLowerCase()).filter(Boolean);
    const sources = lines(text("evidence-sources"));
    const review = {};
    if (text("evidence-reviewer")) review.reviewer = text("evidence-reviewer");
    if (text("evidence-reviewer-role")) review.reviewer_role = text("evidence-reviewer-role");
    if (text("evidence-review-scope")) review.scope = text("evidence-review-scope");
    if (text("evidence-reviewed-at")) review.reviewed_at = text("evidence-reviewed-at");
    if (sources.length) review.sources = sources;
    const reproduction = {};
    if (text("evidence-reproducer")) reproduction.reproducer_name = text("evidence-reproducer");
    if (text("evidence-reproducer-github")) reproduction.reproducer_github = text("evidence-reproducer-github").replace(/^@/, "");
    if (text("evidence-reproduction-scope")) reproduction.scope = text("evidence-reproduction-scope");
    if (Object.keys(reproduction).length) reproduction.receipt_file = `receipts/run-${String(state.receipts.length).padStart(2, "0")}.json`;
    return {
      schema_version: "aau-community-evidence/1.0",
      id: slug(text("evidence-id")),
      origin: "community-submission",
      contributor: { name: text("evidence-name"), github: text("evidence-github").replace(/^@/, "") },
      summary: text("evidence-summary"), why_fork: text("evidence-why-fork"),
      beneficiaries: text("evidence-beneficiaries"), industry: text("evidence-industry"),
      failure_shape: text("evidence-failure-shape"), tags, review, reproduction,
    };
  }

  async function validateReceipt(receipt, suite) {
    const suiteHash = await sha256(suiteText(suite));
    const exactFields = JSON.stringify(Object.keys(receipt).sort()) === JSON.stringify(RECEIPT_FIELDS);
    const rows = Array.isArray(receipt?.results) ? receipt.results : [];
    const metricNames = ["submitted_rate", "outcome_exact_rate", "no_forbidden_attempt_rate", "no_forbidden_execute_rate", "exact_rate", "mean_latency_s"];
    const metrics = receipt?.metrics || {};
    const safeMetrics = metricNames.every((name) => typeof metrics[name] === "number" && Number.isFinite(metrics[name]));
    return exactFields && receipt.receipt_version === "aau-byo-agent-receipt/1.0"
      && ["command", "endpoint"].includes(receipt.adapter_kind)
      && receipt.suite_id === suite.suite_id && receipt.suite_sha256 === suiteHash
      && receipt.scenario_count === suite.cases.length && rows.length === suite.cases.length
      && JSON.stringify(canonical(receipt.privacy)) === JSON.stringify(canonical(privacyContract)) && safeMetrics;
  }

  async function deriveEvidence(meta, starter, suite, receipts) {
    const receiptHashes = await Promise.all(receipts.map((item) => sha256(renderJson(item))));
    const review = meta.review || {};
    const reproduction = meta.reproduction || {};
    const originalSuiteHash = starter?.generated_file_sha256?.["suite.json"];
    const adapted = Boolean(originalSuiteHash && originalSuiteHash !== await sha256(renderJson(suite)));
    const reproductionComplete = Boolean(
      reproduction.reproducer_name && reproduction.reproducer_github
      && reproduction.reproducer_github.toLowerCase() !== meta.contributor.github.toLowerCase()
      && reproduction.scope && receipts.length > 0 && reproduction.receipt_file,
    );
    const checks = [
      ["starter-contract", "Generated", starter?.starter_version === "aau-agent-evidence-starter/1.0", `starter contract ${starter?.starter_version || "missing"}`],
      ["public-agent-receipt", "Generated", receipts.length > 0, `${receipts.length} non-mock privacy-bounded receipt(s)`],
      ["protected-human-authority", "Generated", Boolean(suite?.human_authority?.accountable_role && suite?.human_authority?.protected_action), suite?.human_authority?.accountable_role || "missing"],
      ["adapted-suite", "Domain reviewed", adapted, adapted ? "suite differs from generated template" : "starter smoke suite is unchanged"],
      ["scenario-depth", "Domain reviewed", suite?.cases?.length >= 10, `${suite?.cases?.length || 0}/10 synthetic cases`],
      ["named-domain-review", "Domain reviewed", ["reviewer", "reviewer_role", "scope", "reviewed_at"].every((field) => review[field]), review.scope || "named review is incomplete"],
      ["source-ledger", "Domain reviewed", (review.sources || []).filter((url) => url.startsWith("https://")).length >= 2, `${(review.sources || []).length}/2 https source links`],
      ["repeated-receipts", "Reproduced", receipts.length >= 3 && new Set(receiptHashes).size >= 3, `${receipts.length} receipts · ${new Set(receiptHashes).size} distinct hashes`],
      ["named-independent-reproduction", "Verified", reproductionComplete, reproductionComplete ? `named reproduction by @${reproduction.reproducer_github}` : "different named reproducer and linked receipt required"],
    ].map(([id, stage, passed, detail]) => ({ id, stage, passed: Boolean(passed), detail }));
    let level = "Draft";
    for (const candidate of LEVELS) {
      const rank = LEVELS.indexOf(candidate);
      if (checks.filter((item) => LEVELS.indexOf(item.stage) <= rank).every((item) => item.passed)) level = candidate;
      else break;
    }
    return { checks_version: "aau-community-evidence-checks/1.0", level, levels: LEVELS, score: { passed: checks.filter((item) => item.passed).length, total: checks.length }, checks, boundary: "Evidence levels are derived from submitted artifacts. They are not identity verification, certification, endorsement, production validation, or authority to deploy." };
  }

  async function validateLocalFiles() {
    const meta = metadata();
    const files = [...byId("evidence-receipts").files];
    try {
      state.starter = await readJsonFile(byId("evidence-starter-manifest").files[0], "aau-starter.json");
      state.suite = await readJsonFile(byId("evidence-suite").files[0], "suite.json");
      state.receipts = await Promise.all(files.map((file, index) => readJsonFile(file, `receipt ${index + 1}`)));
    } catch (error) {
      state.starter = null; state.suite = null; state.receipts = [];
      byId("evidence-status").textContent = error.message;
    }
    const starterFields = state.starter && JSON.stringify(Object.keys(state.starter).sort()) === JSON.stringify(STARTER_FIELDS);
    const sharing = state.suite?.sharing || {};
    const publicSuite = ["synthetic", "public", "public_synthetic"].includes(sharing.classification)
      && sharing.human_review_complete === true
      && ["contains_personally_identifiable_information", "contains_procurement_sensitive_information", "contains_controlled_unclassified_information", "contains_classified_information", "contains_secrets_or_credentials"].every((field) => sharing[field] === false);
    const receiptsSafe = state.suite && state.receipts.length > 0 && (await Promise.all(state.receipts.map((item) => validateReceipt(item, state.suite)))).every(Boolean);
    const findings = sensitiveFindings([renderJson(meta), renderJson(state.suite || {}), ...state.receipts.map(renderJson)]);
    const requiredMeta = meta.id && /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$/.test(meta.contributor.github)
      && [meta.contributor.name, meta.summary, meta.why_fork, meta.beneficiaries, meta.industry, meta.failure_shape].every((item) => item.length > 0)
      && meta.tags.length >= 2 && meta.tags.length <= 6;
    const gates = [
      ["Exact public Starter manifest loaded", Boolean(starterFields)],
      ["Reviewed synthetic/public suite loaded", Boolean(publicSuite)],
      ["Protected human authority matches Starter", Boolean(state.starter && JSON.stringify(canonical(state.starter.human_authority)) === JSON.stringify(canonical(state.suite?.human_authority)))],
      ["One to twelve command/endpoint receipts loaded", state.receipts.length >= 1 && state.receipts.length <= 12],
      ["Every receipt is suite-bound and privacy-bounded", Boolean(receiptsSafe)],
      ["Contribution id is a safe slug", /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(meta.id)],
      ["Contributor name and GitHub handle declared", Boolean(meta.contributor.name && meta.contributor.github)],
      ["Beneficiary, summary, reuse story, industry, and failure shape declared", Boolean(requiredMeta)],
      ["Two to six discovery tags declared", meta.tags.length >= 2 && meta.tags.length <= 6],
      [findings.length ? `Sensitive-data scan found: ${findings.join(", ")}` : "No common sensitive-data pattern detected", findings.length === 0],
      ["Synthetic/public sharing attestation accepted", byId("evidence-attest-public").checked],
      ["Non-certification and human-authority boundary accepted", byId("evidence-attest-boundary").checked],
    ];
    state.report = state.starter && state.suite ? await deriveEvidence(meta, state.starter, state.suite, state.receipts) : null;
    const passed = gates.filter(([, ready]) => ready).length;
    byId("evidence-validation-list").replaceChildren(...gates.map(([label, ready]) => {
      const item = document.createElement("li"); item.textContent = label; item.classList.toggle("is-pass", ready); return item;
    }));
    byId("evidence-gate-score").textContent = `${passed} / ${gates.length} gates`;
    byId("evidence-derived-level").textContent = state.report?.level || "Draft";
    byId("evidence-export").disabled = passed !== gates.length || state.report?.level === "Draft";
    byId("evidence-status").textContent = passed === gates.length ? `${state.report.level} pack ready. No file or form value has left this tab.` : `${gates.length - passed} local gate${gates.length - passed === 1 ? "" : "s"} remain.`;
  }

  function shareCard(meta, checks, suite) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img"><rect width="1200" height="630" rx="38" fill="#081522"/><text x="70" y="75" fill="#58e1ba" font-family="monospace" font-size="18">AAU / BUILT WITH EVIDENCE</text><text x="70" y="145" fill="#fff" font-family="sans-serif" font-size="42" font-weight="800">${escapeXml(meta.id.replaceAll("-", " ").toUpperCase())}</text><path d="M120 330H1080" stroke="#31526e" stroke-width="4" stroke-dasharray="9 12"/><g fill="#102b3b" stroke="#58e1ba" stroke-width="3"><circle cx="150" cy="330" r="55"/><circle cx="450" cy="330" r="55"/><circle cx="750" cy="330" r="55"/><circle cx="1050" cy="330" r="55"/></g><g fill="#fff" font-family="monospace" font-size="14" text-anchor="middle"><text x="150" y="335">CONNECT</text><text x="450" y="335">REVIEW</text><text x="750" y="335">REPEAT</text><text x="1050" y="335">PUBLISH</text></g><text x="70" y="500" fill="#9fb4c9" font-family="monospace" font-size="15">DERIVED EVIDENCE LEVEL</text><text x="70" y="550" fill="#fff" font-family="sans-serif" font-size="38" font-weight="800">${escapeXml(checks.level)}</text><text x="535" y="500" fill="#ffc96b" font-family="monospace" font-size="15">PROTECTED HUMAN AUTHORITY</text><text x="535" y="542" fill="#fff" font-family="sans-serif" font-size="19" font-weight="700">${escapeXml(suite.human_authority.accountable_role)}</text><text x="70" y="600" fill="#58e1ba" font-family="monospace" font-size="14">PUBLIC RECEIPTS · SYNTHETIC SUITE · SHA-256 MANIFEST · NO PRIVATE TRACES</text></svg>`;
  }

  async function buildContributionPack() {
    await validateLocalFiles();
    if (byId("evidence-export").disabled) return;
    const meta = metadata();
    const receiptNames = state.receipts.map((_, index) => `receipts/run-${String(index + 1).padStart(2, "0")}.json`);
    const complete = { ...meta, package_version: "1.3.0", starter_version: state.starter.starter_version, suite_id: state.suite.suite_id, suite_sha256: await sha256(suiteText(state.suite)), receipt_files: receiptNames };
    const sourceLines = (meta.review.sources || []).map((url) => `- ${url}`).join("\n") || "- No source URLs supplied; Domain reviewed cannot be derived.";
    const files = {
      "submission.json": renderJson(complete), "starter-manifest.json": renderJson(state.starter), "suite.json": renderJson(state.suite), "checks.json": renderJson(state.report),
      "privacy-scan.json": renderJson({ privacy_version: "aau-community-evidence-privacy/1.0", status: "passed_no_common_sensitive_pattern_detected", findings: [], scanned: ["submission metadata", "suite.json", ...receiptNames], boundary: "Pattern absence does not prove a file contains no sensitive information; authorized human review remains required." }),
      "SOURCE_LEDGER.md": `# Source and review ledger\n\nContributor-supplied scope; no regulator or government approval is implied.\n\n- Reviewer: ${meta.review.reviewer || "Not yet supplied"}\n- Role: ${meta.review.reviewer_role || "Not yet supplied"}\n- Reviewed at: ${meta.review.reviewed_at || "Not yet supplied"}\n- Scope: ${meta.review.scope || "Not yet supplied"}\n\n## Sources\n\n${sourceLines}\n`,
      "README.md": `# ${meta.id.replaceAll("-", " ")}\n\n> Built with AAU · derived evidence level: **${state.report.level}**\n\n${meta.summary}\n\n## Who this helps\n\n${meta.beneficiaries}\n\n## Why fork it\n\n${meta.why_fork}\n\nValidate with \`aau submit --validate .\`. This level is not certification, endorsement, production validation, or authority to deploy.\n`,
      "CONTRIBUTION_CHECKLIST.md": "# Contribution checklist\n\n- [ ] Synthetic or public cases received human review.\n- [ ] Public receipts contain aggregate fields only.\n- [ ] Protected human authority remains explicit.\n- [ ] `aau submit --validate .` passes.\n- [ ] No certification, endorsement, or production approval is claimed.\n",
      "assets/evidence-card.svg": shareCard(meta, state.report, state.suite),
    };
    state.receipts.forEach((receipt, index) => { files[receiptNames[index]] = renderJson(receipt); });
    const manifestRows = await Promise.all(Object.entries(files).sort().map(async ([path, contents]) => ({ path, bytes: encoder.encode(contents).length, sha256: await sha256(contents) })));
    files["manifest.json"] = renderJson({ manifest_version: "aau-community-evidence-manifest/1.0", submission_id: meta.id, hash_algorithm: "sha256", files: manifestRows, claims: { byte_integrity_only: true, identity_verified: false, certification_proved: false, production_validation_proved: false, government_endorsement_proved: false } });
    const archive = globalThis.AAUBoundaryZip.archive(files);
    const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([archive], { type: "application/zip" })); link.download = `${meta.id}-aau-evidence.zip`; link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1_000);
    byId("evidence-status").textContent = `${state.report.level} contribution pack downloaded locally. Validate it with aau-harness 1.3.0 before opening a pull request.`;
  }

  function renderShowcase(data) {
    byId("evidence-stat-packs").textContent = data.stats.submissions;
    byId("evidence-stat-receipts").textContent = data.stats.receipts;
    byId("evidence-stat-industries").textContent = data.stats.industries;
    byId("evidence-showcase-grid").replaceChildren(...data.entries.map((entry) => {
      const article = document.createElement("article"); article.className = "evidence-card";
      const eyebrow = document.createElement("span"); eyebrow.textContent = `${entry.evidence.level} · ${entry.origin.replace("-", " ")}`;
      const title = document.createElement("h3"); title.textContent = entry.id.replaceAll("-", " ");
      const summary = document.createElement("p"); summary.textContent = entry.summary;
      const meter = document.createElement("div"); meter.className = "evidence-card-meter"; meter.innerHTML = `<i style="width:${(entry.evidence.score.passed / entry.evidence.score.total) * 100}%"></i>`;
      const proof = document.createElement("small"); proof.textContent = `${entry.evidence.score.passed}/${entry.evidence.score.total} checks · ${entry.evidence.receipt_count} receipt · ${Math.round(entry.metrics.exact_rate * 100)}% exact`;
      const boundary = document.createElement("blockquote"); boundary.textContent = entry.human_authority.accountable_role;
      const actions = document.createElement("div");
      const inspect = document.createElement("a"); inspect.href = `https://github.com/immu4989/awesome-agentic-usecases/tree/main/${entry.pack_path}`; inspect.textContent = "Inspect pack ↗";
      const card = document.createElement("a"); card.href = `https://raw.githubusercontent.com/immu4989/awesome-agentic-usecases/main/${entry.card_path}`; card.textContent = "Open share card ↗";
      actions.append(inspect, card); article.append(eyebrow, title, summary, meter, proof, boundary, actions); return article;
    }));
  }

  async function loadExample() {
    const example = state.data?.entries?.[0];
    if (!example) return;
    byId("evidence-id").value = `my-${example.id.replace(/-reference$/, "")}`; byId("evidence-name").value = "Your name"; byId("evidence-github").value = "your-github-handle";
    byId("evidence-summary").value = example.summary; byId("evidence-why-fork").value = example.why_fork; byId("evidence-beneficiaries").value = example.beneficiaries;
    byId("evidence-industry").value = example.industry; byId("evidence-failure-shape").value = example.failure_shape; byId("evidence-tags").value = example.tags.join(", ");
    await validateLocalFiles();
    byId("evidence-status").textContent = "Safe metadata example loaded. Add your own Starter manifest, suite, and public receipt files; nothing is fetched or uploaded.";
  }

  async function start() {
    try { state.data = await fetch("community-evidence-data.json").then((response) => { if (!response.ok) throw new Error("showcase unavailable"); return response.json(); }); renderShowcase(state.data); }
    catch { byId("evidence-status").textContent = "The showcase could not load; the local desk remains available."; }
    byId("evidence-form").addEventListener("input", validateLocalFiles); byId("evidence-form").addEventListener("change", validateLocalFiles);
    byId("evidence-load-example").addEventListener("click", loadExample); byId("evidence-export").addEventListener("click", buildContributionPack);
    byId("evidence-begin").addEventListener("click", () => byId("evidence-desk").scrollIntoView({ behavior: "smooth", block: "start" }));
    validateLocalFiles();
  }
  document.addEventListener("DOMContentLoaded", start);
})();
