"""SQLite-backed public-synthetic adapter for the ASEL process race lab."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from aau_race_lab import PROTOCOL_VERSION  # noqa: E402


def _contains_oracle(value: object) -> bool:
    if isinstance(value, dict):
        return "expected" in value or any(_contains_oracle(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_oracle(item) for item in value)
    return False


def _connect(state_dir: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(state_dir / "effects.sqlite3", timeout=15)
    connection.execute("PRAGMA busy_timeout = 15000")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS effects ("
        "idempotency_key TEXT PRIMARY KEY, intent_sha256 TEXT NOT NULL, effect_count INTEGER NOT NULL)"
    )
    return connection


def _attempt(request: dict[str, object], state_dir: Path) -> dict[str, object]:
    attempt = request["attempt"]
    assert isinstance(attempt, dict)
    reasons = []
    if not attempt["approval_valid"]:
        reasons.append("APPROVAL_INVALID")
    if not attempt["authority_valid"]:
        reasons.append("AUTHORITY_INVALID")
    if reasons:
        return {
            "attempt_id": attempt["attempt_id"],
            "outcome": "blocked",
            "reason_codes": sorted(reasons),
        }
    connection = _connect(state_dir)
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT intent_sha256 FROM effects WHERE idempotency_key = ?",
            (attempt["idempotency_key"],),
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO effects (idempotency_key, intent_sha256, effect_count) VALUES (?, ?, 1)",
                (attempt["idempotency_key"], attempt["intent_sha256"]),
            )
            outcome, reasons = "committed", []
        elif existing[0] == attempt["intent_sha256"]:
            outcome, reasons = "replayed", ["IDEMPOTENT_RESULT_REPLAY"]
        else:
            outcome, reasons = "conflict", ["IDEMPOTENCY_KEY_REUSED_FOR_DIFFERENT_INTENT"]
        connection.commit()
    finally:
        connection.close()
    return {
        "attempt_id": attempt["attempt_id"],
        "outcome": outcome,
        "reason_codes": reasons,
    }


def _inspect(request: dict[str, object], state_dir: Path) -> dict[str, object]:
    connection = _connect(state_dir)
    try:
        effect_count, key_count = connection.execute(
            "SELECT COALESCE(SUM(effect_count), 0), COUNT(*) FROM effects"
        ).fetchone()
    finally:
        connection.close()
    return {
        "case_id": request["case_id"],
        "effect_count": effect_count,
        "key_count": key_count,
    }


def main() -> int:
    request = json.load(sys.stdin)
    if request.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("unsupported race adapter protocol")
    if _contains_oracle(request):
        raise ValueError("race adapter request leaked expected evidence")
    phase = request.get("phase")
    expected_keys = (
        {"protocol_version", "phase", "suite_id", "case_id", "worker_count", "state_dir", "profile", "attempt"}
        if phase == "attempt"
        else {"protocol_version", "phase", "suite_id", "case_id", "state_dir", "profile"}
    )
    if set(request) != expected_keys:
        raise ValueError("race adapter request fields changed")
    state_dir = Path(request["state_dir"])
    if state_dir.is_symlink() or not state_dir.is_dir():
        raise ValueError("state_dir must be an existing non-symbolic directory")
    if phase == "attempt":
        response = _attempt(request, state_dir)
    elif phase == "inspect":
        response = _inspect(request, state_dir)
    else:
        raise ValueError("unsupported race adapter phase")
    json.dump(response, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
