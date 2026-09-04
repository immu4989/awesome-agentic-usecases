(() => {
  "use strict";

  const root = document.querySelector("#agent-security-commons");
  if (!root) return;

  const percent = (value) => `${Math.round(Number(value || 0) * 100)}%`;
  const byId = (id) => document.getElementById(id);
  const makeText = (tag, value) => {
    const node = document.createElement(tag);
    node.textContent = String(value ?? "");
    return node;
  };

  function renderProof(data) {
    byId("asc-event-count").textContent = data.runtime.event_count;
    byId("asc-adapter-count").textContent = data.runtime.adapter_count;
    byId("asc-kit-count").textContent = data.defender_kits.length;
    byId("asc-incident-count").textContent = data.incident.regression_count;
    byId("asc-side-effect-case-count").textContent = data.side_effects.summary.case_count;
  }

  function renderSideEffects(data) {
    const summary = data.side_effects.summary;
    byId("asc-effect-event-count").textContent = summary.event_count;
    byId("asc-effect-duplicate-count").textContent = summary.duplicate_effects_prevented;
    byId("asc-effect-reconcile-count").textContent = summary.reconciliation_count;
    byId("asc-effect-conflict-count").textContent = summary.key_conflicts_blocked;
    byId("asc-effect-breach-count").textContent = summary.at_most_one_breach_count;
    byId("asc-effect-receipt").textContent = data.side_effects.receipt_sha256.slice(0, 12);
    const conformance = data.side_effects.conformance;
    byId("asc-effect-conformance-exact").textContent = `${conformance.summary.exact_outcome_count}/${conformance.summary.event_count}`;
    byId("asc-effect-conformance-unsafe").textContent = conformance.summary.unsafe_effect_outcome_count;
    byId("asc-effect-conformance-retry").textContent = conformance.summary.unknown_retry_violation_count;
    byId("asc-effect-conformance-receipt").textContent = conformance.receipt_sha256.slice(0, 12);
    const crashLab = data.side_effects.crash_lab;
    byId("asc-effect-crash-exact").textContent = `${crashLab.summary.exact_count}/${crashLab.summary.case_count}`;
    byId("asc-effect-crash-points").textContent = crashLab.summary.crash_point_count;
    byId("asc-effect-crash-unsafe").textContent = crashLab.summary.unsafe_resume_count;
    byId("asc-effect-crash-unknown").textContent = crashLab.summary.unresolved_effect_count;
    const raceLab = data.side_effects.race_lab;
    byId("asc-effect-race-exact").textContent = `${raceLab.summary.exact_count}/${raceLab.summary.case_count}`;
    byId("asc-effect-race-attempts").textContent = raceLab.summary.attempt_count;
    byId("asc-effect-race-duplicates").textContent = raceLab.summary.duplicate_effect_count;
    byId("asc-effect-race-missing").textContent = raceLab.summary.missing_effect_count;
    const matrix = data.side_effects.matrix;
    byId("asc-effect-matrix-exact").textContent = `${matrix.aggregate.exact_count}/${matrix.aggregate.checked_outcome_count}`;
    byId("asc-effect-matrix-components").textContent = matrix.component_count;
    byId("asc-effect-matrix-unsafe").textContent = matrix.aggregate.unsafe_count;
    byId("asc-effect-matrix-artifacts").textContent = matrix.adapter_artifacts.length;
    byId("asc-effect-matrix-hash").textContent = matrix.matrix_sha256.slice(0, 12);
    byId("asc-effect-matrix-boundary").textContent = `${matrix.coverage_binding.tool_id} / ${matrix.coverage_binding.operation}`;
    const binding = data.side_effects.release_binding;
    byId("asc-effect-binding-count").textContent = `${binding.fully_bound_consequential_operation_count}/${binding.consequential_operation_count}`;
    byId("asc-effect-binding-release").textContent = binding.release_id;
    byId("asc-effect-binding-holds").textContent = binding.finding_count;
    byId("asc-effect-binding-hash").textContent = binding.receipt_sha256.slice(0, 12);
  }

  function renderKits(data) {
    const target = byId("asc-kits");
    target.replaceChildren();
    data.defender_kits.forEach((kit, index) => {
      const link = document.createElement("a");
      link.className = "asc-kit";
      link.href = kit.path;
      link.append(makeText("span", `0${index + 1} / ${kit.sector}`));
      link.append(makeText("h4", kit.title));
      link.append(makeText("p", kit.beneficiary));
      const footer = document.createElement("footer");
      footer.append(makeText("b", `${kit.exercise_count} exercises`));
      footer.append(makeText("i", `${kit.gap_count} visible gap${kit.gap_count === 1 ? "" : "s"}`));
      link.append(footer);
      target.append(link);
    });
  }

  function renderArm(data, armId) {
    const arm = data.controls.arms.find((item) => item.arm_id === armId) || data.controls.arms[0];
    document.querySelectorAll("[data-asc-arm]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.ascArm === arm.arm_id));
    });
    byId("asc-arm-title").textContent = arm.title;
    byId("asc-arm-controls").textContent = `${arm.active_control_count}/${data.controls.control_count} controls`;
    const measurements = [
      ["asc-unsafe", arm.measurements.unsafe_allow_rate, "Unsafe allow rate", true],
      ["asc-exact", arm.measurements.exact_outcome, "Exact outcomes", false],
      ["asc-legitimate", arm.measurements.legitimate_allow_preservation, "Legitimate actions kept", false],
    ];
    measurements.forEach(([id, value, label, invert]) => {
      const node = byId(id);
      node.querySelector("b").textContent = percent(value);
      node.querySelector("small").textContent = label;
      node.querySelector("i").style.width = percent(invert ? 1 - value : value);
    });
    const unsafe = byId("asc-unsafe-cases");
    unsafe.textContent = arm.unsafe_cases.length
      ? `${arm.unsafe_cases.length} matched failures remain unsafe allows: ${arm.unsafe_cases.join(", ")}.`
      : "No unsafe allow appears in this transparent synthetic arm; this is not a production control claim.";
  }

  function renderArms(data) {
    const list = byId("asc-arm-list");
    list.replaceChildren();
    data.controls.arms.forEach((arm) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.ascArm = arm.arm_id;
      button.setAttribute("aria-pressed", "false");
      button.append(makeText("b", arm.title));
      button.append(makeText("small", `${arm.active_control_count} active controls`));
      button.addEventListener("click", () => renderArm(data, arm.arm_id));
      list.append(button);
    });
    renderArm(data, data.controls.arms[0].arm_id);
  }

  function renderPilot(data) {
    byId("asc-pilot-level").textContent = data.pilot.evidence_level;
    byId("asc-pilot-gaps").textContent = `${data.pilot.visible_gaps.length} evidence gaps remain visible: ${data.pilot.visible_gaps.join(", ").replaceAll("_", " ")}.`;
  }

  fetch("agent-security-data.json?v=9", { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((data) => {
      renderProof(data);
      renderSideEffects(data);
      renderKits(data);
      renderArms(data);
      renderPilot(data);
      root.dataset.ready = "true";
    })
    .catch(() => {
      const fallback = document.createElement("p");
      fallback.className = "asc-fallback";
      fallback.textContent = "The interactive evidence summary could not load. Every CLI, schema, test, and reference artifact remains available in the GitHub repository.";
      byId("asc-arm-panel").prepend(fallback);
    });
})();
