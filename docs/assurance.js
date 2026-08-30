(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const text = (id, value) => {
    const node = byId(id);
    if (node) node.textContent = String(value);
  };
  const labels = {
    planned_events_not_observed: "Outside adapter event is planned, not observed",
    no_held_out_material: "Public reference material is revealed, not held out",
    no_observed_independent_reproduction: "No outside independent reproduction observed",
  };

  function renderStages(stages) {
    const target = byId("paa-stages");
    if (!target) return;
    target.replaceChildren();
    stages.forEach((stage) => {
      const card = document.createElement("article");
      const detail = stage.detail;
      const measurement = detail.block_count
        ? `${detail.block_count} Blocks`
        : detail.observed_event_ids
          ? `${detail.observed_event_ids.length} observed / ${detail.planned_event_ids.length} planned`
          : detail.reporting_output_count
            ? `${detail.reporting_output_count} outputs`
            : `${detail.stakeholder_count} stakeholder groups`;
      const number = document.createElement("span");
      number.textContent = stage.number;
      const title = document.createElement("h4");
      title.textContent = stage.title;
      const value = document.createElement("p");
      value.textContent = measurement;
      card.append(number, title, value);
      target.append(card);
    });
  }

  function renderReasons(rows) {
    const target = byId("paa-reasons");
    if (!target) return;
    target.replaceChildren();
    rows.forEach((row) => {
      const item = document.createElement("li");
      const code = document.createElement("code");
      code.textContent = row.code;
      const count = document.createElement("span");
      count.textContent = `${row.count} exact ${row.count === 1 ? "fixture" : "fixtures"}`;
      item.append(code, count);
      target.append(item);
    });
  }

  function renderGaps(gaps) {
    const target = byId("paa-gaps");
    if (!target) return;
    target.replaceChildren();
    gaps.forEach((gap) => {
      const item = document.createElement("li");
      item.textContent = labels[gap] || gap.replaceAll("_", " ");
      target.append(item);
    });
  }

  function renderRoutes(routes) {
    const target = byId("paa-routes");
    if (!target) return;
    target.replaceChildren();
    routes.forEach((route) => {
      const link = document.createElement("a");
      link.href = route.href;
      link.textContent = `${route.label} ↗`;
      target.append(link);
    });
  }

  function checkEnvelope(value) {
    const checks = [];
    const add = (name, pass, detail) => checks.push({ name, pass: Boolean(pass), detail });
    add("Version", value?.envelope_version === "aau-agent-assurance-envelope/0.1", "Exact 0.1 envelope contract");
    add(
      "Public fixture boundary",
      value?.classification?.data === "synthetic" && value?.classification?.live_system === false && value?.classification?.test_credentials_only === true,
      "Synthetic data, no live system, test credentials only",
    );
    add(
      "Named subject",
      typeof value?.subject?.agent_id === "string" && typeof value?.subject?.operator_ref === "string" && /^spiffe:\/\//.test(value?.subject?.workload_identity?.identifier || ""),
      "Agent, operator, and workload identity remain separate",
    );
    const issued = Date.parse(value?.issued_at);
    const expires = Date.parse(value?.expires_at);
    const validFrom = Date.parse(value?.authority?.valid_from);
    const validUntil = Date.parse(value?.authority?.valid_until);
    add("Nested time bounds", Number.isFinite(issued) && Number.isFinite(expires) && Number.isFinite(validFrom) && Number.isFinite(validUntil) && issued < validFrom && validFrom < validUntil && validUntil <= expires, "Authority is a non-empty subset of envelope validity");
    add(
      "Live authority fields",
      typeof value?.authority?.lease_id === "string" && typeof value?.authority?.task_id === "string" && Number.isInteger(value?.authority?.policy_epoch) && ["active", "revoked"].includes(value?.authority?.revocation_state),
      "Lease, task, epoch, and revocation state are explicit",
    );
    add(
      "Exact actions",
      Array.isArray(value?.authority?.allowed_actions) && value.authority.allowed_actions.length > 0 && value.authority.allowed_actions.every((row) => ["mcp", "a2a"].includes(row.protocol) && row.operation && row.resource && row.destination),
      "Protocol, operation, resource, and destination are jointly bounded",
    );
    add(
      "Protocol guards",
      value?.protocols?.mcp?.token_passthrough_forbidden === true && value?.protocols?.a2a?.authorization_per_request === true && /^[0-9a-f]{64}$/.test(value?.protocols?.a2a?.agent_card_sha256 || ""),
      "MCP passthrough denied; A2A authorization and card binding required",
    );
    add(
      "Claim boundary",
      value?.claim_boundaries?.not_certification === true && value?.claim_boundaries?.production_identity_not_verified === true && value?.claim_boundaries?.no_live_action_authorized === true,
      "No certification, production identity, or live authorization claim",
    );
    return checks;
  }

  function renderChecks(checks) {
    const target = byId("paa-inspector-checks");
    if (!target) return;
    target.replaceChildren();
    checks.forEach((check) => {
      const row = document.createElement("article");
      row.className = check.pass ? "pass" : "hold";
      const state = document.createElement("b");
      state.textContent = check.pass ? "PASS" : "HOLD";
      const copy = document.createElement("div");
      const name = document.createElement("span");
      name.textContent = check.name;
      const detail = document.createElement("small");
      detail.textContent = check.detail;
      copy.append(name, detail);
      row.append(state, copy);
      target.append(row);
    });
    const passed = checks.filter((check) => check.pass).length;
    text("paa-inspector-status", `${passed}/${checks.length} structural gates passed · production identity not verified`);
  }

  async function inspectFile(file) {
    if (!file) return;
    try {
      if (file.size > 1_000_000) throw new Error("File exceeds the 1 MB local-inspection limit.");
      const value = JSON.parse(await file.text());
      if (!value || Array.isArray(value) || typeof value !== "object") throw new Error("JSON root must be an object.");
      renderChecks(checkEnvelope(value));
    } catch (error) {
      text("paa-inspector-status", `HOLD · ${error.message}`);
      byId("paa-inspector-checks")?.replaceChildren();
    }
  }

  async function start() {
    const section = byId("agent-assurance");
    if (!section) return;
    try {
      const response = await fetch("assurance-data.json?v=3", { cache: "no-store" });
      if (!response.ok) throw new Error(`data request returned ${response.status}`);
      const data = await response.json();
      text("paa-case-count", data.suite.case_count);
      text("paa-exact-count", `${data.suite.exact_count}/${data.suite.case_count}`);
      text("paa-twin-count", data.suite.clean_twin_allow_count);
      text("paa-block-count", data.tevva.block_count);
      text("paa-identity-state", data.envelope.production_identity_verified ? "VERIFIED" : "NOT VERIFIED");
      text("paa-mcp-revision", data.mcp_2026.protocol_revision);
      text("paa-mcp-exact", `${data.mcp_2026.exact_count}/${data.mcp_2026.case_count}`);
      text("paa-mcp-clean", data.mcp_2026.clean_twin_count);
      text("paa-mcp-unsafe", data.mcp_2026.unsafe_allow_count);
      text("paa-mcp-blocks", data.mcp_2026.legitimate_block_count);
      text("paa-a2a-revision", `${data.a2a_1.protocol_revision} @ ${data.a2a_1.specification_release}`);
      text("paa-a2a-exact", `${data.a2a_1.exact_count}/${data.a2a_1.case_count}`);
      text("paa-a2a-clean", data.a2a_1.clean_twin_count);
      text("paa-a2a-unsafe", data.a2a_1.unsafe_allow_count);
      text("paa-a2a-blocks", data.a2a_1.legitimate_block_count);
      text("paa-relay-a2a", data.authority_relay.a2a_revision);
      text("paa-relay-mcp", data.authority_relay.mcp_revision);
      text("paa-relay-exact", `${data.authority_relay.exact_count}/${data.authority_relay.case_count}`);
      text("paa-relay-clean", data.authority_relay.clean_twin_count);
      text("paa-relay-unsafe", data.authority_relay.unsafe_allow_count);
      text("paa-relay-blocks", data.authority_relay.legitimate_block_count);
      text("paa-chain", data.suite.result_chain_head_sha256.slice(0, 16));
      text("paa-deadline", data.tevva.comment_deadline);
      renderStages(data.tevva.stages);
      renderReasons(data.suite.reason_codes);
      renderGaps(data.tevva.visible_gaps);
      renderRoutes(data.routes);
      section.dataset.ready = "true";
    } catch (error) {
      section.dataset.ready = "false";
      text("paa-data-status", `Evidence data unavailable: ${error.message}`);
    }
    byId("paa-envelope-file")?.addEventListener("change", (event) => inspectFile(event.target.files?.[0]));
  }

  start();
})();
