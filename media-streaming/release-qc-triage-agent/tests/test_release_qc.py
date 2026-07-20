import json

import pytest

from aau_harness import CostTracker, run_tool_agent
from release_qc_agent.agent import SUBMIT_TOOL, SYSTEM_PROMPT, MockBackend
from release_qc_agent.evaluate import evaluate, score_run
from release_qc_agent.tools import TOOL_SCHEMAS, execute_tool
from release_qc_agent.world import (
    generate_scenarios,
    gold_triage,
    search_policy,
)


def test_generator_is_deterministic():
    a = [s.as_dict() for s in generate_scenarios(n=30, seed=19)]
    b = [s.as_dict() for s in generate_scenarios(n=30, seed=19)]
    assert a == b


def test_gold_rules_cover_queues_and_actions():
    scenarios = generate_scenarios(n=120, seed=19)
    assert {s.gold_queue for s in scenarios} == {
        "video-eng", "audio-eng", "timed-text", "no-defect"
    }
    assert {s.gold_action for s in scenarios} == {
        "waive_and_release", "vendor_redelivery", "expedite_internal_fix",
        "delay_release", "escalate_to_release_board",
    }


def test_caption_rule_outranks_severity():
    """A minor caption defect in a covered territory can never be waived, even
    inside the release window where minor defects normally ship."""
    flag = {"creative_intent_match": False, "component": "timed_text",
            "severity": "minor", "is_caption_defect": True}
    covered = {"cvaa_covered": True, "days_to_premiere": 2, "tier": "standard"}
    assert gold_triage(flag, covered) == ("timed-text", "expedite_internal_fix")
    # too little time to fix in house -> the release moves, still never waived
    tight = {"cvaa_covered": True, "days_to_premiere": 1, "tier": "tentpole"}
    assert gold_triage(flag, tight) == ("timed-text", "delay_release")


def test_caption_rule_does_not_over_generalize():
    """Outside covered territories the same defect is an ordinary minor defect."""
    flag = {"creative_intent_match": False, "component": "timed_text",
            "severity": "minor", "is_caption_defect": True}
    uncovered = {"cvaa_covered": False, "days_to_premiere": 2, "tier": "standard"}
    assert gold_triage(flag, uncovered) == ("timed-text", "waive_and_release")


def test_creative_intent_outranks_everything():
    flag = {"creative_intent_match": True, "component": "audio",
            "severity": "major", "is_caption_defect": False}
    title = {"cvaa_covered": True, "days_to_premiere": 1, "tier": "tentpole"}
    assert gold_triage(flag, title) == ("no-defect", "waive_and_release")


def test_board_escalation_requires_unfixable_tentpole_in_window():
    flag = {"creative_intent_match": False, "component": "video",
            "severity": "major", "is_caption_defect": False}
    tentpole = {"cvaa_covered": False, "days_to_premiere": 3, "tier": "tentpole"}
    assert gold_triage(flag, tentpole)[1] == "escalate_to_release_board"
    standard = {**tentpole, "tier": "standard"}
    assert gold_triage(flag, standard)[1] == "delay_release"


def test_qc_flag_tool_hides_generator_bookkeeping():
    """creative_intent_match must not leak through get_qc_flag — the agent has to
    reach intent via check_creative_annotations."""
    sc = next(s for s in generate_scenarios(n=30, seed=19)
              if s.archetype == "INTENTIONAL_CREATIVE")
    flag = json.loads(execute_tool("get_qc_flag", {"asset_id": sc.asset_id}, sc))
    assert "creative_intent_match" not in flag
    ann = json.loads(execute_tool("check_creative_annotations",
                                  {"asset_id": sc.asset_id}, sc))
    assert any(a["covers_flagged_range"] for a in ann["annotations"])


def test_distractor_annotations_do_not_cover_flagged_range():
    scenarios = generate_scenarios(n=30, seed=19)
    distractors = [s for s in scenarios
                   if s.archetype != "INTENTIONAL_CREATIVE" and s.annotations]
    assert distractors, "need non-matching annotations as distractors"
    for s in distractors:
        assert not any(a["covers_flagged_range"] for a in s.annotations)
        assert s.gold_queue != "no-defect"


def test_tools_answer_only_for_this_scenario():
    sc = generate_scenarios(n=1, seed=19)[0]
    ok = json.loads(execute_tool("get_release_context", {"title_id": sc.title_id}, sc))
    assert ok["days_to_premiere"] == sc.title["days_to_premiere"]
    miss = json.loads(execute_tool("get_release_context", {"title_id": "TTL-0"}, sc))
    assert "error" in miss


def test_policy_search_finds_accessibility_block():
    docs = search_policy("caption defect waiver accessibility")
    assert any(d["id"] == "RQ-CVAA-01" for d in docs)


def test_tool_schemas_are_strict():
    for schema in TOOL_SCHEMAS:
        assert schema["strict"] is True
        assert schema["input_schema"]["additionalProperties"] is False
        assert set(schema["input_schema"]["required"]) == set(
            schema["input_schema"]["properties"]
        )


def test_mock_agent_end_to_end_submits():
    sc = generate_scenarios(n=1, seed=19)[0]
    cost = CostTracker(model="mock")
    run = run_tool_agent(
        MockBackend(), SYSTEM_PROMPT, TOOL_SCHEMAS, sc.flag_text,
        lambda n, i: execute_tool(n, i, sc), SUBMIT_TOOL, cost,
    )
    assert run.submitted
    assert [c["name"] for c in run.tool_calls][:4] == [
        "get_release_context", "get_qc_flag",
        "check_creative_annotations", "search_release_policy",
    ]


def test_mock_eval_error_comes_from_caption_gap():
    scenarios = generate_scenarios(n=30, seed=19)
    agg = evaluate(scenarios, backend_kind="mock", repeats=2)
    assert agg.metric_means["queue_accuracy"] == 1.0, "mock routes correctly"
    assert 0.5 <= agg.metric_means["action_accuracy"] < 1.0, "caption gap must cost it"
    assert agg.metric_means["submitted"] == 1.0
    assert agg.total_cost_usd == 0.0


def test_generator_includes_both_caption_branches():
    scenarios = generate_scenarios(n=30, seed=19)
    caps = [s for s in scenarios if s.archetype == "CAPTION_SYNC"]
    assert any(s.title["cvaa_covered"] for s in caps), "need covered-territory captions"
    assert any(not s.title["cvaa_covered"] for s in caps), "need the over-generalization trap"


def test_score_run_unsubmitted_is_zero():
    sc = generate_scenarios(n=1, seed=19)[0]

    class Dead:
        submitted = False
        submission = None

    assert score_run(sc, Dead()) == {
        "queue_accuracy": 0.0, "action_accuracy": 0.0,
        "exact_match": 0.0, "submitted": 0.0,
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
