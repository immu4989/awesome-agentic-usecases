"""Deterministic public-synthetic adapter for the Agent Release Gate example."""

import json
import sys


request = json.load(sys.stdin)
facts = request["input"]
actions_attempted = []

if facts["monitor"] != "available":
    outcome = "pause"
elif facts["authority"] != "active":
    outcome = "block"
elif facts["policy_epoch"] != "synthetic-18":
    outcome = "block"
elif facts["destination"] != "records.internal.test":
    outcome = "block"
elif facts["operation"] == "prepare_write":
    outcome = "human_review"
    actions_attempted = ["records.prepare"]
else:
    outcome = "allow"
    actions_attempted = ["records.read"]

print(
    json.dumps(
        {
            "outcome": outcome,
            "actions_attempted": actions_attempted,
            "actions_executed": [],
            "submitted": True,
        }
    )
)
