(() => {
  "use strict";

  const STARTER_VERSION = "aau-agent-evidence-starter/1.0";
  const STATUS = "synthetic_onboarding_not_production_validation";
  const ACTION_PINS = Object.freeze({
    checkout: "3d3c42e5aac5ba805825da76410c181273ba90b1",
    setupPython: "ece7cb06caefa5fff74198d8649806c4678c61a1",
    uploadArtifact: "ea165f8d65b6e75b540449e92b4886f43607fa02",
  });
  const FILE_LABEL = "Eleven-file Agent Evidence Starter";
  const encoder = new TextEncoder();
  const byId = (id) => document.getElementById(id);
  const state = { contract: null, step: 0 };

  function canonical(value) {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === "object") {
      return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
    }
    return value;
  }

  function renderJson(value) {
    return `${JSON.stringify(canonical(value), null, 2)}\n`;
  }

  async function sha256(text) {
    const digest = await crypto.subtle.digest("SHA-256", encoder.encode(text));
    return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  }

  function escapeXml(value) {
    return String(value).replace(/[<>&"']/g, (character) => ({
      "<": "&lt;", ">": "&gt;", "&": "&amp;", "\"": "&quot;", "'": "&apos;",
    })[character]);
  }

  function shellQuote(value) {
    return `'${String(value).replaceAll("'", `'\"'\"'`)}'`;
  }

  function pythonLiteral(value) {
    if (value === true) return "True";
    if (value === false) return "False";
    if (value === null) return "None";
    if (typeof value === "string") return JSON.stringify(value);
    if (Array.isArray(value)) return `[${value.map(pythonLiteral).join(", ")}]`;
    if (value && typeof value === "object") {
      return `{${Object.entries(value).map(([key, item]) => `${pythonLiteral(key)}: ${pythonLiteral(item)}`).join(", ")}}`;
    }
    return String(value);
  }

  function selectedTemplate() {
    const selected = document.querySelector('input[name="starter-template"]:checked');
    return state.contract?.templates.find((template) => template.id === selected?.value) || null;
  }

  function outcomeSlug(value) {
    return value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  }

  function values() {
    const template = selectedTemplate();
    return {
      template,
      name: byId("starter-name").value.trim(),
      title: byId("starter-title-input").value.trim(),
      mission: byId("starter-mission").value.trim(),
      humanRole: byId("starter-human-role").value.trim(),
      protectedAction: byId("starter-protected-action").value.trim(),
      outcomes: {
        routine: outcomeSlug(byId("starter-routine-outcome").value),
        human: outcomeSlug(byId("starter-human-outcome").value),
        stop: outcomeSlug(byId("starter-stop-outcome").value),
      },
      adapter: byId("starter-adapter").value,
    };
  }

  function sensitiveFindings(fields) {
    const joined = fields.join("\n");
    const patterns = [
      ["email address", /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i],
      ["U.S. Social Security number", /\b\d{3}[- ]?\d{2}[- ]?\d{4}\b/],
      ["payment card-like number", /\b(?:\d[ -]*?){13,19}\b/],
      ["credential or private key", /(?:api[_ -]?key|access[_ -]?token|client[_ -]?secret|password)\s*[:=]|-----BEGIN [A-Z ]*PRIVATE KEY-----/i],
      ["classified or controlled-data marker", /\b(?:TOP SECRET|SECRET\/\/|CUI\/\/|SOURCE SELECTION INFORMATION)\b/i],
    ];
    return patterns.filter(([, pattern]) => pattern.test(joined)).map(([label]) => label);
  }

  function gates() {
    const current = values();
    const outcomes = Object.values(current.outcomes);
    const sensitive = sensitiveFindings([
      current.title, current.mission, current.humanRole, current.protectedAction, ...outcomes,
    ]);
    return [
      ["Template contract selected", Boolean(current.template)],
      ["Project name is a safe 1–63 character slug", /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(current.name)],
      ["Readable project title declared", current.title.length >= 5],
      ["Concrete mission declared", current.mission.length >= 20],
      ["Accountable human role named", current.humanRole.length >= 3],
      ["Protected human action is explicit", current.protectedAction.length >= 10],
      ["Routine, human, and stop outcomes are unique slugs", outcomes.every((item) => /^[a-z0-9](?:[a-z0-9_]{0,78}[a-z0-9])?$/.test(item)) && new Set(outcomes).size === 3],
      [sensitive.length ? `Sensitive-data scan found: ${sensitive.join(", ")}` : "No common sensitive-data pattern detected", sensitive.length === 0],
      ["Synthetic/public-data attestation accepted", byId("starter-attest-synthetic").checked],
      ["Human-review and receipt-boundary attestations accepted", byId("starter-attest-review").checked && byId("starter-attest-sensitive").checked],
    ];
  }

  function renderValidation() {
    const checks = gates();
    const passed = checks.filter(([, ready]) => ready).length;
    const list = byId("starter-validation-list");
    list.replaceChildren(...checks.map(([label, ready]) => {
      const item = document.createElement("li");
      item.textContent = label;
      item.classList.toggle("is-pass", ready);
      return item;
    }));
    byId("starter-validation-score").textContent = `${passed} / ${checks.length} gates`;
    byId("starter-download").disabled = passed !== checks.length;
    byId("starter-readiness-bar").style.width = `${(passed / checks.length) * 100}%`;
    byId("starter-readiness-copy").textContent = passed === checks.length
      ? `${FILE_LABEL} is ready to generate locally.`
      : `${checks.length - passed} local gate${checks.length - passed === 1 ? "" : "s"} remain.`;
  }

  function renderPreview() {
    const current = values();
    byId("starter-preview-id").textContent = current.name ? current.name.toUpperCase() : "DRAFT";
    byId("starter-preview-title").textContent = current.title || "Your evidence starter";
    byId("starter-preview-mission").textContent = current.mission || "Choose a starter shape to see its evidence story.";
    byId("starter-preview-role").textContent = current.humanRole || "Name the accountable role";
    byId("starter-preview-action").textContent = current.protectedAction || "Name the action software cannot own.";
    byId("starter-preview-adapter").textContent = current.adapter === "http" ? "localhost HTTP endpoint" : "stdin / stdout command";
    byId("starter-preview-outcomes").textContent = Object.values(current.outcomes).filter(Boolean).join(" · ") || "routine · human · stop";
    renderValidation();
  }

  function applyTemplate(template, { projectName = "" } = {}) {
    const radio = document.querySelector(`input[name="starter-template"][value="${template.id}"]`);
    if (radio) radio.checked = true;
    byId("starter-name").value = projectName;
    byId("starter-title-input").value = template.title;
    byId("starter-mission").value = template.mission;
    byId("starter-human-role").value = template.human_role;
    byId("starter-protected-action").value = template.protected_action;
    byId("starter-routine-outcome").value = template.outcomes.routine;
    byId("starter-human-outcome").value = template.outcomes.human;
    byId("starter-stop-outcome").value = template.outcomes.stop;
    renderPreview();
  }

  function showStep(step) {
    state.step = Math.max(0, Math.min(3, step));
    document.querySelectorAll("[data-starter-panel]").forEach((panel) => {
      panel.hidden = Number(panel.dataset.starterPanel) !== state.step;
    });
    document.querySelectorAll("[data-starter-step]").forEach((button) => {
      if (Number(button.dataset.starterStep) === state.step) button.setAttribute("aria-current", "step");
      else button.removeAttribute("aria-current");
    });
    byId("starter-current-step").textContent = String(state.step + 1);
    byId("starter-previous").disabled = state.step === 0;
    byId("starter-next").hidden = state.step === 3;
    renderPreview();
  }

  function currentPanelReady() {
    const panel = document.querySelector(`[data-starter-panel="${state.step}"]`);
    const required = [...panel.querySelectorAll("input[required], textarea[required], select[required]")];
    const invalid = required.find((field) => !field.checkValidity());
    if (state.step === 0 && !selectedTemplate()) {
      byId("starter-action-status").textContent = "Choose a starter shape before continuing.";
      return false;
    }
    if (invalid) {
      invalid.reportValidity();
      return false;
    }
    return true;
  }

  function suiteFor(current) {
    return {
      suite_version: "aau-byo-agent-suite/1.0",
      suite_id: `${current.name}-synthetic-smoke`,
      description: current.mission,
      sharing: {
        classification: "synthetic",
        human_review_complete: true,
        contains_personally_identifiable_information: false,
        contains_procurement_sensitive_information: false,
        contains_controlled_unclassified_information: false,
        contains_classified_information: false,
        contains_secrets_or_credentials: false,
      },
      human_authority: {
        accountable_role: current.humanRole,
        protected_action: current.protectedAction,
      },
      cases: current.template.cases.map((item) => ({
        scenario_id: item.scenario_id,
        input: item.input,
        expected: { outcome: current.outcomes[item.expected_slot] },
        forbidden_actions: item.forbidden_actions,
      })),
    };
  }

  function adapterSource(current) {
    return `#!/usr/bin/env python3
"""Reference stdin/stdout adapter for ${current.name}.

Replace \`\`decide\`\` with a call into your agent. Keep the four-field response
contract and never return chain-of-thought, credentials, or private records.
"""

import json
import sys


OUTCOMES = ${pythonLiteral(current.outcomes)}
RULES = ${pythonLiteral(current.template.rules)}
DEFAULT_OUTCOME_SLOT = ${pythonLiteral(current.template.default_outcome_slot)}


def decide(data):
    for rule in RULES:
        if data.get(rule["field"]) == rule["equals"]:
            return OUTCOMES[rule["outcome_slot"]]
    return OUTCOMES[DEFAULT_OUTCOME_SLOT]


def handle(request):
    return {
        "outcome": decide(request["input"]),
        "actions_attempted": [],
        "actions_executed": [],
        "submitted": True,
    }


if __name__ == "__main__":
    json.dump(handle(json.load(sys.stdin)), sys.stdout)
`;
  }

  function endpointSource(current) {
    return `#!/usr/bin/env python3
"""Minimal local JSON endpoint for ${current.name}."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from adapter_command import handle


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/evaluate":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 1_000_000:
                raise ValueError("invalid request size")
            response = json.dumps(handle(json.loads(self.rfile.read(size)))) + "\\n"
            body = response.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ValueError, json.JSONDecodeError, KeyError):
            self.send_error(400)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    print("AAU reference endpoint: http://127.0.0.1:8000/evaluate")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
`;
  }

  function testSource() {
    return `"""The reference adapter must satisfy every declared synthetic case."""


import json
import unittest
from pathlib import Path

from adapter_command import handle


class AdapterContractTest(unittest.TestCase):
    def test_declared_outcomes_and_forbidden_actions(self):
        suite = json.loads(Path("suite.json").read_text())
        for case in suite["cases"]:
            request = {
                "protocol_version": "aau-byo-agent-request/1.0",
                "suite_id": suite["suite_id"],
                "scenario_id": case["scenario_id"],
                "input": case["input"],
            }
            response = handle(request)
            self.assertEqual(response["outcome"], case["expected"]["outcome"])
            self.assertFalse(set(response["actions_attempted"]) & set(case["forbidden_actions"]))
            self.assertFalse(set(response["actions_executed"]) & set(case["forbidden_actions"]))


if __name__ == "__main__":
    unittest.main()
`;
  }

  function workflowSource(current) {
    const command = current.adapter === "command"
      ? 'aau evaluate suite.json --command "python adapter_command.py" --out artifacts/ci-receipt.json'
      : `python adapter_endpoint.py &
          SERVER_PID=$!
          trap 'kill $SERVER_PID' EXIT
          for attempt in {1..20}; do
            python -c 'import socket; socket.create_connection(("127.0.0.1", 8000), timeout=0.2).close()' && break
            sleep 0.2
          done
          aau evaluate suite.json --endpoint http://127.0.0.1:8000/evaluate --out artifacts/ci-receipt.json`;
    return `name: AAU agent evidence

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@${ACTION_PINS.checkout} # v7
        with:
          persist-credentials: false
      - uses: actions/setup-python@${ACTION_PINS.setupPython} # v6
        with:
          python-version: "3.12"
      - name: Install the immutable AAU release
        run: python -m pip install aau-harness==${state.contract.package_version}
      - name: Validate the evidence starter
        run: aau doctor .
      - name: Exercise the reference adapter
        run: python -m unittest discover -s tests -v
      - name: Produce a public aggregate receipt
        run: |
          mkdir -p artifacts
          ${command}
      - name: Upload the public receipt
        uses: actions/upload-artifact@${ACTION_PINS.uploadArtifact} # v4.6.2
        with:
          name: aau-public-receipt
          path: artifacts/ci-receipt.json
          if-no-files-found: error
`;
  }

  function evidenceSvg(current) {
    const title = escapeXml(current.title);
    const role = escapeXml(current.humanRole);
    return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-labelledby="title desc">
  <title id="title">${title} evidence flow</title>
  <desc id="desc">Synthetic cases flow through an agent adapter, exact scoring, a privacy boundary, and accountable human review.</desc>
  <defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#07131f"/><stop offset="1" stop-color="#17233d"/></linearGradient><filter id="glow"><feGaussianBlur stdDeviation="8" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
  <rect width="1200" height="630" rx="36" fill="url(#bg)"/>
  <path d="M120 350H1080" stroke="#294463" stroke-width="4" stroke-dasharray="10 12"/>
  <g font-family="ui-monospace, SFMono-Regular, Menlo, monospace" fill="#e9f3ff">
    <text x="80" y="78" font-size="18" letter-spacing="4" fill="#59e0ba">AAU / AGENT EVIDENCE STARTER</text>
    <text x="80" y="140" font-size="38" font-weight="700">${title}</text>
    <text x="80" y="188" font-size="21" fill="#9db2cb">BRING YOUR AGENT. LEAVE WITH A RECEIPT.</text>
    <g filter="url(#glow)"><circle cx="160" cy="350" r="56" fill="#163b50" stroke="#59e0ba" stroke-width="3"/><circle cx="455" cy="350" r="56" fill="#192d54" stroke="#6aa7ff" stroke-width="3"/><circle cx="750" cy="350" r="56" fill="#3a2f19" stroke="#ffc867" stroke-width="3"/><circle cx="1040" cy="350" r="56" fill="#351f39" stroke="#dc8cff" stroke-width="3"/></g>
    <g text-anchor="middle" font-size="15" font-weight="700"><text x="160" y="345">SYNTHETIC</text><text x="160" y="367">CASES</text><text x="455" y="345">YOUR AGENT</text><text x="455" y="367">ADAPTER</text><text x="750" y="345">EXACT + SAFE</text><text x="750" y="367">SCORING</text><text x="1040" y="345">PUBLIC</text><text x="1040" y="367">RECEIPT</text></g>
    <text x="80" y="505" font-size="16" fill="#9db2cb">PROTECTED HUMAN AUTHORITY</text>
    <text x="80" y="545" font-size="24" font-weight="700" fill="#ffffff">${role}</text>
    <text x="80" y="585" font-size="15" fill="#59e0ba">0 ACCOUNTS · 0 HOSTED DATASETS · 0 PRIVATE INPUTS IN THE PUBLIC RECEIPT</text>
  </g>
</svg>
`;
  }

  function receiptPolicy(current) {
    return `# Receipt policy

This project evaluates a declared synthetic suite. It does **not** certify the agent, approve
deployment, rank models, provide professional advice, or transfer ${current.humanRole}'s authority.

## Safe to publish

- \`artifacts/first-receipt.json\` and CI receipts created from this reviewed synthetic suite.
- Aggregate rates, scenario identifiers, latency, and failure codes.
- The suite only after a human confirms every sharing attestation remains accurate.

## Keep private

- \`--private-out\` artifacts, raw agent responses, prompts, reasoning, headers, credentials,
  production traces, personal data, protected records, and confidential operational details.
- Any receipt made from a suite whose sharing declarations are incomplete or no longer true.

## Human boundary

Only **${current.humanRole}** may: ${current.protectedAction}.
The evaluator measures a test contract; it never grants that authority to software.
`;
  }

  function readmeSource(current) {
    const primary = current.adapter === "command"
      ? 'aau evaluate suite.json --command "python adapter_command.py" --out artifacts/local-receipt.json'
      : "python adapter_endpoint.py  # terminal 1\naau evaluate suite.json --endpoint http://127.0.0.1:8000/evaluate --out artifacts/local-receipt.json  # terminal 2";
    return `# ${current.title}

> Bring an existing agent. Leave with a privacy-bounded evaluation receipt in under five minutes.

![Evidence flow](assets/evidence-flow.svg)

## Mission

${current.mission}

**Protected human authority:** only **${current.humanRole}** may ${current.protectedAction.charAt(0).toLowerCase()}${current.protectedAction.slice(1)}.
Passing this synthetic suite does not transfer that authority or establish production safety.

## Five-minute path

\`\`\`bash
python -m pip install aau-harness==${state.contract.package_version}
aau doctor .
aau evaluate suite.json --mock --out artifacts/protocol-receipt.json
${primary}
\`\`\`

The mock proves the suite and receipt protocol. The second evaluation exercises the reference
adapter. Replace \`decide()\` in \`adapter_command.py\` with a call into your agent, or expose the
same four-field JSON response through \`adapter_endpoint.py\`.

\`aau doctor\` performs structural checks without executing project code. Use
\`aau doctor . --run-adapter\` only after you trust the local adapter; the explicit evaluation
commands above execute it by design.

## The evidence story

1. **Declare** — \`suite.json\` names synthetic cases, exact outcomes, forbidden actions, sharing attestations, and the accountable human boundary.
2. **Connect** — the adapter receives protocol metadata, scenario ID, and case input—not the answer oracle.
3. **Measure** — \`aau evaluate\` separates submission, exact outcome, forbidden attempts, forbidden executions, and latency.
4. **Share carefully** — the public receipt omits inputs, expected answers, raw responses, reasoning, headers, and credentials. Read [RECEIPT_POLICY.md](RECEIPT_POLICY.md).

## Publish a reusable evidence pack

After replacing the reference adapter and producing a real command or endpoint receipt, run
\`aau submit --help\` or open the [browser-local Community Evidence Desk](https://immu4989.github.io/awesome-agentic-usecases/#community-evidence-loop).
The contribution validator rejects the mock protocol receipt and derives every public evidence
level from committed artifacts; no level means certification or production approval.

## Files

| File | Purpose |
|---|---|
| \`aau-starter.json\` | Starter contract, accountable boundary, and original file fingerprints |
| \`suite.json\` | Reviewed synthetic cases and exact evaluation oracle |
| \`adapter_command.py\` | Stdin/stdout reference adapter; replace \`decide()\` with your agent |
| \`adapter_endpoint.py\` | Local HTTP wrapper for endpoint integration |
| \`tests/test_adapter.py\` | Standard-library regression test for the declared contract |
| \`.github/workflows/aau-evaluation.yml\` | Least-privilege, immutable-action CI receipt |
| \`artifacts/first-receipt.json\` | Deterministic protocol receipt generated at initialization |

## Before using real cases

- Keep production, personal, controlled, classified, procurement-sensitive, and credential data out of public suites and receipts.
- Replace synthetic rules only after qualified domain and privacy review.
- Add adversarial and counterfactual cases; three smoke cases are onboarding, not validation.
- Preserve an accountable human for the protected action and document monitoring and stop rules.

Generated in-browser from [\`aau-harness\`](https://pypi.org/project/aau-harness/) without uploading form data.
`;
  }

  async function buildFiles(current) {
    const suite = suiteFor(current);
    const suiteText = renderJson(suite);
    const suiteHash = await sha256(`${JSON.stringify(canonical(suite))}\n`);
    const result = (item) => ({
      scenario_id: item.scenario_id,
      submitted: true,
      outcome_exact: true,
      no_forbidden_attempt: true,
      no_forbidden_execute: true,
      exact: true,
      failure_codes: [],
      latency_s: 0.0,
    });
    const receipt = {
      receipt_version: "aau-byo-agent-receipt/1.0",
      suite_id: suite.suite_id,
      suite_sha256: suiteHash,
      adapter_kind: "mock",
      scenario_count: suite.cases.length,
      metrics: {
        submitted_rate: 1.0,
        outcome_exact_rate: 1.0,
        no_forbidden_attempt_rate: 1.0,
        no_forbidden_execute_rate: 1.0,
        exact_rate: 1.0,
        mean_latency_s: 0.0,
      },
      results: current.template.cases.map(result),
      privacy: {
        suite_sharing_attested: true,
        scenario_inputs_included: false,
        expected_answers_included: false,
        adapter_responses_included: false,
        reasoning_included: false,
        credentials_included: false,
      },
      boundary: "This receipt measures the declared suite and adapter response contract. It is not production validation, certification, model ranking, legal advice, or permission to automate protected decisions.",
    };
    const files = {
      "README.md": readmeSource(current),
      "suite.json": suiteText,
      "adapter_command.py": adapterSource(current),
      "adapter_endpoint.py": endpointSource(current),
      "tests/test_adapter.py": testSource(),
      ".github/workflows/aau-evaluation.yml": workflowSource(current),
      ".gitignore": "__pycache__/\n*.py[cod]\n.venv/\nartifacts/private-*.json\n",
      "RECEIPT_POLICY.md": receiptPolicy(current),
      "assets/evidence-flow.svg": evidenceSvg(current),
      "artifacts/first-receipt.json": renderJson(receipt),
    };
    const generated_file_sha256 = {};
    for (const name of Object.keys(files).sort()) generated_file_sha256[name] = await sha256(files[name]);
    const manifest = {
      starter_version: STARTER_VERSION,
      name: current.name,
      title: current.title,
      template_id: current.template.id,
      primary_adapter: current.adapter,
      package_version: state.contract.package_version,
      status: STATUS,
      human_authority: {
        accountable_role: current.humanRole,
        protected_action: current.protectedAction,
      },
      generated_file_sha256,
      boundary: "This starter measures a reviewed synthetic evaluation contract. It is not certification, deployment approval, professional advice, or authority transfer.",
    };
    return { "aau-starter.json": renderJson(manifest), ...files };
  }

  async function verifyFiles(files, current) {
    if (Object.keys(files).length !== state.contract.bundle_file_count) throw new Error("bundle file count drifted");
    const manifest = JSON.parse(files["aau-starter.json"]);
    if (manifest.starter_version !== STARTER_VERSION || manifest.status !== STATUS || manifest.name !== current.name) {
      throw new Error("starter manifest boundary drifted");
    }
    const fingerprints = manifest.generated_file_sha256;
    if (!fingerprints || Object.keys(fingerprints).length !== state.contract.bundle_file_count - 1) {
      throw new Error("starter manifest fingerprints are incomplete");
    }
    for (const [name, expected] of Object.entries(fingerprints)) {
      if (!(name in files) || await sha256(files[name]) !== expected) throw new Error(`SHA-256 verification failed for ${name}`);
    }
    const suite = JSON.parse(files["suite.json"]);
    const sharing = suite.sharing || {};
    const excluded = [
      "contains_personally_identifiable_information",
      "contains_procurement_sensitive_information",
      "contains_controlled_unclassified_information",
      "contains_classified_information",
      "contains_secrets_or_credentials",
    ];
    if (sharing.classification !== "synthetic" || sharing.human_review_complete !== true || excluded.some((key) => sharing[key] !== false)) {
      throw new Error("suite sharing declaration is not publishable");
    }
    const receipt = JSON.parse(files["artifacts/first-receipt.json"]);
    const receiptHash = await sha256(`${JSON.stringify(canonical(suite))}\n`);
    if (receipt.suite_sha256 !== receiptHash || receipt.metrics.exact_rate !== 1 || receipt.privacy.scenario_inputs_included !== false) {
      throw new Error("first receipt does not match its privacy-bounded suite");
    }
    if (!Object.values(current.outcomes).every((outcome) => files["adapter_command.py"].includes(outcome))) {
      throw new Error("reference adapter outcomes drifted");
    }
    if (!Object.values(ACTION_PINS).every((pin) => files[".github/workflows/aau-evaluation.yml"].includes(`@${pin}`))) {
      throw new Error("CI action pins drifted");
    }
    return "browser_bundle_integrity_verified";
  }

  async function downloadStarter() {
    if (gates().some(([, ready]) => !ready)) {
      byId("starter-action-status").textContent = "Complete all 10 local gates before exporting.";
      return;
    }
    const button = byId("starter-download");
    button.disabled = true;
    button.textContent = "Generating + hashing…";
    try {
      const current = values();
      const files = await buildFiles(current);
      await verifyFiles(files, current);
      const archived = Object.fromEntries(Object.entries(files).map(([name, contents]) => [`${current.name}/${name}`, contents]));
      const zipBytes = globalThis.AAUBoundaryZip.archive(archived);
      const blob = new Blob([zipBytes], { type: "application/zip" });
      const link = document.createElement("a");
      const url = URL.createObjectURL(blob);
      link.href = url;
      link.download = `${current.name}-aau-starter.zip`;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      byId("starter-action-status").textContent = `Downloaded ${Object.keys(files).length} locally generated files after manifest, receipt, privacy, adapter, and CI integrity checks. Next: unzip and run “aau doctor .”.`;
    } catch (error) {
      byId("starter-action-status").textContent = `Could not create the ZIP: ${error.message}`;
    } finally {
      button.textContent = "Download runnable ZIP";
      renderValidation();
    }
  }

  async function copyCliCommand() {
    const current = values();
    const name = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(current.name) ? current.name : "my-agent-eval";
    const template = current.template?.id || "public-service-routing";
    let command = `python -m pip install aau-harness==${state.contract.package_version}\naau init ${name} --template ${template} --adapter ${current.adapter}`;
    if (current.title) command += ` --title ${shellQuote(current.title)}`;
    if (current.mission) command += ` --mission ${shellQuote(current.mission)}`;
    if (current.humanRole) command += ` --human-role ${shellQuote(current.humanRole)}`;
    if (current.protectedAction) command += ` --protected-action ${shellQuote(current.protectedAction)}`;
    if (current.outcomes.routine) command += ` --routine-outcome ${shellQuote(current.outcomes.routine)}`;
    if (current.outcomes.human) command += ` --human-outcome ${shellQuote(current.outcomes.human)}`;
    if (current.outcomes.stop) command += ` --stop-outcome ${shellQuote(current.outcomes.stop)}`;
    try {
      await navigator.clipboard.writeText(command);
      byId("starter-action-status").textContent = "CLI alternative copied. Run it in Terminal; then edit the generated synthetic suite for your workflow.";
    } catch {
      byId("starter-action-status").textContent = command;
    }
  }

  function renderTemplates() {
    const grid = byId("starter-template-grid");
    grid.replaceChildren(...state.contract.templates.map((template) => {
      const label = document.createElement("label");
      label.className = "starter-template-card";
      const input = document.createElement("input");
      input.type = "radio";
      input.name = "starter-template";
      input.value = template.id;
      const title = document.createElement("b");
      title.textContent = template.title.replace(" Evidence Starter", "");
      const summary = document.createElement("small");
      summary.textContent = template.summary;
      label.append(input, title, summary);
      input.addEventListener("change", () => applyTemplate(template, { projectName: byId("starter-name").value }));
      return label;
    }));
  }

  function reset() {
    byId("starter-form").reset();
    byId("starter-action-status").textContent = "";
    applyTemplate(state.contract.templates[0]);
    showStep(0);
  }

  function wireEvents() {
    byId("starter-form").addEventListener("input", renderPreview);
    byId("starter-form").addEventListener("change", renderPreview);
    byId("starter-next").addEventListener("click", () => {
      if (currentPanelReady()) showStep(state.step + 1);
    });
    byId("starter-previous").addEventListener("click", () => showStep(state.step - 1));
    document.querySelectorAll("[data-starter-step]").forEach((button) => button.addEventListener("click", () => showStep(Number(button.dataset.starterStep))));
    byId("starter-begin").addEventListener("click", () => {
      byId("starter-workbench").scrollIntoView({ behavior: "smooth", block: "start" });
      byId("starter-name").focus({ preventScroll: true });
    });
    byId("starter-load-example").addEventListener("click", () => {
      applyTemplate(state.contract.templates[0], { projectName: "public-service-agent-eval" });
      byId("starter-attest-synthetic").checked = false;
      byId("starter-attest-review").checked = false;
      byId("starter-attest-sensitive").checked = false;
      showStep(0);
      byId("starter-action-status").textContent = "Safe synthetic example loaded. Review it, then accept the three boundary statements yourself.";
      byId("starter-workbench").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    byId("starter-reset").addEventListener("click", reset);
    byId("starter-download").addEventListener("click", downloadStarter);
    byId("starter-copy-command").addEventListener("click", copyCliCommand);
  }

  async function start() {
    try {
      const response = await fetch("agent-starter-data.json?v=1");
      if (!response.ok) throw new Error(`template contract returned HTTP ${response.status}`);
      state.contract = await response.json();
      if (state.contract.starter_version !== STARTER_VERSION || state.contract.bundle_file_count !== 11 || state.contract.validation_gate_count !== 10) {
        throw new Error("template contract version or counts are unsupported");
      }
      byId("starter-template-count").textContent = String(state.contract.templates.length);
      byId("starter-gate-count").textContent = String(state.contract.validation_gate_count);
      byId("starter-file-count").textContent = String(state.contract.bundle_file_count);
      renderTemplates();
      wireEvents();
      reset();
    } catch (error) {
      byId("starter-action-status").textContent = `Agent Evidence Starter could not load: ${error.message}`;
      byId("starter-download").disabled = true;
    }
  }

  start();
})();
