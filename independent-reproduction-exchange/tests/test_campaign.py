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
    assert len(campaign["challenges"]) >= 5
    assert sum(
        entry["task_count"] for entry in campaign["challenges"]
        if entry["status"] == "open"
    ) >= 26
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


def test_open_portable_challenge_is_revision_locked():
    module = campaign_module()
    campaign = module.verify_campaign()
    original = next(
        item for item in campaign["challenges"]
        if item["challenge_id"] == "portable-agent-assurance-2026-01"
    )
    current = next(
        item for item in campaign["challenges"]
        if item["challenge_id"] == "portable-agent-assurance-2026-02"
    )
    assert original["status"] == "closed"
    assert current["status"] == "open"
    challenge = module.load_public(ROOT / "reproduction-challenges" / current["path"])
    urls = {source["url"] for source in challenge["official_sources"]}
    assert any("v1.0.1" in url for url in urls)
    assert any("2026-07-28" in url for url in urls)
    assert any("2026-02" in url and url.endswith(".pdf") for url in urls)
    assert all("/blob/main/" not in url and "/raw/main/" not in url for url in urls)


def test_mutable_github_source_can_only_remain_as_closed_history():
    module = campaign_module()
    original = module.load_public(
        ROOT / "reproduction-challenges" / "portable-agent-assurance" / "challenge.json"
    )
    try:
        module.validate_challenge_sources({"status": "open"}, original)
    except ValueError as exc:
        assert "mutable GitHub branch URL" in str(exc)
    else:
        raise AssertionError("an open challenge accepted a mutable GitHub source")
    module.validate_challenge_sources({"status": "closed"}, original)


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


def test_independent_count_is_derived_from_verified_registry_entries():
    module = campaign_module()
    campaign = module.load_public(ROOT / "reproduction-challenges" / "campaign.json")
    registry = module.load_public(
        ROOT / "reproduction-challenges" / "accepted-reproductions.json"
    )
    assert module.verify_reproduction_registry(campaign, registry)["entries"] == []

    inflated = dict(campaign)
    inflated["independently_reproduced_count"] = 1
    try:
        module.verify_reproduction_registry(inflated, registry)
    except ValueError as exc:
        assert "must equal verified registry entries" in str(exc)
    else:
        raise AssertionError("a manually inflated independent count was accepted")


def test_acceptance_plan_recomputes_pack_without_mutating_campaign(tmp_path, monkeypatch):
    module = campaign_module()
    exchange = module.exchange_module()
    demo = ROOT / "independent-reproduction-exchange" / "examples" / "revealed-protocol-demo"
    challenge = exchange.load_json(demo / "challenge.json")
    oracle = exchange.load_json(demo / "oracle.json")
    stored_submission = exchange.load_json(demo / "submission.json")
    metadata = {
        "metadata_version": "aau-reproduction-metadata/0.1",
        "submission_id": "outside-reproducer-test",
        "producer_commitment_sha256": stored_submission["producer_commitment_sha256"],
        "relationship_to_issuer": "none",
        "executed_on": "2026-08-30",
        "environment": stored_submission["environment"],
        "methodology": stored_submission["methodology"],
        "sharing": stored_submission["sharing"],
    }
    submission = exchange.build_submission(challenge, stored_submission["responses"], metadata)
    review = exchange.load_json(demo / "review.json")
    review["relationship_to_issuer"] = "none"
    review["relationship_to_producer"] = "none"
    review["limitations"] = ["Synthetic test of the acceptance transition only."]
    payloads, adjudication = exchange.pack_payloads(challenge, oracle, submission, review)
    assert adjudication["status"] == "independence_reviewed"
    pack = tmp_path / "reviewed-pack"
    pack.mkdir()
    for name, payload in payloads.items():
        (pack / name).write_bytes(payload)

    campaign_root = tmp_path / "campaign"
    (campaign_root / "demo").mkdir(parents=True)
    (campaign_root / "demo" / "challenge.json").write_text(
        json.dumps(challenge, indent=2) + "\n"
    )
    response_template = {
        "responses": [{"task_id": task["task_id"]} for task in challenge["tasks"]]
    }
    (campaign_root / "demo" / "responses.template.json").write_text(
        json.dumps(response_template, indent=2) + "\n"
    )
    (campaign_root / "demo" / "metadata.template.json").write_text("{}\n")
    base_campaign = module.load_public(ROOT / "reproduction-challenges" / "campaign.json")
    campaign = {
        **base_campaign,
        "independently_reproduced_count": 0,
        "challenges": [{
            "challenge_id": challenge["challenge_id"],
            "title": challenge["title"],
            "path": "demo/challenge.json",
            "responses_template": "demo/responses.template.json",
            "metadata_template": "demo/metadata.template.json",
            "task_count": len(challenge["tasks"]),
            "status": "open",
        }],
    }
    (campaign_root / "campaign.json").write_text(json.dumps(campaign, indent=2) + "\n")
    registry = module.load_public(
        ROOT / "reproduction-challenges" / "accepted-reproductions.json"
    )
    (campaign_root / "accepted-reproductions.json").write_text(
        json.dumps(registry, indent=2) + "\n"
    )
    monkeypatch.setattr(module, "HERE", campaign_root)

    out = tmp_path / "acceptance-plan"
    plan = module.plan_acceptance(
        challenge["challenge_id"], pack, "outside-reproducer-test", "2026-08-30", out
    )
    assert plan["entry"]["adjudication_sha256"] == adjudication["adjudication_sha256"]
    proposed_campaign = json.loads((out / "campaign.proposed.json").read_text())
    proposed_registry = json.loads((out / "accepted-reproductions.proposed.json").read_text())
    assert proposed_campaign["challenges"][0]["status"] == "closed"
    assert proposed_campaign["independently_reproduced_count"] == 1
    assert len(proposed_registry["entries"]) == 1
    assert not (campaign_root / "accepted").exists()
    assert json.loads((campaign_root / "campaign.json").read_text()) == campaign
    assert set(path.name for path in out.iterdir()) == {
        "README.md", "SHA256SUMS", "acceptance-plan.json",
        "accepted-reproductions.proposed.json", "campaign.proposed.json",
    }


def test_acceptance_plan_rejects_protocol_demonstration(tmp_path):
    module = campaign_module()
    demo_pack = (
        ROOT / "independent-reproduction-exchange" / "examples" / "revealed-protocol-demo"
    )
    try:
        module.plan_acceptance(
            "portable-agent-assurance-2026-02",
            demo_pack,
            "invalid-protocol-demo",
            "2026-08-30",
            tmp_path / "must-not-exist",
        )
    except ValueError as exc:
        assert "only an independence-reviewed pack" in str(exc)
    else:
        raise AssertionError("a protocol demonstration was accepted")
    assert not (tmp_path / "must-not-exist").exists()
