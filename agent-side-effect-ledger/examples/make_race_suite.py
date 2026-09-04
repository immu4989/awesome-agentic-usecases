"""Build the deterministic public-synthetic ASEL race suite."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


INTENT_A = "a" * 64
INTENT_B = "b" * 64
INTENT_C = "c" * 64


def _attempts(case_id: str, specs: list[tuple[str, str, bool, bool]]) -> list[dict]:
    return [
        {
            "attempt_id": f"{case_id}-W{index:02d}",
            "idempotency_key": key,
            "intent_sha256": intent,
            "authority_valid": authority,
            "approval_valid": approval,
        }
        for index, (key, intent, authority, approval) in enumerate(specs, 1)
    ]


def _expected(
    effect: int, committed: int, replayed: int, conflict: int, blocked: int
) -> dict:
    return {
        "effect_count": effect,
        "key_count": effect,
        "committed_count": committed,
        "replayed_count": replayed,
        "conflict_count": conflict,
        "blocked_count": blocked,
    }


def build() -> dict:
    cases = []

    def add(
        case_id: str,
        title: str,
        specs: list[tuple[str, str, bool, bool]],
        expected: dict,
    ) -> None:
        cases.append(
            {
                "case_id": case_id,
                "title": title,
                "attempts": _attempts(case_id, specs),
                "expected": expected,
            }
        )

    add(
        "RACE-TWO-IDENTICAL",
        "Two authorized workers submit the same exact intent and key",
        [("shared-two", INTENT_A, True, True)] * 2,
        _expected(1, 1, 1, 0, 0),
    )
    add(
        "RACE-FOUR-IDENTICAL",
        "Four authorized workers submit the same exact intent and key",
        [("shared-four", INTENT_A, True, True)] * 4,
        _expected(1, 1, 3, 0, 0),
    )
    add(
        "RACE-EIGHT-IDENTICAL",
        "Eight authorized workers submit the same exact intent and key",
        [("shared-eight", INTENT_A, True, True)] * 8,
        _expected(1, 1, 7, 0, 0),
    )
    add(
        "RACE-CHANGED-INTENT",
        "Two intent variants collide on one idempotency key",
        [
            ("changed-intent", INTENT_A, True, True),
            ("changed-intent", INTENT_B, True, True),
            ("changed-intent", INTENT_A, True, True),
            ("changed-intent", INTENT_B, True, True),
        ],
        _expected(1, 1, 1, 2, 0),
    )
    add(
        "RACE-UNIQUE-KEYS",
        "Four distinct authorized keys preserve legitimate parallel effects",
        [(f"unique-{index}", INTENT_A, True, True) for index in range(1, 5)],
        _expected(4, 4, 0, 0, 0),
    )
    add(
        "RACE-APPROVAL-MISSING",
        "Concurrent attempts share a key but no valid approval",
        [("approval-missing", INTENT_A, True, False)] * 4,
        _expected(0, 0, 0, 0, 4),
    )
    add(
        "RACE-AUTHORITY-INVALID",
        "Concurrent attempts share a key but authority is invalid",
        [("authority-invalid", INTENT_A, False, True)] * 4,
        _expected(0, 0, 0, 0, 4),
    )
    add(
        "RACE-MIXED-AUTHORITY",
        "One authorized attempt races three invalid-authority attempts",
        [("mixed-authority", INTENT_A, True, True)]
        + [("mixed-authority", INTENT_A, False, True)] * 3,
        _expected(1, 1, 0, 0, 3),
    )
    add(
        "RACE-DISTINCT-KEYS-SAME-INTENT",
        "The same intent under two distinct keys remains two effects",
        [
            ("intent-copy-a", INTENT_A, True, True),
            ("intent-copy-b", INTENT_A, True, True),
        ],
        _expected(2, 2, 0, 0, 0),
    )
    add(
        "RACE-SIXTEEN-IDENTICAL",
        "Sixteen fresh workers contend on one exact key and intent",
        [("shared-sixteen", INTENT_A, True, True)] * 16,
        _expected(1, 1, 15, 0, 0),
    )
    add(
        "RACE-THREE-INTENTS-ONE-KEY",
        "Three different intents collide on one idempotency key",
        [
            ("three-intents", INTENT_A, True, True),
            ("three-intents", INTENT_B, True, True),
            ("three-intents", INTENT_C, True, True),
        ],
        _expected(1, 1, 0, 2, 0),
    )
    add(
        "RACE-TWO-GROUPS",
        "Two independent keys each receive three concurrent attempts",
        [("group-a", INTENT_A, True, True)] * 3
        + [("group-b", INTENT_B, True, True)] * 3,
        _expected(2, 2, 4, 0, 0),
    )
    return {
        "suite_version": "aau-agent-side-effect-race-suite/0.1",
        "suite_id": "asel-concurrent-workers-2026-09",
        "title": "Public-synthetic concurrent side-effect attempts",
        "profile": {"operation_id": "synthetic-benefit-notice-create"},
        "cases": cases,
        "boundaries": {
            "public_synthetic_only": True,
            "oracle_withheld_from_adapter": True,
            "fresh_process_per_attempt": True,
            "post_race_state_inspection": True,
            "no_production_target": True,
            "concurrent_launch_is_not_scheduler_proof": True,
            "adapter_scoped_not_exactly_once": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.out.is_symlink():
        raise SystemExit(f"refusing to overwrite: {args.out}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(build(), indent=2) + "\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
