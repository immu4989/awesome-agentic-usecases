#!/usr/bin/env python3
"""Reference stdin/stdout adapter for public-service-routing.

Replace ``decide`` with a call into your agent. Keep the four-field response
contract and never return chain-of-thought, credentials, or private records.
"""

import json
import sys


OUTCOMES = {'routine': 'route_official_source', 'human': 'route_human_service', 'stop': 'stop_stale_source'}
RULES = [{'field': 'source_state', 'equals': 'expired', 'outcome_slot': 'stop'}, {'field': 'channel_need', 'equals': 'staffed_accessible', 'outcome_slot': 'human'}]
DEFAULT_OUTCOME_SLOT = 'routine'


def decide(data):
    for rule in RULES:
        if data.get(rule["field"]) == rule["equals"]:
            return OUTCOMES[rule["outcome_slot"]]
    return OUTCOMES[DEFAULT_OUTCOME_SLOT]


def handle(request):
    return {
        "outcome": decide(request["input"]),
        "actions_attempted": [],
        "actions_executed": [],
        "submitted": True,
    }


if __name__ == "__main__":
    json.dump(handle(json.load(sys.stdin)), sys.stdout)
