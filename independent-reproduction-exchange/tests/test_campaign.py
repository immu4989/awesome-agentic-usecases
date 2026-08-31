import importlib.util
import hashlib
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


def test_campaign_lock_binds_registries_challenges_and_templates():
    module = campaign_module()
    campaign = module.verify_campaign()
    registry = module.load_public(
        ROOT / "reproduction-challenges" / "accepted-reproductions.json"
    )
    lock = module.load_public(ROOT / "reproduction-challenges" / "campaign-lock.json")
    assert lock == module.build_campaign_lock(campaign, registry)
    assert lock["summary"] == {
        "open_challenge_count": 4,
        "closed_challenge_count": 1,
        "open_task_count": 26,
        "accepted_reproduction_count": 0,
    }
    assert len(lock["artifacts"]) == 5
    assert all(len(item["files"]) == 3 for item in lock["artifacts"])
    campaign_bytes = (ROOT / "reproduction-challenges" / "campaign.json").read_bytes()
    registry_bytes = (
        ROOT / "reproduction-challenges" / "accepted-reproductions.json"
    ).read_bytes()
    assert lock["campaign"]["sha256"] == hashlib.sha256(campaign_bytes).hexdigest()
    assert lock["accepted_registry"]["sha256"] == hashlib.sha256(registry_bytes).hexdigest()
    changed = json.loads(json.dumps(campaign))
    changed["challenges"][0]["title"] += " changed"
    changed_bytes = (json.dumps(changed, indent=2) + "\n").encode()
    assert module.build_campaign_lock(
        changed, registry, campaign_payload=changed_bytes, registry_payload=registry_bytes
    )["lock_sha256"] != lock["lock_sha256"]


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


def test_fork_intake_derives_open_ids_instead_of_copying_a_stale_list():
    module = campaign_module()
    open_ids = {entry["challenge_id"] for entry in module.open_challenges()}
    assert open_ids == {
        "portable-agent-assurance-2026-02",
        "grid-restoration-2026-01",
        "pharma-batch-disposition-2026-01",
        "a2a-mcp-authority-relay-2026-01",
    }
    workflow = (ROOT / ".github" / "workflows" / "fork-to-reproduce.yml").read_text()
    issue_form = (
        ROOT / ".github" / "ISSUE_TEMPLATE" / "independent-reproduction.yml"
    ).read_text()
    assert "type: string" in workflow
    assert "type: choice" not in workflow
    assert "portable-agent-assurance-2026-01" not in workflow
    assert "workspace_path:" in workflow and "build-prepared" in workflow
    assert "responses_path:" not in workflow and "metadata_path:" not in workflow
    assert "AAU_CHALLENGE_ID" not in workflow
    challenge_block = issue_form.split("id: challenge", 1)[1].split("validations:", 1)[0]
    assert "Open challenge ID" in challenge_block
    assert "options:" not in challenge_block


def test_fork_workflow_boundary_is_executable_policy():
    module = campaign_module()
    workflow = (ROOT / ".github" / "workflows" / "fork-to-reproduce.yml").read_text()
    module.validate_fork_workflow_text(workflow)

    unsafe_variants = {
        "pull-request trigger": workflow.replace(
            "  workflow_dispatch:", "  pull_request_target:\n  workflow_dispatch:"
        ),
        "inline push trigger": workflow.replace(
            "  workflow_dispatch:", "  push: {}\n  workflow_dispatch:"
        ),
        "write permission": workflow.replace("contents: read", "contents: write"),
        "persisted credentials": workflow.replace(
            "persist-credentials: false", "persist-credentials: true"
        ),
        "secret consumption": workflow.replace(
            "AAU_WORKSPACE_PATH: ${{ inputs.workspace_path }}",
            "AAU_WORKSPACE_PATH: ${{ secrets.WORKSPACE_PATH }}",
        ),
        "unquoted input": workflow.replace(
            '\"$AAU_WORKSPACE_PATH\"', "$AAU_WORKSPACE_PATH"
        ),
        "mutable action": workflow.replace(
            "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1",
            "actions/setup-python@v6",
        ),
    }
    for label, candidate in unsafe_variants.items():
        try:
            module.validate_fork_workflow_text(candidate)
        except ValueError:
            pass
        else:
            raise AssertionError(f"fork workflow accepted {label}")


