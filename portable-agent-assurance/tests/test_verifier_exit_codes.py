"""Valid failed evidence must not turn a downstream CI gate green."""

import importlib.util
import json
import shlex
import sys
import uuid
from types import SimpleNamespace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("module_name,stem", [
    ("mcp_2026_delta", "mcp-2026-authorization"),
    ("a2a_1_delta", "a2a-1-interface-authorization"),
    ("authority_relay", "a2a-mcp-authority-relay"),
])
def test_verify_cli_exit_codes(module_name, stem, tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / f"{module_name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    profile_path = ROOT / "examples" / f"{stem}-profile.json"
    suite_path = ROOT / "examples" / f"{stem}-suite.json"
    profile, suite = module.load_json(profile_path), module.load_json(suite_path)
    adapter = tmp_path / "deny.py"
    adapter.write_text(
        "import json,sys\njson.load(sys.stdin)\n"
        "json.dump({'decision':'block','reason_codes':['DENY_ALL']},sys.stdout)\n"
    )
    failed = module.run_suite(profile, suite, "command",
                              shlex.join([sys.executable, str(adapter)]), 5)
    assert failed["metrics"]["legitimate_block_count"] > 0
    receipt_path = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", [module_name, "verify", str(receipt_path),
                                     str(profile_path), str(suite_path)])
    receipt_path.write_text(json.dumps(failed))
    assert module.main() == 1
    failed["metrics"]["exact_count"] += 1
    receipt_path.write_text(json.dumps(failed))
    assert module.main() == 2
    passed = module.run_suite(profile, suite, "reference", None, 5)
    receipt_path.write_text(json.dumps(passed))
    assert module.main() == 0


@pytest.mark.parametrize("module_name,stem", [
    ("mcp_2026_delta", "mcp-2026-authorization"),
    ("a2a_1_delta", "a2a-1-interface-authorization"),
    ("authority_relay", "a2a-mcp-authority-relay"),
])
def test_transport_ids_do_not_disclose_case_labels(module_name, stem, monkeypatch):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / f"{module_name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite = module.load_json(ROOT / "examples" / f"{stem}-suite.json")
    requests = []

    def execute(argv, **kwargs):
        requests.append(json.loads(kwargs["input"]))
        return SimpleNamespace(returncode=0, stdout=b'{"decision":"block","reason_codes":[]}')

    monkeypatch.setattr(module.subprocess, "run", execute)
    invoke = module._command_adapter("unused-adapter", 5)
    for case in suite["cases"]:
        invoke(case["case_id"], case["request"])
    assert len({request["case_id"] for request in requests}) == len(suite["cases"])
    for request, case in zip(requests, suite["cases"]):
        assert set(request) == {"protocol_version", "case_id", "request"}
        assert uuid.UUID(request["case_id"]).version == 4
        assert request["case_id"] != case["case_id"]
        assert request["request"] == case["request"]
