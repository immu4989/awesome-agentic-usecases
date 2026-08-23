#!/usr/bin/env python3
"""Reference stdin/stdout adapter for customer-escalation.

Replace ``decide`` with a call into your agent. Keep the four-field response
contract and never return chain-of-thought, credentials, or private records.
"""

import json
import sys


OUTCOMES = {'routine': 'route_billing_review', 'human': 'request_identity_verification', 'stop': 'escalate_safety_team'}
RULES = [{'field': 'safety_threat', 'equals': True, 'outcome_slot': 'stop'}, {'field': 'account_verified', 'equals': False, 'outcome_slot': 'human'}]
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
