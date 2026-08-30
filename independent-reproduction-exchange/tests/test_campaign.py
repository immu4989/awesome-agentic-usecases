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


def test_three_public_challenges_are_answer_free_and_bound():
    campaign = campaign_module().verify_campaign()
    assert len(campaign["challenges"]) == 3
    assert campaign["independently_reproduced_count"] == 0
    for entry in campaign["challenges"]:
        challenge = json.loads(
            (ROOT / "reproduction-challenges" / entry["path"]).read_text()
        )
        serialized = json.dumps(challenge)
        assert "gold_outcome" not in serialized
        assert "gold_actions" not in serialized
        assert len(challenge["oracle_commitment_sha256"]) == 64


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
