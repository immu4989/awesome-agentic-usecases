import json
import os

import pytest
from exception_triage_agent.world import (
    ESCALATION_VALUE_USD,
    generate_scenarios,
    gold_triage,
)

from exception_triage_drift.drift import (
    ARCHETYPES,
    ARMS,
    DETECTABLE,
    archetype_for,
    recovering_step,
    served_view,
)
from exception_triage_drift.evaluate import evaluate
from exception_triage_drift.tools import TOOL_SCHEMAS, DriftSession

SCS = generate_scenarios(30, 7)


def find(arch):
    return [s for i, s in enumerate(SCS) if archetype_for(i) == arch]


# ---- the corruption must move the answer, and the gold must not move ------------------

def test_every_corruption_would_flip_the_decision():
    """A corruption the gold rule doesn't read would measure nothing."""
    for i, s in enumerate(SCS):
        arch = archetype_for(i)
        if arch == "CLEAN":
            continue
        view = served_view(s, arch)["shipment"]
        if arch == "DEGRADED_PARTIAL":
            assert view["value_usd"] is None and view["customer_tier"] is None
            continue
        assert gold_triage(view) != gold_triage(s.shipment), (s.scenario_id, arch)


def test_gold_never_moves_regardless_of_archetype():
    for i, s in enumerate(SCS):
        served_view(s, archetype_for(i))
        assert (s.gold_queue, s.gold_action) == gold_triage(s.shipment)


def test_stale_flips_across_the_escalation_threshold_both_ways():
    highs = lows = 0
    for s in find("STALE_SNAPSHOT"):
        v = served_view(s, "STALE_SNAPSHOT")["shipment"]["value_usd"]
        highs += v > ESCALATION_VALUE_USD
        lows += v <= ESCALATION_VALUE_USD
    assert highs and lows, "corruption should push both directions across the threshold"


def test_conflicting_code_always_changes_the_queue():
    """Swapping within a queue (DAMAGED vs LOST are both carrier-claims) corrupts the
    record without moving the decision, which measures nothing."""
    from exception_triage_agent.world import EXCEPTIONS
    for s in find("SOURCE_CONFLICT"):
        served = served_view(s, "SOURCE_CONFLICT")["shipment"]["exception_code"]
        true = s.shipment["exception_code"]
        assert EXCEPTIONS[served][0] != EXCEPTIONS[true][0], s.scenario_id


def test_corruption_is_stable_across_processes():
    """Python's built-in hash() is salted per process; using it here would make the
    scenarios irreproducible between runs and silently break the determinism bar."""
    import subprocess
    import sys
    import json as _json
    code = (
        "import json;"
        "from exception_triage_agent.world import generate_scenarios;"
        "from exception_triage_drift.drift import served_view, archetype_for;"
        "scs=generate_scenarios(30,7);"
        "print(json.dumps([served_view(s, archetype_for(i))['shipment']['exception_code']"
        " for i,s in enumerate(scs)]))"
    )
    runs = [
        _json.loads(subprocess.run([sys.executable, "-c", code], capture_output=True,
                                   text=True, check=True,
                                   env={**os.environ, "PYTHONHASHSEED": seed}).stdout)
        for seed in ("0", "12345")
    ]
    assert runs[0] == runs[1], "corruption must not depend on the process hash seed"


def test_archetypes_are_balanced_and_complete():
    seen = {archetype_for(i) for i in range(len(SCS))}
    assert seen == set(ARCHETYPES)


def test_only_three_archetypes_are_detectable():
    assert set(DETECTABLE) == {"STALE_SNAPSHOT", "SOURCE_CONFLICT", "DEGRADED_PARTIAL"}
    assert recovering_step("SILENT_WRONG") is None
    assert recovering_step("CLEAN") is None


# ---- what the tools serve --------------------------------------------------------------

def test_stale_read_carries_a_marker_and_refresh_returns_truth():
    s = find("STALE_SNAPSHOT")[0]
    sess = DriftSession(s, "STALE_SNAPSHOT", "drift")
    cached = json.loads(sess("lookup_shipment", {"tracking_id": s.tracking_id}))
    assert cached.get("cached") is True and "as_of" in cached
    assert cached["value_usd"] != s.shipment["value_usd"]
    live = json.loads(sess("lookup_shipment", {"tracking_id": s.tracking_id, "refresh": True}))
    assert live["value_usd"] == s.shipment["value_usd"]
    assert sess.refreshed is True