def test_prepared_workspace_is_oracle_free_current_and_tamper_evident(tmp_path):
    module = campaign_module()
    workspace = tmp_path / "relay-reproduction"
    origin = module.prepare_workspace(
        "a2a-mcp-authority-relay-2026-01", workspace
    )
    assert origin["challenge_id"] == "a2a-mcp-authority-relay-2026-01"
    assert set(path.name for path in workspace.iterdir()) == {
        ".aau", "README.md", "metadata.json", "responses.json",
    }
    public_text = "\n".join(
        path.read_text()
        for path in workspace.rglob("*")
        if path.is_file()
    )
    assert "gold_outcome" not in public_text
    assert "gold_actions" not in public_text
    try:
        module.check_prepared(workspace)
    except ValueError:
        pass
    else:
        raise AssertionError("an unfinished workspace was treated as ready")

    responses_path = workspace / "responses.json"
    responses = json.loads(responses_path.read_text())
    responses["system_id"] = "outside-system-test"
    responses["adapter_description"] = "Public synthetic test adapter."
    for row in responses["responses"]:
        row.update({
            "outcome": "investigate",
            "actions": ["route-review"],
            "source_refs": [],
            "human_escalation": True,
            "service_preserved": True,
        })
    responses_path.write_text(json.dumps(responses, indent=2) + "\n")
    metadata_path = workspace / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata.update({
        "submission_id": "outside-system-test-2026-08-30",
        "producer_commitment_sha256": "d" * 64,
        "executed_on": "2026-08-30",
    })
    metadata["environment"].update({
        "runtime": "Python 3.12",
        "runner": "local synthetic test",
        "adapter_version": "outside-system-test/1.0",
    })
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    submission = module.check_prepared(workspace)
    assert submission["challenge_sha256"] == origin["challenge_sha256"]
    assert len(submission["submission_sha256"]) == 64
    submission_path = tmp_path / "submission.json"
    built = module.build_prepared(workspace, submission_path)
    assert json.loads(submission_path.read_text()) == built == submission
    try:
        module.build_prepared(workspace, submission_path)
    except ValueError as exc:
        assert "refusing to overwrite" in str(exc)
    else:
        raise AssertionError("build-prepared overwrote an existing submission")

    challenge_path = workspace / ".aau" / "challenge.json"
    challenge_path.write_bytes(challenge_path.read_bytes() + b" ")
    try:
        module.check_prepared(workspace)
    except ValueError as exc:
        assert "origin bytes do not match" in str(exc)
    else:
        raise AssertionError("protected challenge tampering was accepted")

    forged = tmp_path / "forged-origin"
    module.prepare_workspace("a2a-mcp-authority-relay-2026-01", forged)
    protected_template = forged / ".aau" / "responses.template.json"
    protected_template.write_bytes(protected_template.read_bytes() + b" ")
    manifest_path = forged / ".aau" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    template_entry = next(
        item for item in manifest["files"]
        if item["path"] == "responses.template.json"
    )
    payload = protected_template.read_bytes()
    template_entry["sha256"] = hashlib.sha256(payload).hexdigest()
    template_entry["bytes"] = len(payload)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    try:
        module.verify_prepared_origin(forged)
    except ValueError as exc:
        assert "differs from the current upstream template" in str(exc)
    else:
        raise AssertionError("a self-consistent but non-upstream template was accepted")


def test_every_open_challenge_produces_a_current_oracle_free_workspace(tmp_path):
    module = campaign_module()
    for entry in module.open_challenges():
        workspace = tmp_path / entry["challenge_id"]
        origin = module.prepare_workspace(entry["challenge_id"], workspace)
        checked_origin, challenge = module.verify_prepared_origin(workspace)
        responses = json.loads((workspace / "responses.json").read_text())
        assert checked_origin == origin
        assert len(challenge["tasks"]) == entry["task_count"]
        assert {row["task_id"] for row in responses["responses"]} == {
            row["task_id"] for row in challenge["tasks"]
        }
        serialized = "\n".join(
            path.read_text() for path in workspace.rglob("*") if path.is_file()
        )
        assert "gold_outcome" not in serialized
        assert "gold_actions" not in serialized


def test_prepare_rejects_closed_challenge(tmp_path):
    module = campaign_module()
    try:
        module.prepare_workspace(
            "portable-agent-assurance-2026-01", tmp_path / "closed"
        )
    except ValueError as exc:
        assert "closed" in str(exc)
    else:
        raise AssertionError("a closed challenge produced a new workspace")


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
    review["reviewed_on"] = "2026-08-30"
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
    campaign_lock = module.build_campaign_lock(campaign, registry)
    (campaign_root / "campaign-lock.json").write_text(
        json.dumps(campaign_lock, indent=2) + "\n"
    )

    try:
        module.plan_acceptance(
            challenge["challenge_id"],
            pack,
            "outside-reproducer-early",
            "2026-08-28",
            tmp_path / "early-plan",
        )
    except ValueError as exc:
        assert "cannot precede the pack review date" in str(exc)
    else:
        raise AssertionError("acceptance before review was planned")
    assert not (tmp_path / "early-plan").exists()

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
        "accepted-reproductions.proposed.json", "campaign-lock.proposed.json",
        "campaign.proposed.json",
    }
    proposed_lock = json.loads((out / "campaign-lock.proposed.json").read_text())
    assert proposed_lock["lock_sha256"] == plan["proposed_campaign_lock_sha256"]


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
