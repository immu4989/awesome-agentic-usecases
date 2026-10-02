import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from aau_harness.agent_bom import load_json
from aau_harness.authority_starter import create_starter


ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / ".github/actions/aau-authority-check/run.py"


def test_action_preserves_failed_evidence_and_emits_summary(tmp_path):
    workspace = tmp_path / "workspace with spaces"
    create_starter(load_json(ROOT / "agent-capability-bom/examples/candidate.json"), workspace)
    env = dict(os.environ, GITHUB_WORKSPACE=str(workspace),
               AAU_AUTHORITY_INVENTORY="inventory.json", AAU_AUTHORITY_ARTIFACT="adapter.py",
               AAU_AUTHORITY_COMMAND=shlex.join([sys.executable, "adapter.py"]),
               AAU_AUTHORITY_OUTPUT="results with spaces", GITHUB_STEP_SUMMARY=str(tmp_path / "summary.md"))
    result = subprocess.run([sys.executable, str(DRIVER)], env=env, capture_output=True, text=True)
    assert result.returncode == 1, result.stderr
    assert load_json(workspace / "results with spaces/completion.json")["status"] == "evidence_failed"
    assert "0/" in (tmp_path / "summary.md").read_text()
    assert (workspace / "results with spaces/results.xml").exists()
    result = subprocess.run([sys.executable, str(DRIVER)], env=env, capture_output=True, text=True)
    assert result.returncode == 2
    assert "overwrite" in result.stderr


@pytest.mark.parametrize("path", ["../outside", "/tmp/outside", ".", ""])
def test_action_rejects_escaping_or_root_output_before_execution(tmp_path, path):
    env = dict(os.environ, GITHUB_WORKSPACE=str(tmp_path), AAU_AUTHORITY_INVENTORY="inventory.json",
               AAU_AUTHORITY_ARTIFACT="adapter.py", AAU_AUTHORITY_COMMAND="never execute",
               AAU_AUTHORITY_OUTPUT=path)
    result = subprocess.run([sys.executable, str(DRIVER)], env=env, capture_output=True, text=True)
    assert result.returncode == 2
    assert "Action path" in result.stderr
    assert not list(tmp_path.iterdir())


def test_action_passes_with_explicit_protocol_reference(tmp_path):
    # Use the synthetic reference only to check plumbing, not as deployment evidence.
    out = tmp_path / "workspace"
    out.mkdir()
    bom = load_json(ROOT / "agent-capability-bom/examples/candidate.json")
    (out / "inventory.json").write_text(json.dumps(bom))
    (out / "candidate.json").write_text(json.dumps(bom))
    (out / "adapter.py").write_bytes((ROOT / "agent-capability-bom/examples/reference_conformance_adapter.py").read_bytes())
    env = dict(os.environ, GITHUB_WORKSPACE=str(out), AAU_AUTHORITY_INVENTORY="inventory.json",
               AAU_AUTHORITY_ARTIFACT="adapter.py", AAU_AUTHORITY_COMMAND=shlex.join([sys.executable, "adapter.py"]),
               AAU_AUTHORITY_OUTPUT="results", PYTHONPATH=str(ROOT / "harness/src"))
    result = subprocess.run([sys.executable, str(DRIVER)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert load_json(out / "results/completion.json")["status"] == "evidence_passed"
