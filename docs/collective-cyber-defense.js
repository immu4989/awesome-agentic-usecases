(() => {
  "use strict";

  const root = document.querySelector("#collective-cyber-defense");
  if (!root) return;
  const byId = (id) => document.getElementById(id);
  const text = (tag, value, className) => {
    const node = document.createElement(tag);
    node.textContent = String(value ?? "");
    if (className) node.className = className;
    return node;
  };
  let siteData;
  let currentPlan;

  function renderProof(data) {
    byId("ccd-fix-count").textContent = data.fixes.length;
    byId("ccd-event-count").textContent = data.containment.event_count;
    byId("ccd-task-count").textContent = data.benchmark.summary.task_count;
    byId("ccd-artifact-count").textContent = data.mesh.record_count;
    byId("ccd-independent-count").textContent = data.outcomes.summary.independent_reproduction_count;
  }

  function renderRoutes(data) {
    const target = byId("ccd-routes");
    target.replaceChildren();
    data.routes.forEach((route, index) => {
      const card = document.createElement("a");
      card.className = "ccd-route";
      card.href = route.href;
      card.append(text("span", `0${index + 1} / OPEN MODULE`));
      card.append(text("h4", route.title));
      card.append(text("p", route.description));
      target.append(card);
    });
  }

  function renderFixes(data) {
    const target = byId("ccd-fixes");
    target.replaceChildren();
    data.fixes.forEach((fix) => {
      const card = document.createElement("a");
      card.className = "ccd-fix";
      card.href = fix.path;
      const header = document.createElement("header");
      header.append(text("span", fix.change_kind));
      header.append(text("b", fix.evidence_level.replaceAll("_", " ")));
      card.append(header);
      card.append(text("h4", fix.title));
      const footer = document.createElement("footer");
      footer.append(text("span", `${fix.case_count} cases`));
      footer.append(text("span", `${Math.round(fix.after_pass_rate * 100)}% reference after-pass`));
      card.append(footer);
      target.append(card);
    });
  }

  function renderControls(data) {
    const values = [
      ["ccd-pause-latency", `${data.containment.pause_latency_ms} ms`],
      ["ccd-revoke-latency", `${data.containment.revocation_latency_ms} ms`],
      ["ccd-child-latency", `${data.containment.child_revocation_latency_ms} ms`],
      ["ccd-queue-latency", `${data.containment.queue_cancel_latency_ms} ms`],
      ["ccd-breach-count", data.containment.containment_breach_count],
    ];
    values.forEach(([id, value]) => { byId(id).textContent = value; });
    const families = byId("ccd-families");
    families.replaceChildren();
    data.benchmark.families.forEach((family) => {
      const row = document.createElement("div");
      row.className = "ccd-family";
      row.append(text("span", family.family.replaceAll("_", " ")));
      row.append(text("b", `${family.task_count} safe tasks`));
      families.append(row);
    });
  }

  function continuityPass(test) {
    return Boolean(test && test.service_available && test.rollback_ready &&
      test.observed_interruption_minutes <= test.max_interruption_minutes);
  }

  function routeFor(applicability, patchability) {
    if (applicability === "unknown") return "investigate";
    if (applicability === "not_affected") return "no_action";
    return patchability === "now" ? "patch" : "compensating_control";
  }

  function assessLocalCampaign(campaign) {
    if (!campaign || !Array.isArray(campaign.assets) || !Array.isArray(campaign.vulnerabilities) ||
        !Array.isArray(campaign.decisions) || !Array.isArray(campaign.continuity_tests)) {
      throw new Error("Expected an AAU campaign with assets, vulnerabilities, decisions, and continuity_tests arrays.");
    }
    if (campaign.assets.length > 500 || campaign.decisions.length > 1000) {
      throw new Error("This browser workbench accepts at most 500 assets and 1,000 decisions.");
    }
    const assets = new Map(campaign.assets.map((item) => [item.asset_id, item]));
    const tests = new Map(campaign.continuity_tests.map((item) => [item.test_id, item]));
    const vulnerabilities = new Map(campaign.vulnerabilities.map((item) => [item.vulnerability_id, item]));
    const rows = campaign.decisions.map((decision) => {
      const asset = assets.get(decision.asset_id);
      const vulnerability = vulnerabilities.get(decision.vulnerability_id);
      if (!asset || !vulnerability) throw new Error("A decision references an unknown asset or vulnerability.");
      const recommended = routeFor(decision.applicability, asset.patchability);
      const needsContinuity = ["patch", "compensating_control"].includes(decision.route);
      const needsApproval = ["patch", "compensating_control", "no_action"].includes(decision.route);
      const continuity = needsContinuity ? continuityPass(tests.get(decision.continuity_test_id)) : null;
      const evidence = Array.isArray(decision.evidence_refs) && decision.evidence_refs.length > 0;
      const pass = decision.route === recommended && evidence && (!needsApproval || decision.human_approved) && (!needsContinuity || continuity);
      return {
        vulnerability_id: decision.vulnerability_id,
        asset_id: decision.asset_id,
        known_exploited: Boolean(vulnerability.known_exploited),
        declared_route: decision.route,
        recommended_route: recommended,
        continuity_pass: continuity,
        human_approved: Boolean(decision.human_approved),
        gate_pass: pass,
      };
    });
    return {
      campaign_id: campaign.campaign_id || "local-campaign",
      evidence_label: "browser-local-unverified",
      rows,
      summary: {
        assets: assets.size,
        decisions: rows.length,
        known_exploited: rows.filter((row) => row.known_exploited).length,
        ready: rows.filter((row) => row.gate_pass).length,
      },
      boundary: { no_upload: true, no_scan: true, no_change: true, not_risk_assessment: true },
    };
  }

  function renderPlan(plan) {
    currentPlan = plan;
    const summary = byId("ccd-plan-summary");
    summary.replaceChildren();
    [
      [plan.summary.assets, "assets"], [plan.summary.decisions, "decisions"],
      [plan.summary.known_exploited, "known-exploited routes"], [plan.summary.ready, "gates ready"],
    ].forEach(([value, label]) => {
      const cell = document.createElement("span");
      cell.append(text("b", value));
      cell.append(text("small", label));
      summary.append(cell);
    });
    const body = byId("ccd-plan-body");
    body.replaceChildren();
    plan.rows.forEach((row) => {
      const tr = document.createElement("tr");
      [row.vulnerability_id, row.asset_id, row.declared_route, row.recommended_route].forEach((value) => tr.append(text("td", value)));
      tr.append(text("td", row.continuity_pass === null ? "not required" : row.continuity_pass ? "pass" : "fail", row.continuity_pass === false ? "ccd-fail" : ""));
      tr.append(text("td", row.human_approved ? "recorded" : "not recorded"));
      tr.append(text("td", row.gate_pass ? "READY" : "HOLD", row.gate_pass ? "ccd-pass" : "ccd-fail"));
      body.append(tr);
    });
    byId("ccd-plan-empty").hidden = true;
    byId("ccd-plan-output").hidden = false;
    byId("ccd-download-plan").disabled = false;
    byId("ccd-local-status").textContent = `${plan.campaign_id} assessed inside this tab. No file was transmitted.`;
    byId("ccd-local-status").classList.remove("ccd-error");
  }

  function failPlan(message) {
    byId("ccd-local-status").textContent = message;
    byId("ccd-local-status").classList.add("ccd-error");
  }

  function renderOutcomes(data) {
    byId("ccd-mesh-copy").textContent = `${data.mesh.record_count} public-safe artifacts expose hashes, evidence levels, bounded measurements, and control fingerprints across four interoperable families.`;
    const levels = byId("ccd-levels");
    levels.replaceChildren();
    Object.entries(data.outcomes.summary.evidence_level_counts).forEach(([level, count]) => {
      levels.append(text("span", `${level.replaceAll("_", " ")}: ${count}`));
    });
    byId("ccd-outcome-gaps").textContent = data.outcomes.visible_gaps.join(" ") || "No declared evidence-level gaps.";
    const sources = byId("ccd-sources");
    sources.replaceChildren();
    data.sources.forEach((source) => {
      const link = text("a", `${source.publisher}: ${source.label} ↗`);
      link.href = source.url;
      sources.append(link);
    });
  }

  byId("ccd-defender-file").addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 1_000_000) return failPlan("Choose a JSON file smaller than 1 MB.");
    const reader = new FileReader();
    reader.onload = () => {
      try { renderPlan(assessLocalCampaign(JSON.parse(reader.result))); }
      catch (error) { failPlan(error.message); }
    };
    reader.onerror = () => failPlan("The browser could not read that local file.");
    reader.readAsText(file);
  });

  byId("ccd-load-example").addEventListener("click", () => {
    if (siteData) renderPlan(assessLocalCampaign(siteData.defender_example));
  });

  byId("ccd-download-plan").addEventListener("click", () => {
    if (!currentPlan) return;
    const blob = new Blob([`${JSON.stringify(currentPlan, null, 2)}\n`], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${currentPlan.campaign_id}-local-plan.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  fetch("collective-cyber-defense-data.json?v=1", { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((data) => {
      siteData = data;
      renderProof(data);
      renderRoutes(data);
      renderFixes(data);
      renderControls(data);
      renderOutcomes(data);
      root.dataset.ready = "true";
    })
    .catch(() => failPlan("The derived reference data could not load. All modules remain available in the GitHub repository."));
})();
