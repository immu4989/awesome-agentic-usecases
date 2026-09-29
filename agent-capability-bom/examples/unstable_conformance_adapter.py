"""Intentionally wrong, stateful fixture. Never use this as an authorization policy.

Usage: python unstable_conformance_adapter.py /path/to/disposable-state.sqlite
Only input digests and visit counts are retained; no oracle or case IDs are used.
"""

import hashlib
import json
import sqlite3
import sys


def main() -> None:
    if len(sys.argv) != 2:
        raise ValueError("provide an explicit disposable SQLite state path")
    request = json.load(sys.stdin)
    if set(request) != {"protocol_version", "case_id", "input"}:
        raise ValueError("unexpected request fields")
    if request["protocol_version"] != "aau-agent-authority-adapter/1.1":
        raise ValueError("unsupported protocol")
    key = hashlib.sha256(json.dumps(request["input"], sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()
    connection = sqlite3.connect(sys.argv[1])
    try:
        with connection:
            connection.execute("CREATE TABLE IF NOT EXISTS visits (input_digest TEXT PRIMARY KEY, count INTEGER NOT NULL)")
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT count FROM visits WHERE input_digest = ?", (key,)).fetchone()
            count = 1 if row is None else row[0] + 1
            connection.execute("INSERT OR REPLACE INTO visits VALUES (?, ?)", (key, count))
    finally:
        connection.close()
    reason = "FIXTURE_ODD_VISIT" if count % 2 else "FIXTURE_EVEN_VISIT"
    json.dump({"decision": "block", "reason_codes": [reason]}, sys.stdout)


if __name__ == "__main__":
    main()
