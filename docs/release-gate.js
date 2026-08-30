(() => {
  "use strict";

  const node = (id) => document.getElementById(id);
  const set = (id, value) => { const target = node(id); if (target) target.textContent = String(value); };

  function renderChanges(changes) {
    const target = node("release-change-list");
    if (!target) return;
    target.replaceChildren();
    changes.forEach((change, index) => {
      const row = document.createElement("article");
      const number = document.createElement("span");
      number.textContent = `0${index + 1}`;
      const copy = document.createElement("div");
      const title = document.createElement("b");
      title.textContent = change.component_id.replaceAll("-", " ");
      const detail = document.createElement("small");
      detail.textContent = `${change.kind.replaceAll("_", " ")} → ${change.impact_tags.join(" · ")}`;
      copy.append(title, detail);
      row.append(number, copy);
      target.append(row);
    });
  }

  function renderChallenges(challenges) {
    const target = node("release-challenges");
    if (!target) return;
    target.replaceChildren();
    challenges.forEach((challenge) => {
      const link = document.createElement("a");
      link.href = `https://github.com/immu4989/awesome-agentic-usecases/tree/main/reproduction-challenges/${challenge.path.split("/")[0]}`;
      if (challenge.status === "closed") link.classList.add("is-closed");
      const state = document.createElement("span");
      state.textContent = `${challenge.task_count} HIDDEN-ORACLE TASKS / ${challenge.status}`;
      const title = document.createElement("b");
      title.textContent = challenge.title;
      const action = document.createElement("small");
      action.textContent = challenge.status === "closed"
        ? "Historical artifact · submissions disabled. ↗"
        : "Fork. Run. Submit attested bytes. ↗";
      link.append(state, title, action);
      target.append(link);
    });
  }

  function renderIncidents(entries) {
    const target = node("release-incidents");
    if (!target) return;
    target.replaceChildren();
    entries.forEach((entry) => {
      const row = document.createElement("li");
      const code = document.createElement("code");
      code.textContent = entry.incident_id;
      const copy = document.createElement("span");
      copy.textContent = entry.title;
      const state = document.createElement("b");
      state.textContent = `${entry.severity} · ${entry.status.replaceAll("_", " ")}`;
      row.append(code, copy, state);
      target.append(row);
    });
  }

  function renderBomFindings(findings) {
    const target = node("release-bom-findings");
    if (!target) return;
    target.replaceChildren();
    findings.forEach((finding) => {
      const row = document.createElement("li");
      const code = document.createElement("code");
      code.textContent = finding.code;
      const copy = document.createElement("span");
      copy.textContent = `${finding.subject} · ${finding.detail}`;
      const state = document.createElement("b");
      state.textContent = finding.severity;
      row.append(code, copy, state);
      target.append(row);
    });
  }

  fetch("release-gate-data.json")
    .then((response) => { if (!response.ok) throw new Error("release data unavailable"); return response.json(); })
    .then((data) => {
      const release = data.release;
      set("release-status", release.status.replaceAll("_", " ").toUpperCase());
      set("release-case-proof", `${release.exact_count}/${release.scenario_count}`);
      set("release-change-count", release.changed_components);
      set("release-tag-count", release.impacted_tags.length);
      set("release-oscal-count", `${release.oscal_observations} + ${release.oscal_findings}`);
      set("release-challenge-count", data.reproduction.challenge_count);
      set("release-challenge-inline", data.reproduction.challenge_count);
      set("release-task-count", data.reproduction.task_count);
      set("release-independent-count", data.reproduction.independently_reproduced_count);
      set("release-incident-count", data.incidents.entry_count);
      set("release-export-count", data.incidents.export_count);
      set("release-source-count", data.freshness.source_count);
      set("release-baseline-count", data.freshness.baseline_count);
      set("release-review-due", data.freshness.next_review_due);
      set("release-compat-binding-count", data.freshness.compatibility.binding_count);
      set("release-migration-count", data.freshness.compatibility.migration_required_count);
      const mcp = data.freshness.mcp_alignment;
      set("release-migration-path", `${mcp.evaluated_revision} = ${mcp.source_revision}`);
      set("release-mcp-delta-count", mcp.case_count);
      const a2a = data.freshness.a2a_alignment;
      set("release-a2a-path", `${a2a.evaluated_revision} = ${a2a.source_revision}`);
      set("release-a2a-delta-count", a2a.case_count);
      set("release-data-status", `Evidence-derived · ${data.generated_on} · human identity not verified`);
      renderChanges(release.changes);
      renderChallenges(data.reproduction.challenges);
      renderIncidents(data.incidents.entries);
      set("release-bom-tool-count", data.capability_bom.tool_count);
      set("release-bom-authority-count", data.capability_bom.authority_count);
      set("release-bom-route-count", data.capability_bom.route_count);
      set("release-bom-evidence-count", data.capability_bom.evidence_count);
      set("release-bom-finding-count", data.capability_bom.finding_count);
      set("release-bom-status", data.capability_bom.diff_status.replaceAll("_", " "));
      set("release-bom-cdx", data.capability_bom.cyclonedx_version);
      set("release-bom-granted", data.capability_bom.reduction_plan.summary.granted_operation_count + data.capability_bom.reduction_plan.summary.granted_scope_count);
      set("release-bom-observed", data.capability_bom.reduction_plan.summary.observed_operation_count + data.capability_bom.reduction_plan.summary.observed_scope_count);
      set("release-bom-unobserved", data.capability_bom.reduction_plan.summary.unobserved_operation_count + data.capability_bom.reduction_plan.summary.unobserved_scope_count);
      set("release-bom-auto-removed", data.capability_bom.reduction_plan.summary.automatically_removed_count);
      set("release-bom-next-evidence", data.capability_bom.reduction_plan.next_evidence_count);
      const conformance = data.capability_bom.conformance;
      set("release-bom-conformance-status", conformance.status.replaceAll("_", " "));
      set("release-bom-conformance-exact", `${conformance.exact_count}/${conformance.case_count}`);
      set("release-bom-conformance-clean", conformance.clean_twin_count);
      set("release-bom-conformance-violations", conformance.violation_twin_count);
      set("release-bom-conformance-unsafe", conformance.unsafe_allow_count);
      set("release-bom-conformance-shapes", conformance.shape_count);
      set("release-bom-conformance-blocks", conformance.legitimate_block_count);
      renderBomFindings(data.capability_bom.findings);
    })
    .catch((error) => set("release-data-status", `Evidence view unavailable: ${error.message}`));
})();
