(() => {
  "use strict";

  const DATA_URL = "receipt-lab-data.json?v=1";
  const MAX_FILE_BYTES = 12 * 1024 * 1024;
  const MEAN_TOLERANCE = 0.00015;
  const RECEIPT_SCHEMA = "aau-reproduction-receipt/1.0";

  const byId = (id) => document.getElementById(id);
  const ui = {
    artifactCount: byId("receipt-artifact-count"),
    hardCount: byId("receipt-hard-count"),
    disclosureCount: byId("receipt-disclosure-count"),
    fileInput: byId("receipt-file-input"),
    fileButton: byId("receipt-file-button"),
    fileName: byId("receipt-file-name"),
    drop: byId("receipt-drop"),
    paste: byId("receipt-paste"),
    inspectPaste: byId("receipt-inspect-paste"),
    samples: byId("receipt-samples"),
    clear: byId("receipt-clear"),
    dashboard: byId("receipt-dashboard"),
    status: byId("receipt-status"),
    statusTitle: byId("receipt-status-title"),
    statusCopy: byId("receipt-status-copy"),
    binding: byId("receipt-binding"),
    summary: byId("receipt-summary"),
    hardList: byId("receipt-hard-list"),
    disclosureList: byId("receipt-disclosure-list"),
    metrics: byId("receipt-metrics"),
    gap: byId("receipt-gap"),
    worst: byId("receipt-worst"),
    provenance: byId("receipt-provenance"),
    privacy: byId("receipt-privacy"),
    downloadJson: byId("receipt-download-json"),
    downloadCard: byId("receipt-download-card"),
    copySummary: byId("receipt-copy-summary"),
    sourceLink: byId("receipt-source-link"),
    labLink: byId("receipt-lab-link"),
    actionStatus: byId("receipt-action-status"),
  };

  if (!ui.dashboard) return;

  const state = { contract: null, inspection: null };

  function finite(value) {
    return typeof value === "number" && Number.isFinite(value);
  }

  function object(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function formatNumber(value, digits = 4) {
    if (!finite(value)) return "—";
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(value);
  }

  function formatMetric(value) {
    if (!finite(value)) return "—";
    if (value >= 0 && value <= 1) return `${(value * 100).toFixed(1)}%`;
    return formatNumber(value);
  }

  function formatMoney(value) {
    if (!finite(value)) return "—";
    return value < 0.01 ? `$${value.toFixed(6)}` : `$${value.toFixed(4)}`;
  }

  function normalizedError(row) {
    if (!object(row)) return null;
    if (typeof row.error === "string" && row.error.trim()) return row.error.trim();
    if (object(row.detail) && typeof row.detail.error === "string" && row.detail.error.trim()) {
      return row.detail.error.trim();
    }
    return null;
  }

  function toleranceEqual(actual, expected, tolerance) {
    return finite(actual) && finite(expected) && Math.abs(actual - expected) <= tolerance;
  }

  function median(values) {
    const sorted = values.filter(finite).sort((a, b) => a - b);
    if (!sorted.length) return null;
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  }

  function check(id, status, detail, observed = null) {
    return { id, status, detail, observed };
  }

  function inspectArtifact(result) {
    const hard = [];
    const disclosures = [];
    const rows = object(result) && Array.isArray(result.results) ? result.results : [];
    const means = object(result) && object(result.metric_means) ? result.metric_means : {};
    const intervals = object(result) && object(result.metric_ci95) ? result.metric_ci95 : {};
    const metricNames = Object.keys(means);

    hard.push(check("parse", object(result) ? "pass" : "fail", object(result) ? "JSON parsed as one object." : "The JSON root must be one object."));

    const envelopeFields = ["backend", "model", "n_scenarios", "n_repeats", "metric_means", "metric_ci95", "mean_cost_per_scenario_usd", "total_cost_usd", "p50_latency_s", "results"];
    const missingEnvelope = object(result) ? envelopeFields.filter((key) => !(key in result)) : envelopeFields;
    const envelopeTypes = object(result)
      && typeof result.backend === "string"
      && typeof result.model === "string"
      && object(result.metric_means)
      && object(result.metric_ci95)
      && Array.isArray(result.results);
    hard.push(check("envelope", missingEnvelope.length === 0 && envelopeTypes ? "pass" : "fail", missingEnvelope.length ? `Missing: ${missingEnvelope.join(", ")}.` : envelopeTypes ? "Required fields and core types are present." : "One or more core fields has the wrong type."));

    const positiveCounts = Number.isInteger(result?.n_scenarios) && result.n_scenarios > 0 && Number.isInteger(result?.n_repeats) && result.n_repeats > 0;
    hard.push(check("coverage", positiveCounts ? "pass" : "fail", positiveCounts ? `${result.n_scenarios} scenarios × ${result.n_repeats} repeats declared.` : "n_scenarios and n_repeats must be positive integers."));

    const expectedTrials = positiveCounts ? result.n_scenarios * result.n_repeats : null;
    hard.push(check("trial-count", expectedTrials !== null && rows.length === expectedTrials ? "pass" : "fail", expectedTrials === null ? "Trial count cannot be checked until coverage is valid." : `${rows.length} rows found; ${expectedTrials} expected.`));

    const scenarioIds = rows.map((row) => object(row) ? row.scenario_id : null);
    const usableScenarioIds = scenarioIds.filter((value) => typeof value === "string" || finite(value));
    const uniqueScenarios = new Set(usableScenarioIds.map(String));
    hard.push(check("scenario-grid", positiveCounts && usableScenarioIds.length === rows.length && uniqueScenarios.size === result.n_scenarios ? "pass" : "fail", positiveCounts ? `${uniqueScenarios.size} unique scenario identities found; ${result.n_scenarios} declared.` : "Scenario identities cannot be reconciled until coverage is valid."));

    let repeatGridValid = positiveCounts && uniqueScenarios.size === result.n_scenarios;
    const expectedRepeats = positiveCounts ? Array.from({ length: result.n_repeats }, (_, index) => index).join(",") : "";
    if (repeatGridValid) {
      for (const scenario of uniqueScenarios) {
        const repeats = rows.filter((row) => String(row.scenario_id) === scenario).map((row) => row.repeat).sort((a, b) => a - b).join(",");
        if (repeats !== expectedRepeats) repeatGridValid = false;
      }
    }
    hard.push(check("repeat-grid", repeatGridValid ? "pass" : "fail", repeatGridValid ? `Every scenario contains repeats 0–${result.n_repeats - 1}.` : "One or more scenarios has missing, duplicate, or unexpected repeat indices."));

    const rowShapeValid = rows.length > 0 && rows.every((row) => object(row)
      && (typeof row.scenario_id === "string" || finite(row.scenario_id))
      && Number.isInteger(row.repeat)
      && object(row.metrics)
      && "cost_usd" in row
      && "latency_s" in row
      && "n_api_calls" in row);
    hard.push(check("row-shape", rowShapeValid ? "pass" : "fail", rowShapeValid ? "Every row exposes identity, metrics, cost, latency, and call count." : "At least one trial row is missing a required field or type."));

    const trialNumbers = rows.flatMap((row) => object(row) ? [row.cost_usd, row.latency_s, row.n_api_calls, ...Object.values(object(row.metrics) ? row.metrics : {})] : [NaN]);
    const publishedNumbers = [...Object.values(means), result?.mean_cost_per_scenario_usd, result?.total_cost_usd, result?.p50_latency_s];
    const finiteValues = rows.length > 0 && trialNumbers.every(finite) && metricNames.length > 0 && publishedNumbers.every(finite);
    hard.push(check("finite-values", finiteValues ? "pass" : "fail", finiteValues ? "Trial and published numeric values are finite." : "A metric, cost, latency, call count, or published aggregate is not finite."));

    const recomputedMeans = {};
    let meansValid = metricNames.length > 0 && rows.length > 0;
    for (const metric of metricNames) {
      const values = rows.map((row) => object(row?.metrics) ? row.metrics[metric] : undefined);
      if (!values.every(finite)) {
        meansValid = false;
        continue;
      }
      recomputedMeans[metric] = values.reduce((sum, value) => sum + value, 0) / values.length;
      if (!toleranceEqual(recomputedMeans[metric], means[metric], MEAN_TOLERANCE)) meansValid = false;
    }
    hard.push(check("metric-aggregation", meansValid ? "pass" : "fail", meansValid ? `${metricNames.length} published means recompute from ${rows.length} rows.` : "At least one published mean does not recompute within 0.00015, or trial values are absent."));

    const recomputedCost = rows.every((row) => finite(row?.cost_usd)) ? rows.reduce((sum, row) => sum + row.cost_usd, 0) : null;
    const costTolerance = finite(result?.total_cost_usd) ? Math.max(0.001, Math.abs(result.total_cost_usd) * 0.01) : 0.001;
    const costValid = recomputedCost !== null && toleranceEqual(recomputedCost, result.total_cost_usd, costTolerance);
    hard.push(check("cost-aggregation", costValid ? "pass" : "fail", recomputedCost === null ? "Trial cost cannot be recomputed." : `Rows sum to ${formatMoney(recomputedCost)}; published total is ${formatMoney(result.total_cost_usd)}.`));

    const nonErrorRows = rows.filter((row) => !normalizedError(row));
    const metricCoverageValid = nonErrorRows.length > 0 && nonErrorRows.every((row) => metricNames.every((metric) => finite(row.metrics?.[metric])));
    disclosures.push(check("metric-coverage", metricCoverageValid ? "pass" : "warn", metricCoverageValid ? `All ${nonErrorRows.length} non-error trials expose every published metric.` : "A non-error trial omits a published metric, or every trial is an error."));

    const intervalNames = Object.keys(intervals);
    const missingIntervals = metricNames.filter((metric) => !intervalNames.includes(metric));
    const extraIntervals = intervalNames.filter((metric) => !metricNames.includes(metric));
    const intervalKeysValid = missingIntervals.length === 0 && extraIntervals.length === 0;
    disclosures.push(check("interval-keys", intervalKeysValid ? "pass" : "warn", intervalKeysValid ? `${intervalNames.length} interval keys match the metric keys.` : `Missing: ${missingIntervals.join(", ") || "none"}; extra: ${extraIntervals.join(", ") || "none"}.`));

    const invalidIntervals = metricNames.filter((metric) => {
      const bounds = intervals[metric];
      return !Array.isArray(bounds) || bounds.length !== 2 || !bounds.every(finite) || !finite(means[metric]) || bounds[0] > means[metric] || bounds[1] < means[metric] || bounds[0] > bounds[1];
    });
    disclosures.push(check("interval-bounds", invalidIntervals.length === 0 ? "pass" : "warn", invalidIntervals.length === 0 ? "Every declared interval is finite and contains its published mean." : `Invalid or non-containing intervals: ${invalidIntervals.join(", ")}.`));

    const recomputedMeanCost = rows.length && rows.every((row) => finite(row?.cost_usd)) ? rows.reduce((sum, row) => sum + row.cost_usd, 0) / rows.length : null;
    const meanCostTolerance = finite(result?.mean_cost_per_scenario_usd) ? Math.max(0.00001, Math.abs(result.mean_cost_per_scenario_usd) * 0.02) : 0.00001;
    const meanCostValid = recomputedMeanCost !== null && toleranceEqual(recomputedMeanCost, result.mean_cost_per_scenario_usd, meanCostTolerance);
    disclosures.push(check("mean-cost", meanCostValid ? "pass" : "warn", recomputedMeanCost === null ? "Mean trial cost cannot be recomputed." : `Rows average ${formatMoney(recomputedMeanCost)}; published value is ${formatMoney(result.mean_cost_per_scenario_usd)}.`));

    const recomputedMedian = median(rows.map((row) => row?.latency_s));
    const latencyTolerance = finite(result?.p50_latency_s) ? Math.max(0.05, Math.abs(result.p50_latency_s) * 0.01) : 0.05;
    const latencyValid = recomputedMedian !== null && toleranceEqual(recomputedMedian, result.p50_latency_s, latencyTolerance);
    disclosures.push(check("median-latency", latencyValid ? "pass" : "warn", recomputedMedian === null ? "Median latency cannot be recomputed." : `Rows produce ${formatNumber(recomputedMedian, 3)}s; published value is ${formatNumber(result.p50_latency_s, 3)}s.`));

    const providerErrors = rows.filter((row) => normalizedError(row)).length;
    disclosures.push(check("provider-errors", providerErrors ? "warn" : "pass", providerErrors ? `${providerErrors} provider-error trial${providerErrors === 1 ? " is" : "s are"} visible and retained.` : "No provider-error trials are declared."));

    const provenance = object(result?.provenance) ? result.provenance : null;
    let provenanceStatus = "warn";
    let provenanceDetail = "Provider and model provenance are absent.";
    if (result?.backend === "mock") {
      provenanceStatus = "pass";
      provenanceDetail = "Deterministic mock result; real-provider provenance is not required.";
    } else if (provenance) {
      const corePresent = typeof provenance.requested_model === "string" && typeof provenance.served_model === "string" && typeof provenance.model_pinned === "boolean";
      provenanceStatus = corePresent && provenance.model_pinned ? "pass" : "warn";
      provenanceDetail = !corePresent ? "Provenance exists but lacks requested model, served model, or pinning." : provenance.model_pinned ? `Pinned served model: ${provenance.served_model}.` : `Floating alias disclosed: ${provenance.served_model}. A rerun may use different weights.`;
    }
    disclosures.push(check("provenance", provenanceStatus, provenanceDetail));

    const dimensions = selectDimensions(means);
    const hardFailures = hard.filter((item) => item.status === "fail").length;
    return {
      result,
      hard,
      disclosures,
      hardFailures,
      providerErrors,
      recomputedMeans,
      recomputedCost,
      recomputedMeanCost,
      recomputedMedian,
      dimensions,
      rows,
    };
  }

  function selectDimensions(means) {
    if (!state.contract) return {};
    const selected = {};
    for (const [dimensionId, definition] of Object.entries(state.contract.dimensions)) {
      const metric = definition.selection_priority.find((candidate) => finite(means[candidate]));
      if (!metric) continue;
      const raw = means[metric];
      const inverted = (definition.inverted_risk_metrics || []).includes(metric);
      selected[dimensionId] = {
        id: dimensionId,
        label: definition.label,
        description: definition.description,
        metric,
        raw,
        display: inverted ? 1 - raw : raw,
        inverted,
      };
    }
    return selected;
  }

  function scanPrivacy(text) {
    const patterns = [
      ["possible credential", /(?:api[_-]?key|secret|password|token)\s*["':=]\s*["']?[A-Za-z0-9_\-]{12,}/i],
      ["possible US Social Security number", /\b\d{3}-\d{2}-\d{4}\b/],
      ["possible email address", /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i],
      ["possible payment-card number", /\b(?:\d[ -]*?){13,19}\b/],
      ["possible US phone number", /\b(?:\+?1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]\d{3}[ .-]\d{4}\b/],
    ];
    return patterns.filter(([, expression]) => expression.test(text)).map(([label]) => label);
  }

  async function sha256(text) {
    const bytes = new TextEncoder().encode(text);
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  }

  function clearChildren(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function element(tag, className, textValue) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (textValue !== undefined) node.textContent = textValue;
    return node;
  }

  function renderCheckList(target, checks) {
    clearChildren(target);
    for (const item of checks) {
      const row = element("li", `receipt-check receipt-check-${item.status}`);
      const marker = element("span", "receipt-check-marker", item.status === "pass" ? "PASS" : item.status === "fail" ? "FAIL" : "OPEN");
      const copy = element("div");
      const label = [...state.contract.hard_checks, ...state.contract.disclosure_checks].find((candidate) => candidate.id === item.id)?.label || item.id;
      copy.append(element("b", "", label), element("p", "", item.detail));
      row.append(marker, copy);
      target.append(row);
    }
  }

  function summaryCard(label, value, note) {
    const card = element("article", "receipt-summary-card");
    card.append(element("span", "", label), element("b", "", value), element("small", "", note));
    return card;
  }

  function renderMetrics(inspection) {
    clearChildren(ui.metrics);
    const dimensions = Object.values(inspection.dimensions);
    if (!dimensions.length) {
      ui.metrics.append(element("p", "receipt-empty", "No recognized exactness, completion, or safety endpoint was found. Published source metrics remain in the exported aggregate receipt."));
      return;
    }
    for (const dimension of dimensions) {
      const card = element("article", "receipt-metric");
      const head = element("div", "receipt-metric-head");
      head.append(element("span", "", dimension.label), element("b", "", formatMetric(dimension.display)));
      const bar = element("div", "receipt-metric-bar");
      const fill = element("i");
      if (dimension.display >= 0 && dimension.display <= 1) fill.style.width = `${Math.max(0, Math.min(100, dimension.display * 100))}%`;
      else bar.classList.add("receipt-metric-bar-na");
      bar.append(fill);
      const note = dimension.inverted ? `${dimension.metric} · displayed as 1 − risk; raw ${formatMetric(dimension.raw)}` : `${dimension.metric} · raw published mean`;
      card.append(head, bar, element("p", "", note));
      ui.metrics.append(card);
    }
    const exact = inspection.dimensions.exact;
    const completion = inspection.dimensions.completion;
    if (exact && completion && exact.display >= 0 && exact.display <= 1 && completion.display >= 0 && completion.display <= 1) {
      const gap = (completion.display - exact.display) * 100;
      ui.gap.hidden = false;
      ui.gap.textContent = `${gap >= 0 ? "+" : ""}${gap.toFixed(1)} points completion − exactness. These endpoints answer different questions; the gap is context, not a score.`;
    } else {
      ui.gap.hidden = true;
    }
  }

  function renderWorstTrials(inspection) {
    clearChildren(ui.worst);
    const exact = inspection.dimensions.exact;
    const metric = exact?.metric || Object.keys(inspection.result.metric_means || {})[0];
    if (!metric || !inspection.rows.length) {
      ui.worst.append(element("p", "receipt-empty", "No trial rows are available."));
      return;
    }
    const table = element("table", "receipt-trial-table");
    const caption = element("caption", "", `Five lowest trials by ${metric}; ties preserve source order.`);
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    ["Scenario", "Repeat", "Metric", "Error", "Cost", "Latency"].forEach((label) => headRow.append(element("th", "", label)));
    head.append(headRow);
    const body = document.createElement("tbody");
    inspection.rows.map((row, index) => ({ row, index, value: finite(row.metrics?.[metric]) ? row.metrics[metric] : Infinity }))
      .sort((a, b) => a.value - b.value || a.index - b.index)
      .slice(0, 5)
      .forEach(({ row, value }) => {
        const tr = document.createElement("tr");
        [String(row.scenario_id), String(row.repeat), finite(value) ? formatMetric(value) : "—", normalizedError(row) ? "yes" : "no", formatMoney(row.cost_usd), `${formatNumber(row.latency_s, 3)}s`]
          .forEach((valueText) => tr.append(element("td", "", valueText)));
        body.append(tr);
      });
    table.append(caption, head, body);
    ui.worst.append(table);
  }

  function renderProvenance(result) {
    clearChildren(ui.provenance);
    const rows = [
      ["Backend", result.backend || "not declared"],
      ["Requested artifact model", result.model || "not declared"],
    ];
    if (object(result.provenance)) {
      rows.push(
        ["Requested model", result.provenance.requested_model || "not declared"],
        ["Served model", result.provenance.served_model || "not declared"],
        ["Pinned snapshot", result.provenance.model_pinned === true ? "yes" : result.provenance.model_pinned === false ? "no" : "not declared"],
        ["Generated", result.provenance.generated_at || "not declared"],
        ["Harness", result.provenance.harness_version || "not declared"],
      );
    }
    for (const [label, value] of rows) {
      const row = element("div");
      row.append(element("span", "", label), element("b", "", String(value)));
      ui.provenance.append(row);
    }
  }

  function receiptLevel(inspection, binding) {
    if (inspection.hardFailures) return { key: "gaps", label: "INTEGRITY GAPS", copy: `${inspection.hardFailures} hard check${inspection.hardFailures === 1 ? " needs" : "s need"} attention. Disclosure findings are reported separately.` };
    if (binding) return { key: "bound", label: "SOURCE-BOUND EXAMPLE", copy: "The artifact is structurally coherent and its committed source hash is known. It has not been independently reproduced by this browser." };
    return { key: "coherent", label: "STRUCTURALLY COHERENT", copy: "The local artifact passes the hard checks. Its source, domain truth, and independent reproduction remain unverified." };
  }

  function setLinks(binding) {
    if (binding) {
      ui.sourceLink.href = binding.result_url;
      ui.sourceLink.hidden = false;
      ui.labLink.href = binding.lab_url;
      ui.labLink.hidden = false;
    } else {
      ui.sourceLink.hidden = true;
      ui.labLink.hidden = true;
    }
  }

  function renderInspection() {
    const current = state.inspection;
    if (!current) return;
    const { analysis, binding, fileName, hash, privacyFindings } = current;
    const level = receiptLevel(analysis, binding);
    ui.dashboard.hidden = false;
    ui.status.className = `receipt-status receipt-status-${level.key}`;
    ui.statusTitle.textContent = level.label;
    ui.statusCopy.textContent = level.copy;
    ui.binding.textContent = binding ? `SOURCE SHA-256 ${binding.source_sha256} · ${binding.source_path}` : `LOCAL SHA-256 ${hash} · not source-bound`;
    clearChildren(ui.summary);
    ui.summary.append(
      summaryCard("Artifact", `${analysis.result.n_scenarios || "—"} × ${analysis.result.n_repeats || "—"}`, `${analysis.rows.length} trial rows`),
      summaryCard("Hard integrity", `${analysis.hard.length - analysis.hardFailures}/${analysis.hard.length}`, analysis.hardFailures ? "gaps found" : "checks passed"),
      summaryCard("Provider errors", String(analysis.providerErrors), "retained, not hidden"),
      summaryCard("Recorded cost", formatMoney(analysis.result.total_cost_usd), `${formatNumber(analysis.result.p50_latency_s, 3)}s p50 latency`),
    );
    renderCheckList(ui.hardList, analysis.hard);
    renderCheckList(ui.disclosureList, analysis.disclosures);
    renderMetrics(analysis);
    renderWorstTrials(analysis);
    renderProvenance(analysis.result);
    ui.privacy.textContent = privacyFindings.length
      ? `Local scan flagged ${privacyFindings.length} ${privacyFindings.length === 1 ? "category" : "categories"}: ${privacyFindings.join(", ")}. Nothing was uploaded. Aggregate exports are locked until the source is redacted.`
      : "Local scan found no likely credentials or common personal identifiers. Nothing was uploaded; exported receipts still exclude trial details.";
    setLinks(binding);
    ui.fileName.textContent = fileName;
    ui.clear.hidden = false;
    const exportSafe = privacyFindings.length === 0;
    ui.downloadJson.disabled = !exportSafe;
    ui.downloadCard.disabled = !exportSafe;
    ui.copySummary.disabled = !exportSafe;
    ui.actionStatus.textContent = exportSafe ? "Inspection complete. No file data left this tab." : "Inspection complete. Redact the flagged source data to unlock aggregate exports.";
    ui.dashboard.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  }

  async function inspectText(text, fileName, binding = null) {
    ui.actionStatus.textContent = "Inspecting locally…";
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch (error) {
      renderUnreadable(fileName, error.message);
      return;
    }
    const hash = await sha256(text);
    const analysis = inspectArtifact(parsed);
    state.inspection = { analysis, binding, fileName, hash, privacyFindings: scanPrivacy(text) };
    renderInspection();
  }

  function renderUnreadable(fileName, errorMessage) {
    state.inspection = null;
    ui.dashboard.hidden = false;
    ui.status.className = "receipt-status receipt-status-unreadable";
    ui.statusTitle.textContent = "UNREADABLE";
    ui.statusCopy.textContent = "The input is not valid JSON, so no integrity claim can be made.";
    ui.binding.textContent = `${fileName} · ${errorMessage}`;
    [ui.summary, ui.hardList, ui.disclosureList, ui.metrics, ui.worst, ui.provenance].forEach(clearChildren);
    ui.gap.hidden = true;
    ui.privacy.textContent = "Parsing stopped locally. No content was uploaded or persisted.";
    setLinks(null);
    ui.clear.hidden = false;
    ui.downloadJson.disabled = true;
    ui.downloadCard.disabled = true;
    ui.copySummary.disabled = true;
    ui.actionStatus.textContent = "Fix the JSON syntax and inspect it again.";
  }

  async function handleFile(file) {
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      ui.actionStatus.textContent = "That file is over the 12 MB local inspection limit.";
      return;
    }
    const text = await file.text();
    await inspectText(text, file.name);
  }

  function aggregateReceipt() {
    const { analysis, binding, fileName, hash, privacyFindings } = state.inspection;
    return {
      schema_version: RECEIPT_SCHEMA,
      generated_at: new Date().toISOString(),
      generator: "AAU Receipt Lab / browser-local",
      claim_level: receiptLevel(analysis, binding).key,
      limitations: [
        "Structural coherence is not domain validation, regulator approval, production certification, or proof of correctness.",
        "Source binding identifies a committed artifact; it is not independent reproduction.",
        "No universal score is calculated because exactness, completion, safety, cost, and latency answer different questions.",
        "This aggregate export intentionally excludes scenario text, tool payloads, reasoning, and per-trial details.",
      ],
      input: {
        file_name: fileName,
        sha256: hash,
        source_binding: binding ? {
          source_path: binding.source_path,
          source_sha256: binding.source_sha256,
          lab_path: binding.lab_path,
          expected_finding: binding.expected_finding,
        } : null,
      },
      identity: {
        backend: analysis.result.backend,
        model: analysis.result.model,
        arm: analysis.result.arm ?? null,
        variant: analysis.result.variant ?? null,
        scoring_revision: analysis.result.scoring_revision ?? null,
        provenance: publicProvenance(analysis.result.provenance),
      },
      coverage: {
        n_scenarios: analysis.result.n_scenarios,
        n_repeats: analysis.result.n_repeats,
        trial_rows: analysis.rows.length,
        provider_error_trials: analysis.providerErrors,
      },
      selected_dimensions: analysis.dimensions,
      published_aggregates: {
        metric_means: analysis.result.metric_means,
        metric_ci95: analysis.result.metric_ci95,
        mean_cost_per_scenario_usd: analysis.result.mean_cost_per_scenario_usd,
        total_cost_usd: analysis.result.total_cost_usd,
        p50_latency_s: analysis.result.p50_latency_s,
      },
      recomputed_aggregates: {
        metric_means: analysis.recomputedMeans,
        mean_cost_per_trial_usd: analysis.recomputedMeanCost,
        total_cost_usd: analysis.recomputedCost,
        median_latency_s: analysis.recomputedMedian,
      },
      integrity_checks: analysis.hard,
      disclosure_findings: analysis.disclosures,
      local_privacy_scan: {
        flagged_categories: privacyFindings,
        raw_values_included: false,
      },
    };
  }

  function publicProvenance(provenance) {
    if (!object(provenance)) return null;
    const allowed = ["generated_at", "harness_version", "python", "platform", "requested_model", "served_model", "served_differs_from_requested", "model_pinned"];
    return Object.fromEntries(allowed.filter((key) => key in provenance).map((key) => [key, provenance[key]]));
  }

  function download(name, content, type) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function escapeXml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[character]);
  }

  function makeCard() {
    const receipt = aggregateReceipt();
    const analysis = state.inspection.analysis;
    const level = receiptLevel(analysis, state.inspection.binding);
    const dimensions = Object.values(analysis.dimensions).slice(0, 3);
    const dimensionRows = dimensions.map((dimension, index) => `<text x="92" y="${432 + index * 57}" class="metric-label">${escapeXml(dimension.label.toUpperCase())}</text><text x="644" y="${432 + index * 57}" class="metric-value" text-anchor="end">${escapeXml(formatMetric(dimension.display))}</text><rect x="680" y="${411 + index * 57}" width="382" height="18" fill="#19232c"/><rect x="680" y="${411 + index * 57}" width="${dimension.display >= 0 && dimension.display <= 1 ? 382 * dimension.display : 0}" height="18" fill="#75e6ff"/>`).join("");
    return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-labelledby="title desc"><title id="title">AAU evaluation receipt: ${escapeXml(level.label)}</title><desc id="desc">Aggregate-only local inspection receipt.</desc><rect width="1200" height="630" fill="#070b10"/><path d="M0 72H1200M775 72V630" stroke="#3d4b55"/><text x="58" y="45" class="micro cyan">AAU / EVALUATION RECEIPT / AGGREGATE ONLY</text><text x="1142" y="45" class="micro" text-anchor="end">NO UNIVERSAL SCORE</text><text x="61" y="158" class="headline">${escapeXml(level.label)}</text><text x="63" y="207" class="copy">${analysis.hard.length - analysis.hardFailures}/${analysis.hard.length} hard checks · ${analysis.rows.length} trials · ${analysis.providerErrors} provider errors</text><text x="63" y="249" class="micro">MODEL</text><text x="63" y="278" class="model">${escapeXml(String(analysis.result.model || "not declared").slice(0, 63))}</text><text x="63" y="335" class="micro">SELECTED DIMENSIONS — DISTINCT, NOT COMPOSITED</text>${dimensionRows}<g transform="translate(817 125)"><text class="micro cyan">EVIDENCE LADDER</text><text y="57" class="step">01  INTEGRITY</text><text y="98" class="step">02  STRUCTURE</text><text y="139" class="step">03  SOURCE BINDING</text><text y="180" class="step">04  REPRODUCTION</text><rect y="231" width="325" height="124" fill="#10171e" stroke="#3d4b55"/><text x="24" y="268" class="micro">INPUT SHA-256</text><text x="24" y="299" class="hash">${escapeXml(receipt.input.sha256.slice(0, 24))}</text><text x="24" y="326" class="hash">${escapeXml(receipt.input.sha256.slice(24, 48))}</text><text x="24" y="353" class="hash">${escapeXml(receipt.input.sha256.slice(48))}</text><text y="414" class="tiny">STRUCTURE ≠ DOMAIN TRUTH ≠ INDEPENDENT RERUN</text></g><style>text{font-family:Inter,system-ui,sans-serif;fill:#f4f2eb}.micro{font:800 12px ui-monospace,monospace;letter-spacing:1.3px;fill:#9eabb4}.cyan{fill:#75e6ff}.headline{font-size:43px;font-weight:950;letter-spacing:-2px}.copy{font-size:18px;fill:#b8c3cb}.model{font:800 22px ui-monospace,monospace}.metric-label{font:850 16px ui-monospace,monospace;fill:#b8c3cb}.metric-value{font:950 23px ui-monospace,monospace;fill:#ffdc67}.step{font:850 17px ui-monospace,monospace}.hash{font:700 13px ui-monospace,monospace;fill:#b69cff}.tiny{font:750 10px ui-monospace,monospace;fill:#9eabb4;letter-spacing:.6px}</style></svg>`;
  }

  function summaryText() {
    const { analysis, binding, hash } = state.inspection;
    const level = receiptLevel(analysis, binding);
    const dimensions = Object.values(analysis.dimensions).map((dimension) => `${dimension.label}: ${formatMetric(dimension.display)} (${dimension.metric}${dimension.inverted ? ", inverted risk display" : ""})`).join(" · ");
    return `AAU Receipt Lab — ${level.label}\n${analysis.hard.length - analysis.hardFailures}/${analysis.hard.length} hard integrity checks passed · ${analysis.rows.length} trials · ${analysis.providerErrors} provider errors\n${dimensions || "No recognized headline dimensions"}\nSHA-256: ${hash}\n${binding ? `Source-bound: ${binding.source_path}` : "Local artifact; source not bound"}\nStructural coherence is not domain validation or independent reproduction.\nhttps://immu4989.github.io/awesome-agentic-usecases/#receipt-lab`;
  }

  function reset() {
    state.inspection = null;
    ui.dashboard.hidden = true;
    ui.fileInput.value = "";
    ui.paste.value = "";
    ui.fileName.textContent = "No artifact selected";
    ui.clear.hidden = true;
    ui.actionStatus.textContent = "Ready for a local file, pasted JSON, or source-bound example.";
  }

  function renderSamples() {
    clearChildren(ui.samples);
    for (const sample of state.contract.samples) {
      const button = element("button", "receipt-sample");
      button.type = "button";
      const meta = element("span", "", `${sample.industry} / ${sample.result.results.length} trials`);
      const title = element("b", "", sample.label);
      const story = element("p", "", sample.story);
      const finding = element("small", "", `EXPECTED OPEN QUESTION / ${sample.expected_finding.replaceAll("-", " ")}`);
      button.append(meta, title, story, finding);
      button.addEventListener("click", async () => {
        const analysis = inspectArtifact(sample.result);
        state.inspection = { analysis, binding: sample, fileName: sample.source_path.split("/").pop(), hash: sample.source_sha256, privacyFindings: [] };
        renderInspection();
      });
      ui.samples.append(button);
    }
  }

  async function init() {
    try {
      const response = await fetch(DATA_URL);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      state.contract = await response.json();
      ui.artifactCount.textContent = String(state.contract.stats.result_artifacts);
      ui.hardCount.textContent = String(state.contract.stats.hard_checks);
      ui.disclosureCount.textContent = String(state.contract.stats.disclosure_checks);
      renderSamples();
      ui.actionStatus.textContent = "Ready for a local file, pasted JSON, or source-bound example.";
    } catch (error) {
      ui.actionStatus.textContent = `Receipt contract could not load: ${error.message}`;
      ui.fileButton.disabled = true;
      ui.inspectPaste.disabled = true;
    }
  }

  ui.fileButton.addEventListener("click", () => ui.fileInput.click());
  ui.fileInput.addEventListener("change", () => handleFile(ui.fileInput.files[0]));
  ui.inspectPaste.addEventListener("click", () => {
    const text = ui.paste.value.trim();
    if (!text) {
      ui.actionStatus.textContent = "Paste an eval JSON object first.";
      return;
    }
    if (new Blob([text]).size > MAX_FILE_BYTES) {
      ui.actionStatus.textContent = "That pasted artifact is over the 12 MB local inspection limit.";
      return;
    }
    inspectText(text, "pasted-eval.json");
  });
  ["dragenter", "dragover"].forEach((eventName) => ui.drop.addEventListener(eventName, (event) => {
    event.preventDefault();
    ui.drop.classList.add("is-dragging");
  }));
  ["dragleave", "drop"].forEach((eventName) => ui.drop.addEventListener(eventName, (event) => {
    event.preventDefault();
    ui.drop.classList.remove("is-dragging");
  }));
  ui.drop.addEventListener("drop", (event) => handleFile(event.dataTransfer.files[0]));
  ui.drop.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      ui.fileInput.click();
    }
  });
  ui.clear.addEventListener("click", reset);
  ui.downloadJson.addEventListener("click", () => {
    download("aau-aggregate-receipt.json", `${JSON.stringify(aggregateReceipt(), null, 2)}\n`, "application/json");
    ui.actionStatus.textContent = "Aggregate JSON receipt downloaded; trial details were excluded.";
  });
  ui.downloadCard.addEventListener("click", () => {
    download("aau-receipt-card.svg", makeCard(), "image/svg+xml");
    ui.actionStatus.textContent = "Aggregate SVG receipt card downloaded.";
  });
  ui.copySummary.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(summaryText());
      ui.actionStatus.textContent = "Aggregate inspection summary copied.";
    } catch {
      ui.actionStatus.textContent = "Clipboard access was unavailable; use the JSON receipt instead.";
    }
  });

  init();
})();
