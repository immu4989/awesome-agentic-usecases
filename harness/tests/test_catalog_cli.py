import json
from pathlib import Path

import pytest

from aau_harness.catalog_cli import (
    doctor,
    filter_cases,
    find_root,
    install_command,
    load_catalog,
    main,
    resolve_case,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def cases():
    return load_catalog(ROOT)


def test_finds_repository_root():
    assert find_root(ROOT / "customer-support" / "refund-guarded") == ROOT


def test_catalog_can_be_searched_by_user_intent(cases):
    security = filter_cases(cases, query="security")
    assert len(security) >= 4
    assert all("security" in json.dumps(item).lower() for item in security)

    acting_guards = filter_cases(cases, query="act guardrails")
    assert {item["cli"] for item in acting_guards} == {
        "refund-guarded",
        "incident-remediation-agent",
    }


def test_resolves_friendly_names(cases):
    assert resolve_case(cases, "exception triage")["cli"] == "exception-triage-agent"
    assert resolve_case(cases, "refund-memory")["title"] == "Refund Memory"
    with pytest.raises(SystemExit, match="No use case"):
        resolve_case(cases, "space gardening")


def test_install_command_includes_local_dependencies(cases):
    item = resolve_case(cases, "refund-injected")
    command = install_command(ROOT, item)
    assert command.startswith("python -m pip install -e harness")
    assert command.index("refund-resolution-agent") < command.index("refund-guarded")
    assert command.index("refund-guarded") < command.index("refund-injected")


def test_doctor_accepts_the_committed_catalog(cases):
    assert doctor(ROOT, cases) == []


def test_cli_start_prints_a_copyable_no_key_path(capsys):
    assert main(["--root", str(ROOT), "start", "exception-triage"]) == 0
    output = capsys.readouterr().out
    assert "python -m pip install -e harness" in output
    assert "exception-triage-agent eval --backend mock" in output


def test_cli_forwards_release_verification(capsys):
    pack = ROOT / "agent-release-gate" / "examples" / "reference-pack"
    assert main(["release", "verify", str(pack)]) == 0
    assert "release pack verified with status release_ready" in capsys.readouterr().out
