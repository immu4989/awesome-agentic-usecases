#!/usr/bin/env python3
"""Reference stdin/stdout adapter for incident-triage.

Replace ``decide`` with a call into your agent. Keep the four-field response
contract and never return chain-of-thought, credentials, or private records.
"""

import json
import sys


OUTCOMES = {'routine': 'route_standard_queue', 'human': 'page_incident_commander', 'stop': 'escalate_security_and_preserve'}
RULES = [{'field': 'confirmed_data_loss', 'equals': True, 'outcome_slot': 'stop'}, {'field': 'service_impact', 'equals': 'multi_region', 'outcome_slot': 'human'}]
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
