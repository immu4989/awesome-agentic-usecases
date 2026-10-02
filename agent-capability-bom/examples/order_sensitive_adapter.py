"""Intentionally broken position-based policy fixture, never a real authorization gate.

Usage: python order_sensitive_adapter.py disposable.sqlite cycle_length
Retains one visit counter, not request inputs or expected answers.
"""

import json
import sqlite3
import sys


def main() -> None:
    if len(sys.argv) != 3:
        raise ValueError("provide a disposable SQLite path and cycle length")
    period = int(sys.argv[2])
    if not 1 <= period <= 100000:
        raise ValueError("cycle length must be 1 to 100000")
    request = json.load(sys.stdin)
    if set(request) != {"protocol_version", "case_id", "input"}:
        raise ValueError("unexpected request fields")
    if request["protocol_version"] != "aau-agent-authority-adapter/1.1":
        raise ValueError("unsupported protocol")
    connection = sqlite3.connect(sys.argv[1])
    try:
        with connection:
            connection.execute("CREATE TABLE IF NOT EXISTS position (id INTEGER PRIMARY KEY CHECK(id = 1), count INTEGER NOT NULL)")
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT count FROM position WHERE id = 1").fetchone()
            count = 0 if row is None else row[0]
            connection.execute("INSERT OR REPLACE INTO position VALUES (1, ?)", (count + 1,))
    finally:
        connection.close()
    json.dump({"decision": "block", "reason_codes": [f"FIXTURE_SLOT_{count % period:06d}"]}, sys.stdout)


if __name__ == "__main__":
    main()