def test_silent_wrong_is_undetectable_and_refresh_does_not_help():
    s = find("SILENT_WRONG")[0]
    sess = DriftSession(s, "SILENT_WRONG", "drift")
    served = json.loads(sess("lookup_shipment", {"tracking_id": s.tracking_id}))
    assert "cached" not in served and "degraded" not in served
    again = json.loads(sess("lookup_shipment", {"tracking_id": s.tracking_id, "refresh": True}))
    assert again["value_usd"] == served["value_usd"] != s.shipment["value_usd"]


def test_carrier_feed_always_tells_the_truth():
    s = find("SOURCE_CONFLICT")[0]
    sess = DriftSession(s, "SOURCE_CONFLICT", "drift")
    rec = json.loads(sess("lookup_shipment", {"tracking_id": s.tracking_id}))
    feed = json.loads(sess("get_carrier_status", {"tracking_id": s.tracking_id}))
    exc = next(e for e in feed["events"] if e["scan"] == "EXCEPTION")
    assert rec["exception_code"] != s.shipment["exception_code"]      # the record lies
    assert exc["exception_code"] == s.shipment["exception_code"]      # the feed does not


def test_lookup_schema_exposes_refresh():
    t = next(t for t in TOOL_SCHEMAS if t["name"] == "lookup_shipment")
    assert "refresh" in t["input_schema"]["properties"]


def test_policy_search_surfaces_the_source_of_truth_doc():
    s = SCS[0]
    sess = DriftSession(s, "CLEAN", "drift")
    docs = json.loads(sess("search_policy", {"query": "conflicting record source of truth"}))
    assert any(d["id"] == "POL-SRC-07" for d in docs)


# ---- arms ------------------------------------------------------------------------------

def test_clean_arm_serves_truth_even_for_corrupt_archetypes():
    s = find("SILENT_WRONG")[0]
    sess = DriftSession(s, "SILENT_WRONG", "clean")
    served = json.loads(sess("lookup_shipment", {"tracking_id": s.tracking_id}))
    assert served["value_usd"] == s.shipment["value_usd"]


def test_gate_repairs_detectable_corruption_without_a_refresh():
    for arch in DETECTABLE:
        s = find(arch)[0]
        sess = DriftSession(s, arch, "freshness_gate")
        served = json.loads(sess("lookup_shipment", {"tracking_id": s.tracking_id}))
        assert served["value_usd"] == s.shipment["value_usd"], arch
        assert served["exception_code"] == s.shipment["exception_code"], arch
        assert sess.refreshed is False   # repaired by the environment, not by the agent


def test_gate_cannot_repair_silent_wrong():
    s = find("SILENT_WRONG")[0]
    sess = DriftSession(s, "SILENT_WRONG", "freshness_gate")
    served = json.loads(sess("lookup_shipment", {"tracking_id": s.tracking_id}))
    assert served["value_usd"] != s.shipment["value_usd"]


def test_unknown_arm_rejected():
    with pytest.raises(ValueError):
        evaluate(SCS[:3], backend_kind="mock", arm="bogus")


# ---- end to end ------------------------------------------------------------------------

def test_clean_arm_beats_drift_arm_on_the_same_scenarios():
    clean = evaluate(SCS, backend_kind="mock", repeats=1, arm="clean")
    drift = evaluate(SCS, backend_kind="mock", repeats=1, arm="drift")
    assert clean.metric_means["action_accuracy"] > drift.metric_means["action_accuracy"]
    assert clean.metric_means["acted_on_stale"] == 0.0


def test_mock_acts_on_stale_because_it_never_refreshes():
    agg = evaluate(SCS, backend_kind="mock", repeats=1, arm="drift")
    assert agg.metric_means["acted_on_stale"] > 0.0
    assert agg.metric_means["noticed"] == 0.0
    for r in agg.results:
        if r.detail["detectable"]:
            assert r.detail["refreshed"] is False


def test_gate_arm_recovers_accuracy_but_is_capped_by_silent_wrong():
    drift = evaluate(SCS, backend_kind="mock", repeats=1, arm="drift")
    gate = evaluate(SCS, backend_kind="mock", repeats=1, arm="freshness_gate")
    assert gate.metric_means["action_accuracy"] > drift.metric_means["action_accuracy"]
    wrong = [r for r in gate.results
             if r.detail["archetype"] == "SILENT_WRONG" and r.metrics["action_accuracy"] == 0.0]
    assert wrong, "silent-wrong must still cost the gate arm some accuracy"


def test_all_arms_run():
    for arm in ARMS:
        agg = evaluate(SCS[:10], backend_kind="mock", repeats=1, arm=arm)
        assert agg.n_scenarios == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
