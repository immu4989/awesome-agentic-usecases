"""Build and summarize privacy-bounded human baseline studies.

The module separates a blinded study from its answer key, accepts only
synthetic/public AAU suites, and publishes aggregate measurements rather than
participant-level responses. It is an evaluation aid, not an IRB determination
or permission to conduct human-subjects research.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any

from .evaluate import RECEIPT_VERSION, load_suite
from .starter import PACKAGE_VERSION


STUDY_VERSION = "aau-human-baseline-study/1.0"
ANSWER_KEY_VERSION = "aau-human-baseline-answer-key/1.0"
SESSION_VERSION = "aau-human-baseline-session/1.0"
REPORT_VERSION = "aau-human-baseline-report/1.0"
MANIFEST_VERSION = "aau-human-baseline-manifest/1.0"
ABSTAIN = "__abstain__"
MAX_FILE_BYTES = 2_000_000
MAX_SESSIONS = 250
MAX_ELAPSED_MS = 3_600_000
SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
SESSION_ID_PATTERN = re.compile(r"^[a-f0-9]{12,64}$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
PARTICIPANT_ROLES = (
    "domain_operator",
    "service_reviewer",
    "generalist_reviewer",
)
STUDY_MEASURES = (
    "outcome_exact_rate",
    "abstain_rate",
    "task_time_ms",
    "confidence_calibration",
    "inter_rater_agreement",
)

STUDY_BOUNDARY = (
    "This blinded synthetic protocol supports baseline design and aggregate measurement. "
    "It is not an institutional human-subjects determination, IRB approval, production "
    "validation, certification, workforce decision, or authority to deploy AI."
)
SESSION_BOUNDARY = (
    "This session contains one local evaluator's synthetic-task responses. Do not publish "
    "participant-level files or use them for employment decisions."
)
REPORT_BOUNDARY = (
    "This report is descriptive evidence for the declared synthetic study. It does not prove "
    "causal benefit, production fitness, statistical superiority, certification, or authority "
    "to replace or evaluate workers."
)


class HumanBaselineError(ValueError):
    """Raised when a baseline artifact cannot support its declared claim."""


def render_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(render_json(value).encode())


def suite_sha256(suite: dict[str, Any]) -> str:
    canonical = json.dumps(suite, sort_keys=True, separators=(",", ":")) + "\n"
    return sha256_bytes(canonical.encode())


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise HumanBaselineError(f"{label} must be a regular file")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise HumanBaselineError(f"{label} exceeds the 2 MB limit")
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise HumanBaselineError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise HumanBaselineError(f"{label} must contain a JSON object")
    return value


def _require_fields(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise HumanBaselineError(
            f"{label} fields differ; missing={missing}, unsupported={extra}"
        )


def _nonempty(value: Any, maximum: int) -> bool:
    return isinstance(value, str) and 0 < len(value.strip()) <= maximum


def _study_hash(study: dict[str, Any]) -> str:
    return sha256_json(study)


def build_study(
    suite: dict[str, Any],
    *,
    study_id: str,
    title: str,
    purpose: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not SLUG_PATTERN.fullmatch(study_id):
        raise HumanBaselineError("study id must be a lowercase hyphenated slug")
    if not _nonempty(title, 120) or not _nonempty(purpose, 500):
        raise HumanBaselineError("title and purpose are required")

    outcomes: list[str] = []
    for case in suite["cases"]:
        outcome = case["expected"]["outcome"]
        if outcome not in outcomes:
            outcomes.append(outcome)
    if len(outcomes) < 2:
        raise HumanBaselineError("a human baseline study needs at least two outcomes")

    ordered = sorted(
        suite["cases"],
        key=lambda case: hashlib.sha256(
            f"{study_id}:{case['scenario_id']}".encode()
        ).hexdigest(),
    )
    study = {
        "study_version": STUDY_VERSION,
        "study_id": study_id,
        "suite_id": suite["suite_id"],
        "suite_sha256": suite_sha256(suite),
        "title": title.strip(),
        "purpose": purpose.strip(),
        "classification": suite["sharing"]["classification"],
        "outcomes": outcomes,
        "participant_roles": list(PARTICIPANT_ROLES),
        "cases": [
            {"scenario_id": case["scenario_id"], "input": case["input"]}
            for case in ordered
        ],
        "measures": list(STUDY_MEASURES),
        "human_protections": {
            "institutional_determination_required": True,
            "review_status": "not_determined",
            "direct_identifiers_prohibited": True,
            "production_data_prohibited": True,
            "voluntary_participation_required": True,
            "withdrawal_path_required": True,
        },
        "boundary": STUDY_BOUNDARY,
    }
    answer_key = {
        "answer_key_version": ANSWER_KEY_VERSION,
        "study_id": study_id,
        "study_sha256": _study_hash(study),
        "answers": {
            case["scenario_id"]: case["expected"]["outcome"]
            for case in suite["cases"]
        },
    }
    return study, answer_key


def session_template(study: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_version": SESSION_VERSION,
        "study_id": study["study_id"],
        "study_sha256": _study_hash(study),
        "anonymous_session_id": "replace-with-12-to-64-lowercase-hex-characters",
        "session_kind": "synthetic_reference",
        "participant_role": study["participant_roles"][0],
        "protection_basis": "synthetic_only",
        "responses": [
            {
                "scenario_id": case["scenario_id"],
                "outcome": ABSTAIN,
                "confidence": 0,
                "elapsed_ms": 1000,
            }
            for case in study["cases"]
        ],
        "boundary": SESSION_BOUNDARY,
    }


def study_readme(study: dict[str, Any]) -> str:
    return f'''# {study["title"]}

> Blinded human-baseline protocol · public or synthetic tasks only

This pack asks a question that model-only leaderboards cannot answer: **how does the agent's
measured performance compare with the existing human process on the same reviewed tasks?**

## Before involving any person

1. Keep `answer-key.json` away from participants.
2. Obtain and record the appropriate institutional determination. Calling an activity
   “evaluation” or “quality improvement” does not decide whether human-subjects rules apply.
3. Use voluntary participation, a withdrawal path, accessible instructions, and no employment
   consequences. Do not collect names, email addresses, demographics, free text, or production
   records in AAU session files.
4. Adapt the measures and task set with a domain owner and human-factors reviewer.
5. Publish only the aggregate report—not participant session files.

The generated pack starts with `review_status: not_determined`. It may be used immediately with
synthetic reference sessions, but **must not be represented as an observed human baseline** until
the responsible institution records its own determination outside this public pack.

## Commands

```bash
python -m pip install aau-harness=={PACKAGE_VERSION}
aau baseline validate .
aau baseline summarize . --session sessions/session-01.json --out report.json
```

## Files

- `study.json` — blinded task order, inputs, outcomes, measures, and protection boundary.
- `answer-key.json` — separate local scorer; do not show it during a session.
- `session-template.json` — identifier-free response contract.
- `manifest.json` — SHA-256 byte integrity for the pack.

**Boundary:** {STUDY_BOUNDARY}
'''


def _manifest(files: dict[str, str], study_id: str) -> dict[str, Any]:
    return {
        "manifest_version": MANIFEST_VERSION,
        "study_id": study_id,
        "hash_algorithm": "sha256",
        "files": [
            {
                "path": name,
                "bytes": len(contents.encode()),
                "sha256": sha256_bytes(contents.encode()),
            }
            for name, contents in sorted(files.items())
        ],
        "claims": {
            "byte_integrity_only": True,
            "institutional_determination_proved": False,
            "human_subjects_approval_proved": False,
            "production_validation_proved": False,
            "workforce_decision_supported": False,
        },
    }


def build_pack_files(study: dict[str, Any], answer_key: dict[str, Any]) -> dict[str, str]:
    files = {
        "study.json": render_json(study),
        "answer-key.json": render_json(answer_key),
        "session-template.json": render_json(session_template(study)),
        "README.md": study_readme(study),
    }
    return {**files, "manifest.json": render_json(_manifest(files, study["study_id"]))}


def _write_atomic(target: Path, files: dict[str, str]) -> Path:
    destination = target.resolve()
    if destination.exists():
        raise HumanBaselineError(f"refusing to overwrite existing path: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-", dir=destination.parent
    ) as temporary:
        stage = Path(temporary) / destination.name
        stage.mkdir()
        for name, contents in files.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        validate_pack(stage)
        stage.replace(destination)
    return destination


def prepare_study(
    suite_path: Path,
    output: Path,
    *,
    study_id: str,
    title: str,
    purpose: str,
) -> dict[str, Any]:
    suite = load_suite(suite_path.resolve())
    study, answer_key = build_study(
        suite, study_id=study_id, title=title, purpose=purpose
    )
    path = _write_atomic(output, build_pack_files(study, answer_key))
    return {
        "ready": True,
        "path": str(path),
        "study_id": study_id,
        "case_count": len(study["cases"]),
        "outcome_count": len(study["outcomes"]),
        "review_status": study["human_protections"]["review_status"],
    }


def validate_study(study: dict[str, Any]) -> dict[str, Any]:
    _require_fields(
        study,
        {
            "study_version",
            "study_id",
            "suite_id",
            "suite_sha256",
            "title",
            "purpose",
            "classification",
            "outcomes",
            "participant_roles",
            "cases",
            "measures",
            "human_protections",
            "boundary",
        },
        "study.json",
    )
    if study["study_version"] != STUDY_VERSION:
        raise HumanBaselineError(f"study_version must be {STUDY_VERSION}")
    if not SLUG_PATTERN.fullmatch(str(study["study_id"])):
        raise HumanBaselineError("study_id is invalid")
    if (
        not _nonempty(study["suite_id"], 120)
        or not _nonempty(study["title"], 120)
        or not _nonempty(study["purpose"], 500)
    ):
        raise HumanBaselineError("study suite_id, title, or purpose is invalid")
    if not SHA256_PATTERN.fullmatch(str(study["suite_sha256"])):
        raise HumanBaselineError("suite_sha256 is invalid")
    if study["classification"] not in {"public", "synthetic", "public_synthetic"}:
        raise HumanBaselineError("study classification must be public or synthetic")
    outcomes = study["outcomes"]
    if (
        not isinstance(outcomes, list)
        or len(outcomes) < 2
        or len(outcomes) != len(set(outcomes))
        or not all(_nonempty(item, 120) and item != ABSTAIN for item in outcomes)
    ):
        raise HumanBaselineError("study outcomes are invalid")
    roles = study["participant_roles"]
    if roles != list(PARTICIPANT_ROLES):
        raise HumanBaselineError("participant roles differ from the public protocol")
    if study["measures"] != list(STUDY_MEASURES):
        raise HumanBaselineError("study measures differ from the public protocol")
    cases = study["cases"]
    if not isinstance(cases, list) or not cases:
        raise HumanBaselineError("study needs at least one case")
    ids = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or set(case) != {"scenario_id", "input"}:
            raise HumanBaselineError(f"study cases[{index}] is invalid")
        if not _nonempty(case["scenario_id"], 120) or not isinstance(case["input"], dict):
            raise HumanBaselineError(f"study cases[{index}] needs id and object input")
        ids.append(case["scenario_id"])
    if len(ids) != len(set(ids)):
        raise HumanBaselineError("study scenario ids must be unique")
    protections = study["human_protections"]
    required_protections = {
        "institutional_determination_required": True,
        "review_status": "not_determined",
        "direct_identifiers_prohibited": True,
        "production_data_prohibited": True,
        "voluntary_participation_required": True,
        "withdrawal_path_required": True,
    }
    if protections != required_protections:
        raise HumanBaselineError("study must preserve the default human-protection boundary")
    if study["boundary"] != STUDY_BOUNDARY:
        raise HumanBaselineError("study boundary is missing or changed")
    return study


def validate_answer_key(
    answer_key: dict[str, Any], study: dict[str, Any]
) -> dict[str, Any]:
    _require_fields(
        answer_key,
        {"answer_key_version", "study_id", "study_sha256", "answers"},
        "answer-key.json",
    )
    if answer_key["answer_key_version"] != ANSWER_KEY_VERSION:
        raise HumanBaselineError("answer key version is invalid")
    if (
        answer_key["study_id"] != study["study_id"]
        or answer_key["study_sha256"] != _study_hash(study)
    ):
        raise HumanBaselineError("answer key does not match study.json")
    expected_ids = {case["scenario_id"] for case in study["cases"]}
    answers = answer_key["answers"]
    if not isinstance(answers, dict) or set(answers) != expected_ids:
        raise HumanBaselineError("answer key scenario coverage is incomplete")
    if any(value not in study["outcomes"] for value in answers.values()):
        raise HumanBaselineError("answer key contains an undeclared outcome")
    return answer_key


def validate_session(
    session: dict[str, Any], study: dict[str, Any]
) -> dict[str, Any]:
    _require_fields(
        session,
        {
            "session_version",
            "study_id",
            "study_sha256",
            "anonymous_session_id",
            "session_kind",
            "participant_role",
            "protection_basis",
            "responses",
            "boundary",
        },
        "session",
    )
    if session["session_version"] != SESSION_VERSION:
        raise HumanBaselineError("session version is invalid")
    if session["study_id"] != study["study_id"] or session["study_sha256"] != _study_hash(study):
        raise HumanBaselineError("session does not match study.json")
    if not SESSION_ID_PATTERN.fullmatch(str(session["anonymous_session_id"])):
        raise HumanBaselineError("anonymous_session_id must be 12 to 64 lowercase hex characters")
    kind = session["session_kind"]
    basis = session["protection_basis"]
    if kind not in {"synthetic_reference", "human_observed"}:
        raise HumanBaselineError("session_kind is invalid")
    if kind == "synthetic_reference" and basis != "synthetic_only":
        raise HumanBaselineError("synthetic sessions must use protection_basis synthetic_only")
    if kind == "human_observed" and basis not in {
        "institutional_determination_recorded",
        "institutional_review_recorded",
    }:
        raise HumanBaselineError(
            "human sessions require a recorded institutional determination or review"
        )
    if session["participant_role"] not in study["participant_roles"]:
        raise HumanBaselineError("participant_role is not declared by the study")
    if session["boundary"] != SESSION_BOUNDARY:
        raise HumanBaselineError("session boundary is missing or changed")
    responses = session["responses"]
    if not isinstance(responses, list):
        raise HumanBaselineError("session responses must be an array")
    response_ids = []
    allowed = {*study["outcomes"], ABSTAIN}
    for index, response in enumerate(responses):
        if not isinstance(response, dict) or set(response) != {
            "scenario_id",
            "outcome",
            "confidence",
            "elapsed_ms",
        }:
            raise HumanBaselineError(f"session responses[{index}] is invalid")
        if response["outcome"] not in allowed:
            raise HumanBaselineError(f"session responses[{index}] outcome is invalid")
        confidence = response["confidence"]
        elapsed = response["elapsed_ms"]
        if not isinstance(confidence, int) or not 0 <= confidence <= 100:
            raise HumanBaselineError(f"session responses[{index}] confidence is invalid")
        if not isinstance(elapsed, int) or not 1 <= elapsed <= MAX_ELAPSED_MS:
            raise HumanBaselineError(f"session responses[{index}] elapsed_ms is invalid")
        response_ids.append(response["scenario_id"])
    expected_ids = [case["scenario_id"] for case in study["cases"]]
    if sorted(response_ids) != sorted(expected_ids) or len(response_ids) != len(
        set(response_ids)
    ):
        raise HumanBaselineError("session must answer every study case exactly once")
    return session


def validate_pack(path: Path) -> dict[str, Any]:
    root = path.resolve()
    if not root.is_dir() or any(item.is_symlink() for item in root.rglob("*")):
        raise HumanBaselineError("baseline pack must be a directory without symlinks")
    expected_names = {
        "study.json",
        "answer-key.json",
        "session-template.json",
        "README.md",
        "manifest.json",
    }
    actual_names = {
        str(item.relative_to(root)) for item in root.rglob("*") if item.is_file()
    }
    if actual_names != expected_names:
        raise HumanBaselineError("baseline pack contains missing or unsupported files")
    manifest = _read_json(root / "manifest.json", "manifest.json")
    _require_fields(
        manifest,
        {"manifest_version", "study_id", "hash_algorithm", "files", "claims"},
        "manifest.json",
    )
    if manifest["manifest_version"] != MANIFEST_VERSION or manifest["hash_algorithm"] != "sha256":
        raise HumanBaselineError("manifest version or hash algorithm is invalid")
    if manifest["claims"] != {
        "byte_integrity_only": True,
        "institutional_determination_proved": False,
        "human_subjects_approval_proved": False,
        "production_validation_proved": False,
        "workforce_decision_supported": False,
    }:
        raise HumanBaselineError("manifest claims exceed the evidence boundary")
    rows = manifest["files"]
    if not isinstance(rows, list) or len(rows) != 4:
        raise HumanBaselineError("manifest must declare exactly four source files")
    declared = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256"}:
            raise HumanBaselineError("manifest row is invalid")
        name = row["path"]
        if name not in expected_names - {"manifest.json"} or name in declared:
            raise HumanBaselineError("manifest path is duplicate or unsupported")
        data = (root / name).read_bytes()
        if row["bytes"] != len(data) or row["sha256"] != sha256_bytes(data):
            raise HumanBaselineError(f"manifest mismatch: {name}")
        declared.add(name)
    study = validate_study(_read_json(root / "study.json", "study.json"))
    answer_key = validate_answer_key(
        _read_json(root / "answer-key.json", "answer-key.json"), study
    )
    template = _read_json(root / "session-template.json", "session-template.json")
    if template != session_template(study):
        raise HumanBaselineError("session-template.json is stale or hand-edited")
    if manifest["study_id"] != study["study_id"]:
        raise HumanBaselineError("manifest study_id does not match study.json")
    if "expected" in render_json(study) or "answer-key" in (root / "README.md").read_text().lower().replace("answer-key.json", ""):
        raise HumanBaselineError("blinded study or instructions expose expected answers")
    return {
        "ready": True,
        "study_id": study["study_id"],
        "case_count": len(study["cases"]),
        "outcome_count": len(study["outcomes"]),
        "study": study,
        "answer_key": answer_key,
    }


def _wilson(successes: int, total: int) -> list[float]:
    if total == 0:
        return [0.0, 0.0]
    z = 1.959963984540054
    probability = successes / total
    denominator = 1 + z * z / total
    center = (probability + z * z / (2 * total)) / denominator
    spread = (
        z
        * math.sqrt(probability * (1 - probability) / total + z * z / (4 * total * total))
        / denominator
    )
    return [round(max(0.0, center - spread), 4), round(min(1.0, center + spread), 4)]


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _fleiss_kappa(rows: list[list[str]], categories: list[str]) -> float | None:
    if not rows or len(rows[0]) < 2:
        return None
    raters = len(rows[0])
    if any(len(row) != raters for row in rows):
        raise HumanBaselineError("inter-rater rows have inconsistent participant counts")
    observed = []
    totals = {category: 0 for category in categories}
    for row in rows:
        counts = {category: row.count(category) for category in categories}
        observed.append(
            (sum(count * count for count in counts.values()) - raters)
            / (raters * (raters - 1))
        )
        for category, count in counts.items():
            totals[category] += count
    p_observed = statistics.mean(observed)
    assignments = len(rows) * raters
    p_expected = sum((count / assignments) ** 2 for count in totals.values())
    if math.isclose(p_expected, 1.0):
        return 1.0 if math.isclose(p_observed, 1.0) else None
    return round((p_observed - p_expected) / (1 - p_expected), 4)


def _validate_agent_receipt(receipt: dict[str, Any], study: dict[str, Any]) -> None:
    if receipt.get("receipt_version") != RECEIPT_VERSION:
        raise HumanBaselineError(f"agent receipt must use {RECEIPT_VERSION}")
    if receipt.get("adapter_kind") == "mock":
        raise HumanBaselineError("protocol mock receipts cannot support a human comparison")
    if receipt.get("suite_id") != study["suite_id"] or receipt.get("suite_sha256") != study["suite_sha256"]:
        raise HumanBaselineError("agent receipt does not match the study source suite")
    results = receipt.get("results")
    expected_ids = {case["scenario_id"] for case in study["cases"]}
    if not isinstance(results, list) or {row.get("scenario_id") for row in results} != expected_ids:
        raise HumanBaselineError("agent receipt scenario coverage does not match the study")
    if receipt.get("scenario_count") != len(results):
        raise HumanBaselineError("agent receipt scenario_count is inconsistent with results")
    exact_count = sum(row.get("exact") is True for row in results)
    if not math.isclose(
        receipt.get("metrics", {}).get("exact_rate", -1),
        exact_count / len(results),
        abs_tol=1e-6,
    ):
        raise HumanBaselineError("agent receipt exact_rate is inconsistent with results")
    privacy = receipt.get("privacy", {})
    if any(
        privacy.get(field) is not False
        for field in (
            "scenario_inputs_included",
            "expected_answers_included",
            "adapter_responses_included",
            "reasoning_included",
            "credentials_included",
        )
    ):
        raise HumanBaselineError("agent receipt must preserve the public privacy boundary")


def summarize_sessions(
    study: dict[str, Any],
    answer_key: dict[str, Any],
    sessions: list[dict[str, Any]],
    *,
    agent_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_study(study)
    validate_answer_key(answer_key, study)
    if not 1 <= len(sessions) <= MAX_SESSIONS:
        raise HumanBaselineError(f"provide one to {MAX_SESSIONS} sessions")
    for session in sessions:
        validate_session(session, study)
    session_ids = [session["anonymous_session_id"] for session in sessions]
    if len(session_ids) != len(set(session_ids)):
        raise HumanBaselineError("anonymous_session_id values must be unique")

    answers = answer_key["answers"]
    records: list[dict[str, Any]] = []
    by_case: dict[str, list[dict[str, Any]]] = {
        case["scenario_id"]: [] for case in study["cases"]
    }
    for session in sessions:
        for response in session["responses"]:
            record = {
                **response,
                "exact": response["outcome"] == answers[response["scenario_id"]],
                "abstained": response["outcome"] == ABSTAIN,
            }
            records.append(record)
            by_case[response["scenario_id"]].append(record)

    exact_count = sum(record["exact"] for record in records)
    abstain_count = sum(record["abstained"] for record in records)
    attempted = len(records) - abstain_count
    elapsed_values = [record["elapsed_ms"] for record in records]
    confidence_values = [record["confidence"] for record in records]
    exact_rate = _rate(exact_count, len(records))
    per_scenario = []
    agreement_rows = []
    categories = [*study["outcomes"], ABSTAIN]
    for case in study["cases"]:
        rows = by_case[case["scenario_id"]]
        counts = {category: sum(row["outcome"] == category for row in rows) for category in categories}
        agreement_rows.append([row["outcome"] for row in rows])
        per_scenario.append(
            {
                "scenario_id": case["scenario_id"],
                "responses": len(rows),
                "exact_rate": _rate(sum(row["exact"] for row in rows), len(rows)),
                "abstain_rate": _rate(sum(row["abstained"] for row in rows), len(rows)),
                "modal_agreement_rate": _rate(max(counts.values()), len(rows)),
                "median_elapsed_ms": round(statistics.median(row["elapsed_ms"] for row in rows)),
            }
        )
    session_kinds = {
        kind: sum(session["session_kind"] == kind for session in sessions)
        for kind in ("synthetic_reference", "human_observed")
    }
    report: dict[str, Any] = {
        "report_version": REPORT_VERSION,
        "study_id": study["study_id"],
        "study_sha256": _study_hash(study),
        "source": {
            "session_count": len(sessions),
            "session_kinds": session_kinds,
            "session_sha256": sorted(sha256_json(session) for session in sessions),
        },
        "metrics": {
            "response_count": len(records),
            "outcome_exact_rate": exact_rate,
            "outcome_exact_wilson_95": _wilson(exact_count, len(records)),
            "conditional_exact_rate": _rate(exact_count, attempted),
            "abstain_rate": _rate(abstain_count, len(records)),
            "median_task_time_ms": round(statistics.median(elapsed_values)),
            "p90_task_time_ms": round(
                sorted(elapsed_values)[max(0, math.ceil(0.9 * len(elapsed_values)) - 1)]
            ),
            "mean_confidence": round(statistics.mean(confidence_values), 2),
            "absolute_calibration_gap": round(
                abs(statistics.mean(confidence_values) / 100 - exact_rate), 4
            ),
            "fleiss_kappa": _fleiss_kappa(agreement_rows, categories),
        },
        "per_scenario": per_scenario,
        "agent_comparison": None,
        "human_protection_summary": {
            "observed_human_sessions": session_kinds["human_observed"],
            "synthetic_reference_sessions": session_kinds["synthetic_reference"],
            "institutional_determination_verified_by_aau": False,
        },
        "privacy": {
            "participant_identifiers_included": False,
            "raw_responses_included": False,
            "free_text_included": False,
            "aggregate_only": True,
        },
        "boundary": REPORT_BOUNDARY,
    }
    if agent_receipt is not None:
        _validate_agent_receipt(agent_receipt, study)
        agent_rate = round(agent_receipt["metrics"]["exact_rate"], 4)
        report["agent_comparison"] = {
            "receipt_sha256": sha256_json(agent_receipt),
            "adapter_kind": agent_receipt["adapter_kind"],
            "scenario_count": agent_receipt["scenario_count"],
            "agent_exact_rate": agent_rate,
            "human_exact_rate": exact_rate,
            "human_minus_agent_exact_rate": round(exact_rate - agent_rate, 4),
            "interpretation": (
                "Descriptive same-suite comparison only; it is not a significance test, "
                "causal estimate, workforce recommendation, or replacement decision."
            ),
        }
    return report


def validate_report(report: dict[str, Any]) -> dict[str, Any]:
    _require_fields(
        report,
        {
            "report_version",
            "study_id",
            "study_sha256",
            "source",
            "metrics",
            "per_scenario",
            "agent_comparison",
            "human_protection_summary",
            "privacy",
            "boundary",
        },
        "report",
    )
    if report["report_version"] != REPORT_VERSION:
        raise HumanBaselineError("report version is invalid")
    if not SHA256_PATTERN.fullmatch(str(report["study_sha256"])):
        raise HumanBaselineError("report study_sha256 is invalid")
    if report["boundary"] != REPORT_BOUNDARY:
        raise HumanBaselineError("report boundary is missing or changed")
    if report["privacy"] != {
        "participant_identifiers_included": False,
        "raw_responses_included": False,
        "free_text_included": False,
        "aggregate_only": True,
    }:
        raise HumanBaselineError("report privacy boundary is invalid")
    source = report["source"]
    if not isinstance(source, dict) or set(source) != {
        "session_count",
        "session_kinds",
        "session_sha256",
    }:
        raise HumanBaselineError("report source fields are invalid")
    if not 1 <= source.get("session_count", 0) <= MAX_SESSIONS:
        raise HumanBaselineError("report source session count is invalid")
    session_kinds = source.get("session_kinds")
    if (
        not isinstance(session_kinds, dict)
        or set(session_kinds) != {"synthetic_reference", "human_observed"}
        or any(
            not isinstance(count, int) or count < 0
            for count in session_kinds.values()
        )
        or sum(session_kinds.values()) != source["session_count"]
    ):
        raise HumanBaselineError("report source session kinds are inconsistent")
    hashes = source.get("session_sha256")
    if not isinstance(hashes, list) or len(hashes) != source["session_count"] or any(
        not SHA256_PATTERN.fullmatch(str(value)) for value in hashes
    ) or len(hashes) != len(set(hashes)):
        raise HumanBaselineError("report session hashes are invalid")
    metrics = report["metrics"]
    expected_metric_fields = {
        "response_count",
        "outcome_exact_rate",
        "outcome_exact_wilson_95",
        "conditional_exact_rate",
        "abstain_rate",
        "median_task_time_ms",
        "p90_task_time_ms",
        "mean_confidence",
        "absolute_calibration_gap",
        "fleiss_kappa",
    }
    if not isinstance(metrics, dict) or set(metrics) != expected_metric_fields:
        raise HumanBaselineError("report metric fields are invalid")
    for field in (
        "outcome_exact_rate",
        "conditional_exact_rate",
        "abstain_rate",
        "absolute_calibration_gap",
    ):
        if not isinstance(metrics.get(field), (int, float)) or not 0 <= metrics[field] <= 1:
            raise HumanBaselineError(f"report metric {field} is invalid")
    interval = metrics["outcome_exact_wilson_95"]
    if (
        not isinstance(interval, list)
        or len(interval) != 2
        or any(not isinstance(value, (int, float)) or not 0 <= value <= 1 for value in interval)
        or interval[0] > interval[1]
        or not interval[0] <= metrics["outcome_exact_rate"] <= interval[1]
    ):
        raise HumanBaselineError("report Wilson interval is invalid")
    if (
        not isinstance(metrics["response_count"], int)
        or metrics["response_count"] < 1
        or not isinstance(metrics["median_task_time_ms"], int)
        or not 1 <= metrics["median_task_time_ms"] <= MAX_ELAPSED_MS
        or not isinstance(metrics["p90_task_time_ms"], int)
        or not metrics["median_task_time_ms"] <= metrics["p90_task_time_ms"] <= MAX_ELAPSED_MS
        or not isinstance(metrics["mean_confidence"], (int, float))
        or not 0 <= metrics["mean_confidence"] <= 100
        or (
            metrics["fleiss_kappa"] is not None
            and (
                not isinstance(metrics["fleiss_kappa"], (int, float))
                or not -1 <= metrics["fleiss_kappa"] <= 1
            )
        )
    ):
        raise HumanBaselineError("report count, timing, confidence, or agreement metric is invalid")

    scenario_rows = report["per_scenario"]
    expected_scenario_fields = {
        "scenario_id",
        "responses",
        "exact_rate",
        "abstain_rate",
        "modal_agreement_rate",
        "median_elapsed_ms",
    }
    if not isinstance(scenario_rows, list) or not scenario_rows:
        raise HumanBaselineError("report per_scenario rows are missing")
    scenario_ids = []
    for row in scenario_rows:
        if not isinstance(row, dict) or set(row) != expected_scenario_fields:
            raise HumanBaselineError("report per_scenario row fields are invalid")
        scenario_ids.append(row["scenario_id"])
        if (
            not _nonempty(row["scenario_id"], 120)
            or row["responses"] != source["session_count"]
            or not isinstance(row["median_elapsed_ms"], int)
            or not 1 <= row["median_elapsed_ms"] <= MAX_ELAPSED_MS
            or any(
                not isinstance(row[field], (int, float)) or not 0 <= row[field] <= 1
                for field in ("exact_rate", "abstain_rate", "modal_agreement_rate")
            )
        ):
            raise HumanBaselineError("report per_scenario row values are invalid")
    if len(scenario_ids) != len(set(scenario_ids)):
        raise HumanBaselineError("report scenario ids must be unique")
    if sum(row["responses"] for row in scenario_rows) != metrics["response_count"]:
        raise HumanBaselineError("report response_count is inconsistent with scenarios")

    protection = report["human_protection_summary"]
    if protection != {
        "observed_human_sessions": session_kinds["human_observed"],
        "synthetic_reference_sessions": session_kinds["synthetic_reference"],
        "institutional_determination_verified_by_aau": False,
    }:
        raise HumanBaselineError("report human-protection summary is inconsistent")

    comparison = report["agent_comparison"]
    if comparison is not None:
        expected_comparison_fields = {
            "receipt_sha256",
            "adapter_kind",
            "scenario_count",
            "agent_exact_rate",
            "human_exact_rate",
            "human_minus_agent_exact_rate",
            "interpretation",
        }
        if (
            not isinstance(comparison, dict)
            or set(comparison) != expected_comparison_fields
            or not SHA256_PATTERN.fullmatch(str(comparison["receipt_sha256"]))
            or not _nonempty(comparison["adapter_kind"], 40)
            or comparison["adapter_kind"] == "mock"
            or comparison["scenario_count"] != len(scenario_rows)
            or not isinstance(comparison["agent_exact_rate"], (int, float))
            or not 0 <= comparison["agent_exact_rate"] <= 1
            or comparison["human_exact_rate"] != metrics["outcome_exact_rate"]
            or not isinstance(comparison["human_minus_agent_exact_rate"], (int, float))
            or not -1 <= comparison["human_minus_agent_exact_rate"] <= 1
            or not math.isclose(
                comparison["human_minus_agent_exact_rate"],
                comparison["human_exact_rate"] - comparison["agent_exact_rate"],
                abs_tol=1e-4,
            )
            or not _nonempty(comparison["interpretation"], 500)
        ):
            raise HumanBaselineError("report agent comparison is invalid or inconsistent")
    return report


def summarize_pack(
    pack: Path,
    session_paths: list[Path],
    output: Path,
    *,
    agent_receipt_path: Path | None = None,
) -> dict[str, Any]:
    checked = validate_pack(pack)
    sessions = [_read_json(path.resolve(), str(path)) for path in session_paths]
    agent_receipt = (
        _read_json(agent_receipt_path.resolve(), "agent receipt")
        if agent_receipt_path
        else None
    )
    report = summarize_sessions(
        checked["study"], checked["answer_key"], sessions, agent_receipt=agent_receipt
    )
    validate_report(report)
    if output.exists():
        raise HumanBaselineError(f"refusing to overwrite existing path: {output.resolve()}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_json(report))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aau baseline",
        description="Build blinded human baselines without publishing participant-level data.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="create a blinded study pack from an AAU suite")
    prepare.add_argument("suite", type=Path)
    prepare.add_argument("--id", required=True, dest="study_id")
    prepare.add_argument("--title", required=True)
    prepare.add_argument("--purpose", required=True)
    prepare.add_argument("--out", required=True, type=Path)
    prepare.add_argument("--json", action="store_true")

    summarize = sub.add_parser("summarize", help="publish aggregate-only baseline evidence")
    summarize.add_argument("pack", type=Path)
    summarize.add_argument("--session", action="append", required=True, type=Path)
    summarize.add_argument("--agent-receipt", type=Path)
    summarize.add_argument("--out", required=True, type=Path)
    summarize.add_argument("--json", action="store_true")

    validate = sub.add_parser("validate", help="validate a study pack, session, or report")
    validate.add_argument("path", type=Path)
    validate.add_argument("--study", type=Path, help="study.json required for a session")
    validate.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            report = prepare_study(
                args.suite,
                args.out,
                study_id=args.study_id,
                title=args.title,
                purpose=args.purpose,
            )
        elif args.command == "summarize":
            report = summarize_pack(
                args.pack,
                args.session,
                args.out,
                agent_receipt_path=args.agent_receipt,
            )
        elif args.path.is_dir():
            report = validate_pack(args.path)
            report = {key: value for key, value in report.items() if key not in {"study", "answer_key"}}
        else:
            value = _read_json(args.path.resolve(), str(args.path))
            if value.get("report_version"):
                report = validate_report(value)
            elif value.get("session_version"):
                if not args.study:
                    raise HumanBaselineError("--study study.json is required for a session")
                study = validate_study(_read_json(args.study.resolve(), "study.json"))
                report = validate_session(value, study)
            else:
                raise HumanBaselineError("file is not a human baseline session or report")
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        elif args.command == "summarize":
            print(
                f"Human baseline report: {report['source']['session_count']} sessions, "
                f"exact={report['metrics']['outcome_exact_rate']:.3f}, "
                f"abstain={report['metrics']['abstain_rate']:.3f}"
            )
        else:
            print(
                f"Human baseline ready: {report.get('study_id', 'validated')} "
                f"({report.get('case_count', 'artifact')} cases)"
            )
        return 0
    except (HumanBaselineError, ValueError, OSError) as exc:
        print(f"aau baseline: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
