"""The reference adapter must satisfy every declared synthetic case."""

import json
import unittest
from pathlib import Path

from adapter_command import handle


class AdapterContractTest(unittest.TestCase):
    def test_declared_outcomes_and_forbidden_actions(self):
        suite = json.loads(Path("suite.json").read_text())
        for case in suite["cases"]:
            request = {
                "protocol_version": "aau-byo-agent-request/1.0",
                "suite_id": suite["suite_id"],
                "scenario_id": case["scenario_id"],
                "input": case["input"],
            }
            response = handle(request)
            self.assertEqual(response["outcome"], case["expected"]["outcome"])
            self.assertFalse(set(response["actions_attempted"]) & set(case["forbidden_actions"]))
            self.assertFalse(set(response["actions_executed"]) & set(case["forbidden_actions"]))


if __name__ == "__main__":
    unittest.main()
