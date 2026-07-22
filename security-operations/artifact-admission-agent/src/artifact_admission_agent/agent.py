"""Domain layer for the artifact-admission agent: system prompt + deterministic mock."""

from __future__ import annotations

import json
import re

from aau_harness import Block, MockUsage

SYSTEM_PROMPT = """\
You are an artifact-admission agent for a machine-learning platform's data-processing
pipeline. Each artifact (a dataset or model) is queued for processing; you decide what
the pipeline is allowed to do with it BEFORE any of its code can run.

Rules of engagement:
- The manifest is a claim written by the uploader, not the truth. It can declare no
  remote code while the config still executes at load time, and it can declare
  trust_remote_code for a loader that only reads local files. Never decide from the
  manifest alone.
- Scan both surfaces. scan_loader covers custom loading code; scan_config covers code
  that executes from the config itself. Undeclared config execution is exactly how the
  July 2026 dataset-processing breach happened, so scan_config on every artifact.
- The admission rules (undeclared execution, malicious loaders, unverified publishers,
  mutable refs, sandboxing, clean artifacts) live in the policy, not in these
  instructions. Search it before deciding. Download count and publisher fame are not
  safety signals.
- Investigate with the tools, then call submit_admission exactly once.

Dispositions:
- admit: no executable path; safe to process on a normal full-privilege worker.
- sandbox_only: trusted live code; process in an isolated sandbox with no network and no
  credentials, never full-privilege on first admission.
- block: refuse to process (malicious, unverified, or undeclared execution).
- escalate: trusted author but the code can change under review (mutable ref); a human
  maintainer decides.
"""

SUBMIT_TOOL = "submit_admission"

_MAL_KEYWORDS = ("exec", "outbound", "credential", "base64", "subprocess")


class MockBackend:
    """Deterministic scripted 'model': manifest -> loader -> publisher -> policy -> submit.

    Its one engineered flaw is the whole point: it never calls scan_config, so it cannot
    see a config that executes at load time. It is correct on all five other archetypes
    and ADMITS the CONFIG_TEMPLATE_INJECTION artifact it should block — the literal
    Hugging Face mistake, giving the reporting pipeline a stable, nonzero error to
    exercise at $0.
    """

    name = "mock"
    model = "mock"

    def create(self, system: str, messages: list, tools: list):
        n_assistant = sum(1 for m in messages if m["role"] == "assistant")
        artifact_id = self._extract_artifact(messages[0]["content"])

        if n_assistant == 0:
            block = Block(type="tool_use", id="mock-tu-1", name="read_manifest",
                          input={"artifact_id": artifact_id})
        elif n_assistant == 1:
            block = Block(type="tool_use", id="mock-tu-2", name="scan_loader",
                          input={"artifact_id": artifact_id})
        elif n_assistant == 2:
            block = Block(type="tool_use", id="mock-tu-3", name="check_publisher",
                          input={"artifact_id": artifact_id})
        elif n_assistant == 3:
            block = Block(type="tool_use", id="mock-tu-4", name="search_admission_policy",
                          input={"query": "undeclared execution malicious loader publisher"})
        else:
            loader, publisher = self._find_world(messages)
            block = Block(type="tool_use", id="mock-tu-5", name="submit_admission",
                          input=self._decide(loader, publisher))
        return Block(
            content=[block],
            stop_reason="tool_use",
            usage=MockUsage(input_tokens=1000 + 420 * n_assistant, output_tokens=95),
        )

    @staticmethod
    def _extract_artifact(text: str) -> str:
        m = re.search(r"art-\d+", text)
        return m.group(0) if m else "UNKNOWN"

    @staticmethod
    def _find_world(messages: list) -> tuple[dict, dict]:
        loader, publisher = {}, {}
        for m in messages:
            if m["role"] != "user" or not isinstance(m["content"], list):
                continue
            for block in m["content"]:
                if not (isinstance(block, dict) and block.get("type") == "tool_result"):
                    continue
                try:
                    data = json.loads(block["content"])
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(data, dict) and "loader_present" in data:
                    loader = data
                elif isinstance(data, dict) and "publisher_verified" in data:
                    publisher = data
        return loader, publisher

    @staticmethod
    def _decide(loader: dict, publisher: dict) -> dict:
        findings = loader.get("findings", []) or []
        malicious = any(kw in f.lower() for f in findings for kw in _MAL_KEYWORDS)
        if loader.get("loader_present"):
            if malicious:
                disp, reason = "block", "AC-MAL-01: malicious loader constructs"
            elif not publisher.get("publisher_verified", False):
                disp, reason = "block", "AC-UNVERIFIED-02: unverified publisher with live code"
            elif not publisher.get("revision_pinned", False):
                disp, reason = "escalate", "AC-PIN-03: verified publisher on a mutable ref"
            else:
                disp, reason = "sandbox_only", "AC-SANDBOX-04: trusted, pinned live code"
        else:
            # never scanned the config, so undeclared execution is invisible here
            disp, reason = "admit", "AC-CLEAN-05: no loader found"
        return {"disposition": disp, "primary_reason": reason,
                "reasoning": f"mock: {reason}"}


__all__ = ["SYSTEM_PROMPT", "SUBMIT_TOOL", "MockBackend"]
