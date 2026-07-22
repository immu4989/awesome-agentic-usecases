import json

import pytest

from refund_guarded.evaluate import evaluate
from refund_guarded.guarded import COMMIT_NUDGE, GuardedSession
from refund_resolution_agent.agent import SYSTEM_PROMPT
from refund_resolution_agent.tools import ToolSession
from refund_resolution_agent.world import generate_scenarios


def verified(session, sc):
    session("verify_identity", {"ticket_id": sc.ticket_id})
    return session


def test_guard_refuses_forbidden_payout():
    sc = next(s for s in generate_scenarios(30, 23) if s.archetype == "CHARGEBACK_PENDING")
    session = verified(GuardedSession(sc), sc)
    out = json.loads(session("issue_refund", {"order_id": sc.order_id, "amount_usd": 10}))
    assert out["executed"] is False
    assert out["refused_by"] == "policy engine"
    assert "chargeback" in out["reason"].lower()
    assert session.blocked == ["issue_refund"]


def test_guard_allows_permitted_payout():
    sc = next(s for s in generate_scenarios(30, 23) if s.archetype == "IN_WINDOW_DEFECT")
    session = verified(GuardedSession(sc), sc)
    out = json.loads(session("issue_refund", {"order_id": sc.order_id, "amount_usd": 10}))
    assert out["executed"] is True
    assert session.blocked == []


def test_guard_matches_the_scorer_exactly():
    """The tool layer must refuse precisely the actions the scorer counts as unsafe,
    otherwise the intervention is measuring something other than the policy."""
    for sc in generate_scenarios(30, 23):
        session = verified(GuardedSession(sc), sc)
        for action in ("issue_refund", "send_replacement"):
            payload = {"order_id": sc.order_id}
            if action == "issue_refund":
                payload["amount_usd"] = 1
            out = json.loads(session(action, payload))
            refused = out.get("executed") is False and "refused_by" in out
            assert refused == (action in sc.forbidden_actions), (
                f"{sc.scenario_id} {sc.archetype}: {action} refused={refused} "
                f"but forbidden={action in sc.forbidden_actions}")


def test_guard_leaves_read_tools_untouched():
    sc = generate_scenarios(1, 23)[0]
    guarded, plain = GuardedSession(sc), ToolSession(sc)
    for s in (guarded, plain):
        s("verify_identity", {"ticket_id": sc.ticket_id})
    a = json.loads(guarded("get_order", {"order_id": sc.order_id}))
    b = json.loads(plain("get_order", {"order_id": sc.order_id}))
    assert a == b


def test_enforced_variant_does_not_touch_the_prompt():
    """Isolating the tool layer requires the prompt to be byte-identical."""
    from refund_guarded import evaluate as ev
    assert COMMIT_NUDGE not in SYSTEM_PROMPT
    # the module builds prompt = SYSTEM_PROMPT + nudge only for commit variants
    src = open(ev.__file__).read()
    assert 'if variant in ("commit", "both")' in src


def test_commit_variant_uses_plain_session():
    """commit must not silently inherit the tool-layer guard, or the A/B mixes both."""
    scenarios = generate_scenarios(6, 23)
    agg = evaluate(scenarios, backend_kind="mock", repeats=1, variant="commit")
    assert agg.metric_means["blocked_attempt"] == 0.0


def test_enforced_eval_blocks_and_reports():
    scenarios = generate_scenarios(30, 23)
    agg = evaluate(scenarios, backend_kind="mock", repeats=1, variant="enforced")
    m = agg.metric_means
    assert m["blocked_attempt"] > 0.0, "the mock's chargeback gap must trip the guard"
    assert m["no_unsafe_action"] == 1.0, "nothing forbidden can execute under enforcement"
    assert "recovered_after_block" in m


def test_unknown_variant_rejected():
    with pytest.raises(ValueError):
        evaluate(generate_scenarios(1, 23), backend_kind="mock", variant="nonsense")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
