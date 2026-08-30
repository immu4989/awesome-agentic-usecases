import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "reproduction-challenges" / "submit.py"


def campaign_module():
    spec = importlib.util.spec_from_file_location("reproduction_campaign", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_challenges_are_answer_free_and_bound():
    campaign = campaign_module().verify_campaign()
    assert len(campaign["challenges"]) >= 4
    assert sum(entry["task_count"] for entry in campaign["challenges"]) >= 26
    assert campaign["independently_reproduced_count"] == 0
    for entry in campaign["challenges"]:
        challenge = json.loads(
            (ROOT / "reproduction-challenges" / entry["path"]).read_text()
        )
        serialized = json.dumps(challenge)
        assert "gold_outcome" not in serialized
        assert "gold_actions" not in serialized
        assert len(challenge["oracle_commitment_sha256"]) == 64


def test_authority_relay_challenge_is_current_and_cross_protocol():
    campaign = campaign_module().verify_campaign()
    entry = next(
        item for item in campaign["challenges"]
        if item["challenge_id"] == "a2a-mcp-authority-relay-2026-01"
    )
    challenge = campaign_module().load_public(
        ROOT / "reproduction-challenges" / entry["path"]
    )
    urls = {source["url"] for source in challenge["official_sources"]}
    assert len(challenge["tasks"]) == 8
    assert any("v1.0.1" in url for url in urls)
    assert any("2026-07-28" in url for url in urls)
    assert any("rfc8693" in url for url in urls)
    assert {task["task_id"] for task in challenge["tasks"]} == {
        f"relay-blind-{number:02d}" for number in range(1, 9)
    }


def test_templates_cannot_accidentally_validate_as_submissions():
    module = campaign_module()
    exchange = module.exchange_module()
    campaign = module.verify_campaign()
    for entry in campaign["challenges"]:
        base = ROOT / "reproduction-challenges"
        challenge = module.load_public(base / entry["path"])
        responses = module.load_public(base / entry["responses_template"])
        metadata = module.load_public(base / entry["metadata_template"])
        try:
            exchange.build_submission(challenge, responses, metadata)
        except exchange.ReproductionError:
            pass
        else:
            raise AssertionError("an unedited TODO template must not validate")


def test_campaign_paths_cannot_escape_or_cross_symlinks(tmp_path):
    module = campaign_module()
    for value in ("../README.md", "/tmp/challenge.json"):
        try:
            module.safe_campaign_path(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe campaign path accepted: {value}")

    link = ROOT / "reproduction-challenges" / "unsafe-test-link"
    try:
        link.symlink_to(tmp_path, target_is_directory=True)
        try:
            module.safe_campaign_path("unsafe-test-link/challenge.json")
        except ValueError:
            pass
        else:
            raise AssertionError("symbolic-link campaign path accepted")
    finally:
        link.unlink(missing_ok=True)
