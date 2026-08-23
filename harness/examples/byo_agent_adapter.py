#!/usr/bin/env python3
"""Minimal stdin/stdout adapter for the AAU BYO-agent protocol."""

import json
import sys


request = json.load(sys.stdin)
scenario = request["input"]
if scenario["source_state"] == "expired":
    outcome = "stop_stale_source"
elif scenario["channel_need"] == "staffed_accessible":
    outcome = "route_human_service"
else:
    outcome = "route_official_source"
json.dump(
    {
        "outcome": outcome,
        "actions_attempted": [],
        "actions_executed": [],
        "submitted": True,
    },
    sys.stdout,
)
