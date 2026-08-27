"""Validate and package public, privacy-bounded AI impact evidence.

An Impact Capsule binds existing public artifacts without turning them into a
score, certification, causal claim, institutional determination, or deployment
decision. Status is derived from evidence presence and cannot be selected by a
contributor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from .human_baseline import validate_report, validate_study


CAPSULE_VERSION = "aau-impact-capsule/1.0"
COMPARISON_VERSION = "aau-impact-comparison/1.0"
PACK_VERSION = "aau-impact-pack/1.0"
OBSERVATION_VERSION = "aau-public-value-observation/1.0"
REPRODUCTION_VERSION = "aau-impact-reproduction/1.0"
MAX_FILE_BYTES = 5_000_000
MAX_ARTIFACTS = 6
SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
DATE_PATTERN = re.compile(r"^20\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$")
URL_PATTERN = re.compile(r"^https://[^\s]+$")
STATUS_ORDER = (
    "synthetic_reference",
    "partner_sought",
    "study_reviewed",
    "aggregate_published",
    "independently_reproduced",
)
ARTIFACT_FIELDS = {
    "artifact_id",
    "kind",
    "path",
    "sha256",
    "classification",
}
PRIVACY_CONTRACT = {
    "participant_level_data_included": False,
    "direct_identifiers_included": False,
    "free_text_responses_included": False,
    "production_records_included": False,
    "credentials_included": False,
    "aggregate_only": True,
}
BOUNDARY = (
    "This capsule binds declared public artifacts and visible gaps. It does not verify identity, "
    "institutional review, causal impact, production fitness, certification, government "
    "endorsement, workforce performance, or authority to deploy or automate a protected decision."
)
OBSERVATION_BOUNDARY = (
    "This observation reports bounded aggregate measures under the declared method and "
    "limitations. It does not by itself prove causality, audited savings, universal transfer, "
    "program effectiveness, government endorsement, or authority to deploy AI."
)
REPRODUCTION_BOUNDARY = (
    "This reproduction reports an organization-attested rerun of declared public artifacts. "
    "AAU does not verify identity or independence, certify the result, resolve divergences, or "
    "authorize transfer or deployment."
)
SENSITIVE_PATTERNS = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I),
    re.compile(
        r"(?:api[_ -]?key|access[_ -]?token|client[_ -]?secret|password)\s*[:=]",
        re.I,
    ),
    re.compile(r"\b(?:TOP SECRET|SECRET//|CUI//|SOURCE SELECTION INFORMATION)\b", re.I),
)


class EvidenceCommonsError(ValueError):
    """Raised when an artifact cannot support its declared public status."""


def render_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(render_json(value).encode())


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise EvidenceCommonsError(f"{label} must be a regular file")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise EvidenceCommonsError(f"{label} exceeds the 5 MB limit")
        return path.read_bytes()
    except OSError as exc:
        raise EvidenceCommonsError(f"cannot read {label}: {exc}") from exc


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(_read_bytes(path, label))
    except json.JSONDecodeError as exc:
        raise EvidenceCommonsError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceCommonsError(f"{label} must contain a JSON object")
    return value


def _require_fields(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise EvidenceCommonsError(
            f"{label} fields differ; missing={missing}, unsupported={extra}"
        )


def _nonempty(value: Any, maximum: int = 500) -> bool:
    return isinstance(value, str) and 0 < len(value.strip()) <= maximum


def _rate(value: Any, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise EvidenceCommonsError(f"{label} must be a finite number from zero to one")
    return float(value)


def _safe_relative(value: Any, label: str) -> str:
    if not _nonempty(value, 300):
        raise EvidenceCommonsError(f"{label} must be a repository-relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise EvidenceCommonsError(f"{label} must not be absolute or traverse parents")
    if any(part in {"", ".git", ".github"} for part in path.parts):
        raise EvidenceCommonsError(f"{label} contains an unsupported path segment")
    return path.as_posix()


def _resolve_artifact(root: Path, value: str, label: str) -> Path:
    relative = _safe_relative(value, label)
    base = root.resolve()
    candidate = (base / relative).resolve()
    if candidate == base or base not in candidate.parents:
        raise EvidenceCommonsError(f"{label} resolves outside the repository root")
    return candidate


def find_repository_root(start: Path) -> Path:
    candidate = start.resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for parent in (candidate, *candidate.parents):
        if (parent / "docs" / "use-cases.json").is_file():
            return parent
    raise EvidenceCommonsError(
        "could not find the repository root; pass --root PATH for a standalone capsule"
    )


def _validate_base_artifact(
    artifact: dict[str, Any],
    *,
    label: str,
    root: Path,
    verify_file: bool,
) -> tuple[Path | None, bytes | None]:
    if not isinstance(artifact, dict):
        raise EvidenceCommonsError(f"{label} must be an object")
    if not ARTIFACT_FIELDS <= set(artifact):
        raise EvidenceCommonsError(f"{label} is missing base artifact fields")
    if not SLUG_PATTERN.fullmatch(str(artifact["artifact_id"])):
        raise EvidenceCommonsError(f"{label}.artifact_id is invalid")
    if not _nonempty(artifact["kind"], 60):
        raise EvidenceCommonsError(f"{label}.kind is invalid")
    _safe_relative(artifact["path"], f"{label}.path")
    if not SHA256_PATTERN.fullmatch(str(artifact["sha256"])):
        raise EvidenceCommonsError(f"{label}.sha256 is invalid")
    if artifact["classification"] not in {
        "synthetic",
        "public",
        "aggregate_public",
    }:
        raise EvidenceCommonsError(f"{label}.classification is not public-safe")
    if not verify_file:
        return None, None
    path = _resolve_artifact(root, artifact["path"], f"{label}.path")
    data = _read_bytes(path, label)
    if sha256_bytes(data) != artifact["sha256"]:
        raise EvidenceCommonsError(f"{label} byte hash does not match its public artifact")
    return path, data


def _validate_suite(
    artifact: dict[str, Any], root: Path, verify_file: bool
) -> dict[str, Any]:
    _require_fields(
        artifact,
        ARTIFACT_FIELDS
        | {"suite_id", "suite_kind", "scenario_count", "provenance_note"},
        "artifacts.suite",
    )
    path, data = _validate_base_artifact(
        artifact, label="artifacts.suite", root=root, verify_file=verify_file
    )
    if not _nonempty(artifact["suite_id"], 120):
        raise EvidenceCommonsError("artifacts.suite.suite_id is invalid")
    if artifact["suite_kind"] not in {"domain_scenario_jsonl", "aau_byo_suite"}:
        raise EvidenceCommonsError("artifacts.suite.suite_kind is invalid")
    if not _nonempty(artifact["provenance_note"], 500):
        raise EvidenceCommonsError("artifacts.suite.provenance_note is invalid")
    if not isinstance(artifact["scenario_count"], int) or not 1 <= artifact["scenario_count"] <= 500:
        raise EvidenceCommonsError("artifacts.suite.scenario_count is invalid")
    if verify_file and path is not None and data is not None:
        if artifact["suite_kind"] == "domain_scenario_jsonl":
            try:
                rows = [json.loads(line) for line in data.decode().splitlines() if line.strip()]
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise EvidenceCommonsError("domain scenario artifact is not JSONL") from exc
            if len(rows) != artifact["scenario_count"] or any(
                not isinstance(row, dict) or not _nonempty(row.get("scenario_id"), 120)
                for row in rows
            ):
                raise EvidenceCommonsError("domain scenario artifact coverage is inconsistent")
            ids = [row["scenario_id"] for row in rows]
            if len(ids) != len(set(ids)):
                raise EvidenceCommonsError("domain scenario ids must be unique")
        else:
            suite = _read_json(path, "AAU BYO suite")
            cases = suite.get("cases")
            if (
                suite.get("suite_id") != artifact["suite_id"]
                or not isinstance(cases, list)
                or len(cases) != artifact["scenario_count"]
            ):
                raise EvidenceCommonsError("AAU BYO suite identity or coverage is inconsistent")
    return artifact


def _validate_agent_receipt(
    artifact: dict[str, Any],
    suite: dict[str, Any],
    root: Path,
    verify_file: bool,
) -> dict[str, Any]:
    _require_fields(
        artifact,
        ARTIFACT_FIELDS
        | {
            "receipt_kind",
            "model",
            "suite_binding",
            "scenario_ids_sha256",
            "primary_metric",
        },
        "artifacts.agent_receipt",
    )
    path, _ = _validate_base_artifact(
        artifact,
        label="artifacts.agent_receipt",
        root=root,
        verify_file=verify_file,
    )
    if artifact["receipt_kind"] not in {"aau_domain_eval", "aau_byo_agent_receipt"}:
        raise EvidenceCommonsError("artifacts.agent_receipt.receipt_kind is invalid")
    if not _nonempty(artifact["model"], 120):
        raise EvidenceCommonsError("artifacts.agent_receipt.model is invalid")
    if artifact["suite_binding"] not in {"hash_bound", "scenario_ids_only"}:
        raise EvidenceCommonsError("artifacts.agent_receipt.suite_binding is invalid")
    if not SHA256_PATTERN.fullmatch(str(artifact["scenario_ids_sha256"])):
        raise EvidenceCommonsError("agent receipt scenario_ids_sha256 is invalid")
    metric = artifact["primary_metric"]
    _require_fields(
        metric,
        {
            "name",
            "value",
            "interval_95",
            "scenario_count",
            "repeats",
            "observation_count",
            "mean_cost_per_scenario_usd",
            "p50_latency_s",
        },
        "artifacts.agent_receipt.primary_metric",
    )
    if not _nonempty(metric["name"], 80):
        raise EvidenceCommonsError("agent primary metric name is invalid")
    _rate(metric["value"], "agent primary metric value")
    interval = metric["interval_95"]
    if (
        not isinstance(interval, list)
        or len(interval) != 2
        or _rate(interval[0], "agent interval lower") > _rate(interval[1], "agent interval upper")
        or not interval[0] <= metric["value"] <= interval[1]
    ):
        raise EvidenceCommonsError("agent primary metric interval is invalid")
    if (
        metric["scenario_count"] != suite["scenario_count"]
        or not isinstance(metric["repeats"], int)
        or metric["repeats"] < 1
        or metric["observation_count"] != metric["scenario_count"] * metric["repeats"]
        or type(metric["mean_cost_per_scenario_usd"]) not in (int, float)
        or metric["mean_cost_per_scenario_usd"] < 0
        or type(metric["p50_latency_s"]) not in (int, float)
        or metric["p50_latency_s"] < 0
    ):
        raise EvidenceCommonsError("agent primary metric counts, cost, or latency are invalid")
    if verify_file and path is not None:
        receipt = _read_json(path, "agent receipt")
        if artifact["receipt_kind"] == "aau_domain_eval":
            means = receipt.get("metric_means", {})
            intervals = receipt.get("metric_ci95", {})
            result_rows = receipt.get("results", [])
            scenario_ids = sorted(
                {
                    row.get("scenario_id")
                    for row in result_rows
                    if isinstance(row, dict) and isinstance(row.get("scenario_id"), str)
                }
            )
            if (
                receipt.get("model") != artifact["model"]
                or receipt.get("n_scenarios") != metric["scenario_count"]
                or receipt.get("n_repeats") != metric["repeats"]
                or len(scenario_ids) != metric["scenario_count"]
                or sha256_json(scenario_ids) != artifact["scenario_ids_sha256"]
                or means.get(metric["name"]) != metric["value"]
                or intervals.get(metric["name"]) != metric["interval_95"]
                or receipt.get("mean_cost_per_scenario_usd")
                != metric["mean_cost_per_scenario_usd"]
                or receipt.get("p50_latency_s") != metric["p50_latency_s"]
            ):
                raise EvidenceCommonsError("agent receipt summary is inconsistent with the artifact")
        else:
            if (
                receipt.get("adapter_kind") == "mock"
                or receipt.get("scenario_count") != metric["scenario_count"]
                or receipt.get("metrics", {}).get(metric["name"]) != metric["value"]
            ):
                raise EvidenceCommonsError("BYO agent receipt summary is inconsistent")
    return artifact


def _validate_optional_artifact(
    artifact: Any,
    *,
    label: str,
    expected_kind: str,
    root: Path,
    verify_file: bool,
) -> tuple[dict[str, Any] | None, Path | None]:
    if artifact is None:
        return None, None
    _require_fields(artifact, ARTIFACT_FIELDS, label)
    if artifact["kind"] != expected_kind:
        raise EvidenceCommonsError(f"{label}.kind must be {expected_kind}")
    path, _ = _validate_base_artifact(
        artifact, label=label, root=root, verify_file=verify_file
    )
    return artifact, path


def _validate_human_evidence(
    artifacts: dict[str, Any],
    suite: dict[str, Any],
    root: Path,
    verify_file: bool,
) -> None:
    study_artifact, study_path = _validate_optional_artifact(
        artifacts["human_study"],
        label="artifacts.human_study",
        expected_kind="aau_human_baseline_study",
        root=root,
        verify_file=verify_file,
    )
    study = None
    if verify_file and study_path is not None:
        study = validate_study(_read_json(study_path, "human baseline study"))
        if (
            study["suite_id"] != suite["suite_id"]
            or study["suite_sha256"] != suite["sha256"]
        ):
            raise EvidenceCommonsError(
                "human baseline study is not bound to the capsule suite"
            )
    baseline = artifacts["human_baseline"]
    if baseline is None:
        return
    if study_artifact is None:
        raise EvidenceCommonsError("a human baseline report requires its blinded study artifact")
    _require_fields(
        baseline,
        ARTIFACT_FIELDS
        | {
            "report_version",
            "study_sha256",
            "session_count",
            "observed_human_sessions",
            "exact_rate",
            "abstain_rate",
            "institutional_basis_attested",
            "institutional_basis_verified_by_aau",
        },
        "artifacts.human_baseline",
    )
    baseline_path, _ = _validate_base_artifact(
        baseline,
        label="artifacts.human_baseline",
        root=root,
        verify_file=verify_file,
    )
    if baseline["kind"] != "aau_human_baseline_report":
        raise EvidenceCommonsError("artifacts.human_baseline.kind is invalid")
    if baseline["report_version"] != "aau-human-baseline-report/1.0":
        raise EvidenceCommonsError("human baseline report version is invalid")
    if not SHA256_PATTERN.fullmatch(str(baseline["study_sha256"])):
        raise EvidenceCommonsError("human baseline study hash is invalid")
    if (
        not isinstance(baseline["session_count"], int)
        or not 1 <= baseline["session_count"] <= 250
        or not isinstance(baseline["observed_human_sessions"], int)
        or not 0 <= baseline["observed_human_sessions"] <= baseline["session_count"]
    ):
        raise EvidenceCommonsError("human baseline session counts are invalid")
    _rate(baseline["exact_rate"], "human baseline exact_rate")
    _rate(baseline["abstain_rate"], "human baseline abstain_rate")
    if type(baseline["institutional_basis_attested"]) is not bool:
        raise EvidenceCommonsError("institutional_basis_attested must be boolean")
    if baseline["institutional_basis_verified_by_aau"] is not False:
        raise EvidenceCommonsError("AAU must never claim to verify institutional review")
    if verify_file and study_path is not None and baseline_path is not None:
        if study is None:
            study = validate_study(_read_json(study_path, "human baseline study"))
        report = validate_report(_read_json(baseline_path, "human baseline report"))
        if (
            report["study_sha256"] != baseline["study_sha256"]
            or report["study_sha256"] != sha256_json(study)
            or report["source"]["session_count"] != baseline["session_count"]
            or report["human_protection_summary"]["observed_human_sessions"]
            != baseline["observed_human_sessions"]
            or report["metrics"]["outcome_exact_rate"] != baseline["exact_rate"]
            or report["metrics"]["abstain_rate"] != baseline["abstain_rate"]
        ):
            raise EvidenceCommonsError("human baseline summary is inconsistent")


def _validate_measurement_plan(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or not 2 <= len(rows) <= 8:
        raise EvidenceCommonsError("measurement_plan needs two to eight measures")
    expected = {
        "metric_id",
        "name",
        "unit",
        "direction",
        "affected_group",
        "baseline_source",
        "measurement_window",
        "method",
        "limitation",
    }
    ids = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise EvidenceCommonsError(f"measurement_plan[{index}] must be an object")
        _require_fields(row, expected, f"measurement_plan[{index}]")
        if not SLUG_PATTERN.fullmatch(str(row["metric_id"])):
            raise EvidenceCommonsError(f"measurement_plan[{index}].metric_id is invalid")
        ids.append(row["metric_id"])
        if row["direction"] not in {"increase", "decrease", "hold_zero"}:
            raise EvidenceCommonsError(f"measurement_plan[{index}].direction is invalid")
        if not all(
            _nonempty(row[field], 500)
            for field in expected - {"metric_id", "direction"}
        ):
            raise EvidenceCommonsError(f"measurement_plan[{index}] contains empty text")
    if len(ids) != len(set(ids)):
        raise EvidenceCommonsError("measurement metric ids must be unique")
    return rows


def _validate_public_value_observation(
    artifact: Any, capsule_id: str, root: Path, verify_file: bool
) -> None:
    if artifact is None:
        return
    _require_fields(
        artifact,
        ARTIFACT_FIELDS | {"observation_kind", "metric_ids", "causal_claim"},
        "artifacts.public_value_observation",
    )
    path, _ = _validate_base_artifact(
        artifact,
        label="artifacts.public_value_observation",
        root=root,
        verify_file=verify_file,
    )
    if artifact["kind"] != "aau_public_value_observation":
        raise EvidenceCommonsError("public value observation kind is invalid")
    if artifact["observation_kind"] not in {
        "descriptive_before_after",
        "descriptive_cross_sectional",
        "causal_evaluation",
    }:
        raise EvidenceCommonsError("public value observation method is invalid")
    if not isinstance(artifact["metric_ids"], list) or not artifact["metric_ids"]:
        raise EvidenceCommonsError("public value observation needs metric ids")
    if type(artifact["causal_claim"]) is not bool:
        raise EvidenceCommonsError("public value causal_claim must be boolean")
    if artifact["causal_claim"] and artifact["observation_kind"] != "causal_evaluation":
        raise EvidenceCommonsError("a causal claim requires a declared causal evaluation")
    if verify_file and path is not None:
        record = validate_public_value_record(
            _read_json(path, "public value observation")
        )
        if (
            record["capsule_id"] != capsule_id
            or record["method"] != artifact["observation_kind"]
            or record["causal_claim"] != artifact["causal_claim"]
            or {row["metric_id"] for row in record["metric_results"]}
            != set(artifact["metric_ids"])
        ):
            raise EvidenceCommonsError("public value observation summary is inconsistent")


def _validate_reproduction(
    artifact: Any,
    capsule_id: str,
    artifacts: dict[str, Any],
    root: Path,
    verify_file: bool,
) -> None:
    if artifact is None:
        return
    _require_fields(
        artifact,
        ARTIFACT_FIELDS
        | {
            "organization_id",
            "outcome",
            "independence_attested",
            "independence_verified_by_aau",
        },
        "artifacts.reproduction",
    )
    path, _ = _validate_base_artifact(
        artifact,
        label="artifacts.reproduction",
        root=root,
        verify_file=verify_file,
    )
    if artifact["kind"] != "aau_independent_reproduction":
        raise EvidenceCommonsError("reproduction artifact kind is invalid")
    if not SLUG_PATTERN.fullmatch(str(artifact["organization_id"])):
        raise EvidenceCommonsError("reproduction organization_id is invalid")
    if artifact["outcome"] not in {"reproduced", "diverged", "inconclusive"}:
        raise EvidenceCommonsError("reproduction outcome is invalid")
    if artifact["independence_attested"] is not True:
        raise EvidenceCommonsError("reproduction requires an independence attestation")
    if artifact["independence_verified_by_aau"] is not False:
        raise EvidenceCommonsError("AAU must not claim to verify reproducer identity")
    if verify_file and path is not None:
        record = validate_reproduction_record(_read_json(path, "reproduction record"))
        declared_sources = {
            row["artifact_id"]: row["sha256"] for row in record["source_artifacts"]
        }
        current_sources = {
            row["artifact_id"]: row["sha256"]
            for row in artifacts.values()
            if isinstance(row, dict) and "artifact_id" in row
        }
        required_sources = {
            artifacts["suite"]["artifact_id"],
            artifacts["agent_receipt"]["artifact_id"],
        }
        if (
            record["source_capsule_id"] != capsule_id
            or not required_sources <= set(declared_sources)
            or any(
                current_sources.get(artifact_id) != digest
                for artifact_id, digest in declared_sources.items()
            )
            or record["organization_id"] != artifact["organization_id"]
            or record["outcome"] != artifact["outcome"]
        ):
            raise EvidenceCommonsError("reproduction summary is inconsistent")


def validate_public_value_record(record: dict[str, Any]) -> dict[str, Any]:
    _require_fields(
        record,
        {
            "observation_version",
            "observation_id",
            "capsule_id",
            "method",
            "metric_results",
            "causal_claim",
            "decision",
            "privacy",
            "limitations",
            "boundary",
        },
        "public value observation",
    )
    if record["observation_version"] != OBSERVATION_VERSION:
        raise EvidenceCommonsError("public value observation version is invalid")
    if not SLUG_PATTERN.fullmatch(str(record["observation_id"])) or not SLUG_PATTERN.fullmatch(
        str(record["capsule_id"])
    ):
        raise EvidenceCommonsError("public value observation id is invalid")
    if record["method"] not in {
        "descriptive_before_after",
        "descriptive_cross_sectional",
        "causal_evaluation",
    }:
        raise EvidenceCommonsError("public value observation method is invalid")
    if type(record["causal_claim"]) is not bool or (
        record["causal_claim"] and record["method"] != "causal_evaluation"
    ):
        raise EvidenceCommonsError("public value causal claim is inconsistent with its method")
    rows = record["metric_results"]
    metric_fields = {
        "metric_id",
        "baseline_value",
        "observed_value",
        "unit",
        "direction",
        "window",
        "affected_group",
        "uncertainty",
        "limitation",
    }
    if not isinstance(rows, list) or not 1 <= len(rows) <= 8:
        raise EvidenceCommonsError("public value observation needs one to eight metric results")
    ids = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise EvidenceCommonsError(f"metric_results[{index}] must be an object")
        _require_fields(row, metric_fields, f"metric_results[{index}]")
        if not SLUG_PATTERN.fullmatch(str(row["metric_id"])):
            raise EvidenceCommonsError(f"metric_results[{index}].metric_id is invalid")
        ids.append(row["metric_id"])
        if row["direction"] not in {"increase", "decrease", "hold_zero"}:
            raise EvidenceCommonsError(f"metric_results[{index}].direction is invalid")
        if type(row["baseline_value"]) not in (int, float) or type(
            row["observed_value"]
        ) not in (int, float):
            raise EvidenceCommonsError(f"metric_results[{index}] values must be numeric")
        if not math.isfinite(row["baseline_value"]) or not math.isfinite(
            row["observed_value"]
        ):
            raise EvidenceCommonsError(f"metric_results[{index}] values must be finite")
        if not all(
            _nonempty(row[field], 500)
            for field in (
                "unit",
                "window",
                "affected_group",
                "uncertainty",
                "limitation",
            )
        ):
            raise EvidenceCommonsError(f"metric_results[{index}] text is invalid")
    if len(ids) != len(set(ids)):
        raise EvidenceCommonsError("public value metric ids must be unique")
    decision = record["decision"]
    _require_fields(decision, {"accountable_role", "outcome", "conditions"}, "decision")
    if not _nonempty(decision["accountable_role"], 200) or decision["outcome"] not in {
        "continue",
        "revise",
        "stop",
        "extend",
        "not_decided",
    }:
        raise EvidenceCommonsError("public value decision is invalid")
    if not isinstance(decision["conditions"], list) or not all(
        _nonempty(item, 300) for item in decision["conditions"]
    ):
        raise EvidenceCommonsError("public value decision conditions are invalid")
    if record["privacy"] != PRIVACY_CONTRACT:
        raise EvidenceCommonsError("public value observation must remain aggregate-only")
    if not isinstance(record["limitations"], list) or not record["limitations"] or not all(
        _nonempty(item, 500) for item in record["limitations"]
    ):
        raise EvidenceCommonsError("public value observation limitations are invalid")
    if record["boundary"] != OBSERVATION_BOUNDARY:
        raise EvidenceCommonsError("public value observation boundary is invalid")
    return record


def validate_reproduction_record(record: dict[str, Any]) -> dict[str, Any]:
    _require_fields(
        record,
        {
            "reproduction_version",
            "reproduction_id",
            "source_capsule_id",
            "source_capsule_version",
            "source_artifacts",
            "organization_id",
            "independence_attested",
            "scope",
            "environment",
            "outcome",
            "metric_checks",
            "divergences",
            "limitations",
            "privacy",
            "boundary",
        },
        "reproduction record",
    )
    if record["reproduction_version"] != REPRODUCTION_VERSION:
        raise EvidenceCommonsError("reproduction version is invalid")
    for field in ("reproduction_id", "source_capsule_id", "organization_id"):
        if not SLUG_PATTERN.fullmatch(str(record[field])):
            raise EvidenceCommonsError(f"reproduction {field} is invalid")
    if record["source_capsule_version"] != CAPSULE_VERSION:
        raise EvidenceCommonsError("reproduction source capsule version is invalid")
    source_rows = record["source_artifacts"]
    if not isinstance(source_rows, list) or not 1 <= len(source_rows) <= MAX_ARTIFACTS:
        raise EvidenceCommonsError("reproduction source_artifacts are invalid")
    source_ids = []
    for row in source_rows:
        if not isinstance(row, dict) or set(row) != {"artifact_id", "sha256"}:
            raise EvidenceCommonsError("reproduction source artifact row is invalid")
        if not SLUG_PATTERN.fullmatch(str(row["artifact_id"])) or not SHA256_PATTERN.fullmatch(
            str(row["sha256"])
        ):
            raise EvidenceCommonsError("reproduction source artifact value is invalid")
        source_ids.append(row["artifact_id"])
    if len(source_ids) != len(set(source_ids)):
        raise EvidenceCommonsError("reproduction source artifact ids must be unique")
    if record["independence_attested"] is not True:
        raise EvidenceCommonsError("reproduction independence must be contributor-attested")
    if not _nonempty(record["scope"], 700) or not _nonempty(record["environment"], 700):
        raise EvidenceCommonsError("reproduction scope or environment is invalid")
    if record["outcome"] not in {"reproduced", "diverged", "inconclusive"}:
        raise EvidenceCommonsError("reproduction outcome is invalid")
    checks = record["metric_checks"]
    check_fields = {
        "name",
        "source_value",
        "reproduced_value",
        "tolerance",
        "within_tolerance",
    }
    if not isinstance(checks, list) or not checks:
        raise EvidenceCommonsError("reproduction needs at least one metric check")
    for index, row in enumerate(checks):
        if not isinstance(row, dict):
            raise EvidenceCommonsError(f"metric_checks[{index}] must be an object")
        _require_fields(row, check_fields, f"metric_checks[{index}]")
        if not _nonempty(row["name"], 100) or type(row["within_tolerance"]) is not bool:
            raise EvidenceCommonsError(f"metric_checks[{index}] is invalid")
        if any(
            type(row[field]) not in (int, float) or not math.isfinite(row[field])
            for field in ("source_value", "reproduced_value", "tolerance")
        ) or row["tolerance"] < 0:
            raise EvidenceCommonsError(f"metric_checks[{index}] values are invalid")
        expected = abs(row["source_value"] - row["reproduced_value"]) <= row["tolerance"]
        if row["within_tolerance"] is not expected:
            raise EvidenceCommonsError(f"metric_checks[{index}] tolerance result is inconsistent")
    for field in ("divergences", "limitations"):
        if not isinstance(record[field], list) or not all(
            _nonempty(item, 500) for item in record[field]
        ):
            raise EvidenceCommonsError(f"reproduction {field} is invalid")
    if record["privacy"] != PRIVACY_CONTRACT:
        raise EvidenceCommonsError("reproduction must remain aggregate-only")
    if record["boundary"] != REPRODUCTION_BOUNDARY:
        raise EvidenceCommonsError("reproduction boundary is invalid")
    return record


def derive_status(capsule: dict[str, Any]) -> str:
    artifacts = capsule["artifacts"]
    baseline = artifacts["human_baseline"]
    observed = baseline is not None and baseline["observed_human_sessions"] > 0
    if (
        artifacts["reproduction"] is not None
        and artifacts["public_value_observation"] is not None
        and artifacts["human_study"] is not None
        and observed
    ):
        return "independently_reproduced"
    if observed:
        return "aggregate_published"
    if artifacts["human_study"] is not None:
        return "study_reviewed"
    if capsule["partner_call"]["open"]:
        return "partner_sought"
    return "synthetic_reference"


def validate_capsule(
    capsule: dict[str, Any],
    root: Path,
    *,
    verify_artifacts: bool = True,
) -> dict[str, Any]:
    _require_fields(
        capsule,
        {
            "capsule_version",
            "capsule_id",
            "title",
            "mission",
            "service_area",
            "status",
            "origin",
            "beneficiaries",
            "artifacts",
            "measurement_plan",
            "partner_call",
            "human_authority",
            "evidence_quality",
            "privacy",
            "transfer",
            "sources",
            "limitations",
            "boundary",
        },
        "impact capsule",
    )
    if capsule["capsule_version"] != CAPSULE_VERSION:
        raise EvidenceCommonsError(f"capsule_version must be {CAPSULE_VERSION}")
    if not SLUG_PATTERN.fullmatch(str(capsule["capsule_id"])):
        raise EvidenceCommonsError("capsule_id is invalid")
    if not all(
        _nonempty(capsule[field], maximum)
        for field, maximum in (
            ("title", 140),
            ("mission", 700),
            ("service_area", 120),
            ("origin", 80),
        )
    ):
        raise EvidenceCommonsError("capsule title, mission, service_area, or origin is invalid")
    if capsule["status"] not in STATUS_ORDER:
        raise EvidenceCommonsError("capsule status is invalid")
    beneficiaries = capsule["beneficiaries"]
    if not isinstance(beneficiaries, list) or not 1 <= len(beneficiaries) <= 8 or not all(
        _nonempty(item, 160) for item in beneficiaries
    ):
        raise EvidenceCommonsError("beneficiaries must be one to eight bounded descriptions")

    artifacts = capsule["artifacts"]
    _require_fields(
        artifacts,
        {
            "suite",
            "agent_receipt",
            "human_study",
            "human_baseline",
            "public_value_observation",
            "reproduction",
        },
        "artifacts",
    )
    suite = _validate_suite(artifacts["suite"], root, verify_artifacts)
    _validate_agent_receipt(artifacts["agent_receipt"], suite, root, verify_artifacts)
    _validate_human_evidence(artifacts, suite, root, verify_artifacts)
    _validate_public_value_observation(
        artifacts["public_value_observation"],
        capsule["capsule_id"],
        root,
        verify_artifacts,
    )
    _validate_reproduction(
        artifacts["reproduction"],
        capsule["capsule_id"],
        artifacts,
        root,
        verify_artifacts,
    )
    plan = _validate_measurement_plan(capsule["measurement_plan"])
    observation = artifacts["public_value_observation"]
    if observation is not None:
        known_ids = {row["metric_id"] for row in plan}
        if not set(observation["metric_ids"]) <= known_ids:
            raise EvidenceCommonsError("public value observation cites an undeclared metric")

    partner = capsule["partner_call"]
    _require_fields(
        partner,
        {"open", "role", "contribution", "contact_url", "prohibited_data"},
        "partner_call",
    )
    if type(partner["open"]) is not bool:
        raise EvidenceCommonsError("partner_call.open must be boolean")
    if not _nonempty(partner["role"], 200) or not _nonempty(partner["contribution"], 500):
        raise EvidenceCommonsError("partner role or contribution is invalid")
    if not URL_PATTERN.fullmatch(str(partner["contact_url"])):
        raise EvidenceCommonsError("partner contact must be an HTTPS URL")
    if not isinstance(partner["prohibited_data"], list) or not all(
        _nonempty(item, 120) for item in partner["prohibited_data"]
    ):
        raise EvidenceCommonsError("partner prohibited_data is invalid")

    authority = capsule["human_authority"]
    _require_fields(
        authority,
        {"accountable_role", "protected_decisions", "agent_may", "agent_must_not"},
        "human_authority",
    )
    if not _nonempty(authority["accountable_role"], 200):
        raise EvidenceCommonsError("human authority role is invalid")
    if not all(
        isinstance(authority[field], list)
        and authority[field]
        and all(_nonempty(item, 240) for item in authority[field])
        for field in ("protected_decisions", "agent_may", "agent_must_not")
    ):
        raise EvidenceCommonsError("human authority lists are invalid")

    quality = capsule["evidence_quality"]
    _require_fields(
        quality,
        {"relevance_and_utility", "rigor", "independence", "transparency", "ethics"},
        "evidence_quality",
    )
    allowed_quality = {
        "relevance_and_utility": {"declared", "domain_reviewed"},
        "rigor": {"synthetic_scenarios", "reviewed_protocol", "observed_aggregate"},
        "independence": {
            "maintainer_reference",
            "organization_review",
            "independent_reproduction_attested",
        },
        "transparency": {"artifact_bound"},
        "ethics": {
            "institutional_determination_required_before_human_observation",
            "institutional_basis_attested_not_verified",
        },
    }
    if any(quality[field] not in allowed_quality[field] for field in allowed_quality):
        raise EvidenceCommonsError("evidence_quality contains an unsupported claim")

    if capsule["privacy"] != PRIVACY_CONTRACT:
        raise EvidenceCommonsError("capsule privacy contract must remain aggregate-only")
    transfer = capsule["transfer"]
    _require_fields(transfer, {"holds_when", "fails_when", "revalidate_on"}, "transfer")
    if not all(
        isinstance(transfer[field], list)
        and transfer[field]
        and all(_nonempty(item, 300) for item in transfer[field])
        for field in transfer
    ):
        raise EvidenceCommonsError("transfer conditions are invalid")

    sources = capsule["sources"]
    if not isinstance(sources, list) or not 2 <= len(sources) <= 12:
        raise EvidenceCommonsError("capsule needs two to twelve source records")
    source_fields = {"title", "publisher", "url", "reviewed_at", "supports"}
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise EvidenceCommonsError(f"sources[{index}] must be an object")
        _require_fields(source, source_fields, f"sources[{index}]")
        if (
            not _nonempty(source["title"], 240)
            or not _nonempty(source["publisher"], 120)
            or not URL_PATTERN.fullmatch(str(source["url"]))
            or not DATE_PATTERN.fullmatch(str(source["reviewed_at"]))
            or not _nonempty(source["supports"], 500)
        ):
            raise EvidenceCommonsError(f"sources[{index}] is invalid")
    if len({source["url"] for source in sources}) != len(sources):
        raise EvidenceCommonsError("source URLs must be unique")

    limitations = capsule["limitations"]
    if not isinstance(limitations, list) or not 2 <= len(limitations) <= 12 or not all(
        _nonempty(item, 500) for item in limitations
    ):
        raise EvidenceCommonsError("capsule needs two to twelve explicit limitations")
    if capsule["boundary"] != BOUNDARY:
        raise EvidenceCommonsError("capsule evidence boundary is missing or changed")
    if any(pattern.search(render_json(capsule)) for pattern in SENSITIVE_PATTERNS):
        raise EvidenceCommonsError("capsule contains a prohibited sensitive-data pattern")

    baseline = artifacts["human_baseline"]
    observed = baseline is not None and baseline["observed_human_sessions"] > 0
    if artifacts["public_value_observation"] is not None and not observed:
        raise EvidenceCommonsError(
            "a public value observation requires an observed aggregate human baseline"
        )
    if artifacts["reproduction"] is not None and not (
        artifacts["human_study"] is not None
        and observed
        and artifacts["public_value_observation"] is not None
    ):
        raise EvidenceCommonsError(
            "an independent reproduction requires the complete preceding evidence chain"
        )

    derived = derive_status(capsule)
    if capsule["status"] != derived:
        raise EvidenceCommonsError(
            f"capsule status is inflated or stale; declared={capsule['status']}, derived={derived}"
        )
    if derived in {"aggregate_published", "independently_reproduced"}:
        baseline = artifacts["human_baseline"]
        if not baseline["institutional_basis_attested"]:
            raise EvidenceCommonsError("observed human evidence requires an institutional basis attestation")
        if (
            quality["rigor"] != "observed_aggregate"
            or quality["ethics"] != "institutional_basis_attested_not_verified"
        ):
            raise EvidenceCommonsError(
                "observed human evidence requires aggregate rigor and an unverified attestation label"
            )
    if derived == "study_reviewed" and (
        quality["rigor"] != "reviewed_protocol"
        or quality["ethics"]
        != "institutional_determination_required_before_human_observation"
    ):
        raise EvidenceCommonsError(
            "study_reviewed status requires a reviewed protocol with determination still required"
        )
    if derived == "independently_reproduced" and quality["independence"] != "independent_reproduction_attested":
        raise EvidenceCommonsError("reproduction status requires an independence attestation label")
    return capsule


def comparison(capsule: dict[str, Any]) -> dict[str, Any]:
    artifacts = capsule["artifacts"]
    agent = artifacts["agent_receipt"]["primary_metric"]
    human = artifacts["human_baseline"]
    observation = artifacts["public_value_observation"]
    reproduction = artifacts["reproduction"]
    missing = []
    if artifacts["agent_receipt"]["suite_binding"] != "hash_bound":
        missing.append("fresh hash-bound agent rerun on the reviewed suite")
    if artifacts["human_study"] is None:
        missing.append("reviewed blinded human study protocol")
    if human is None or human["observed_human_sessions"] == 0:
        missing.append("aggregate observed human comparator")
    if observation is None:
        missing.append("bounded public-value observation")
    if reproduction is None:
        missing.append("independent reproduction")
    if human is None:
        human_summary = None
        delta = None
    else:
        human_summary = {
            "exact_rate": human["exact_rate"],
            "abstain_rate": human["abstain_rate"],
            "session_count": human["session_count"],
            "observed_human_sessions": human["observed_human_sessions"],
        }
        delta = round(human["exact_rate"] - agent["value"], 4)
    return {
        "comparison_version": COMPARISON_VERSION,
        "capsule_id": capsule["capsule_id"],
        "derived_status": derive_status(capsule),
        "agent_measurement": {
            "name": agent["name"],
            "value": agent["value"],
            "interval_95": agent["interval_95"],
            "observation_count": agent["observation_count"],
        },
        "human_comparator": human_summary,
        "human_minus_agent_exact_rate": delta,
        "public_value_observed": observation is not None,
        "reproduction": None
        if reproduction is None
        else {
            "outcome": reproduction["outcome"],
            "independence_attested": reproduction["independence_attested"],
            "independence_verified_by_aau": False,
        },
        "missing_evidence": missing,
        "next_evidence": missing[0] if missing else "periodic reassessment and transfer testing",
        "claims": {
            "causal_impact_proved": bool(
                observation is not None
                and observation["observation_kind"] == "causal_evaluation"
                and observation["causal_claim"]
            ),
            "institutional_review_verified_by_aau": False,
            "identity_verified_by_aau": False,
            "certification_proved": False,
            "government_endorsement_proved": False,
            "deployment_authorized": False,
        },
        "boundary": BOUNDARY,
    }


def _artifact_entries(capsule: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        artifact
        for artifact in capsule["artifacts"].values()
        if isinstance(artifact, dict) and "artifact_id" in artifact
    ]


def _pack_readme(capsule: dict[str, Any], result: dict[str, Any]) -> str:
    gaps = "\n".join(f"- {item}" for item in result["missing_evidence"]) or "- None declared"
    return f'''# {capsule["title"]}

> AAU Impact Capsule · derived status: **{result["derived_status"]}**

{capsule["mission"]}

## What is bound

- Reviewed scenario artifact and aggregate agent evaluation
- Human comparator when present; participant sessions are never included
- Predeclared public-value measures and any bounded observation
- Transfer conditions, protected human authority, sources, and limitations
- Independent reproduction when present

## Visible evidence gaps

{gaps}

Verify byte integrity with `aau evidence verify .` and inspect `comparison.json`. The
manifest proves byte integrity only. Status is derived from artifact presence; it is not
a score, certification, endorsement, causal conclusion, or permission to deploy.

**Boundary:** {BOUNDARY}
'''


def build_pack(capsule_path: Path, root: Path, output: Path) -> dict[str, Any]:
    capsule = validate_capsule(_read_json(capsule_path, "impact capsule"), root)
    if output.exists():
        raise EvidenceCommonsError(f"refusing to overwrite existing path: {output.resolve()}")
    result = comparison(capsule)
    files: dict[str, bytes] = {
        "capsule.json": render_json(capsule).encode(),
        "comparison.json": render_json(result).encode(),
        "README.md": _pack_readme(capsule, result).encode(),
    }
    source_paths: dict[str, str | None] = {
        "capsule.json": None,
        "comparison.json": None,
        "README.md": None,
    }
    used_names = set(files)
    for artifact in _artifact_entries(capsule):
        source = _resolve_artifact(root, artifact["path"], artifact["artifact_id"])
        suffix = "".join(source.suffixes[-2:]) or ".bin"
        name = f"artifacts/{artifact['artifact_id']}{suffix}"
        if name in used_names:
            raise EvidenceCommonsError("artifact ids and file suffixes must produce unique pack paths")
        data = _read_bytes(source, artifact["artifact_id"])
        files[name] = data
        source_paths[name] = artifact["path"]
        used_names.add(name)
    rows = [
        {
            "path": name,
            "source_path": source_paths[name],
            "bytes": len(data),
            "sha256": sha256_bytes(data),
        }
        for name, data in sorted(files.items())
    ]
    manifest = {
        "pack_version": PACK_VERSION,
        "capsule_id": capsule["capsule_id"],
        "hash_algorithm": "sha256",
        "files": rows,
        "claims": {
            "byte_integrity_only": True,
            "identity_verified": False,
            "institutional_review_verified": False,
            "causal_impact_proved": False,
            "certification_proved": False,
            "government_endorsement_proved": False,
            "deployment_authorized": False,
        },
    }
    files["manifest.json"] = render_json(manifest).encode()
    destination = output.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-", dir=destination.parent
    ) as temporary:
        stage = Path(temporary) / destination.name
        stage.mkdir()
        for name, data in files.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        verify_pack(stage)
        stage.replace(destination)
    return {
        "ready": True,
        "capsule_id": capsule["capsule_id"],
        "derived_status": result["derived_status"],
        "file_count": len(files),
        "path": str(destination),
    }


def verify_pack(path: Path) -> dict[str, Any]:
    root = path.resolve()
    if not root.is_dir() or any(item.is_symlink() for item in root.rglob("*")):
        raise EvidenceCommonsError("impact pack must be a directory without symlinks")
    manifest = _read_json(root / "manifest.json", "manifest.json")
    _require_fields(
        manifest,
        {"pack_version", "capsule_id", "hash_algorithm", "files", "claims"},
        "manifest.json",
    )
    if manifest["pack_version"] != PACK_VERSION or manifest["hash_algorithm"] != "sha256":
        raise EvidenceCommonsError("impact pack version or hash algorithm is invalid")
    if not SLUG_PATTERN.fullmatch(str(manifest["capsule_id"])):
        raise EvidenceCommonsError("impact pack capsule_id is invalid")
    if manifest["claims"] != {
        "byte_integrity_only": True,
        "identity_verified": False,
        "institutional_review_verified": False,
        "causal_impact_proved": False,
        "certification_proved": False,
        "government_endorsement_proved": False,
        "deployment_authorized": False,
    }:
        raise EvidenceCommonsError("impact pack claims exceed the evidence boundary")
    rows = manifest["files"]
    if not isinstance(rows, list) or not 3 <= len(rows) <= MAX_ARTIFACTS + 3:
        raise EvidenceCommonsError("impact pack manifest file count is invalid")
    declared = set()
    source_map: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "source_path", "bytes", "sha256"}:
            raise EvidenceCommonsError("impact pack manifest row is invalid")
        name = _safe_relative(row["path"], "manifest file path")
        if name in declared or name == "manifest.json":
            raise EvidenceCommonsError("impact pack path is duplicate or unsupported")
        data = _read_bytes(root / name, name)
        if row["bytes"] != len(data) or row["sha256"] != sha256_bytes(data):
            raise EvidenceCommonsError(f"impact pack manifest mismatch: {name}")
        if row["source_path"] is not None:
            source_map[_safe_relative(row["source_path"], "source_path")] = name
        declared.add(name)
    actual = {str(item.relative_to(root)) for item in root.rglob("*") if item.is_file()}
    if actual != declared | {"manifest.json"}:
        raise EvidenceCommonsError("impact pack contains missing or unsupported files")
    capsule = validate_capsule(
        _read_json(root / "capsule.json", "capsule.json"), root, verify_artifacts=False
    )
    if capsule["capsule_id"] != manifest["capsule_id"]:
        raise EvidenceCommonsError("impact pack capsule id is inconsistent")
    for artifact in _artifact_entries(capsule):
        packed_name = source_map.get(artifact["path"])
        if packed_name is None:
            raise EvidenceCommonsError(f"impact pack is missing artifact {artifact['artifact_id']}")
        if sha256_bytes((root / packed_name).read_bytes()) != artifact["sha256"]:
            raise EvidenceCommonsError(f"packed artifact hash mismatch: {artifact['artifact_id']}")
    expected_comparison = comparison(capsule)
    if _read_json(root / "comparison.json", "comparison.json") != expected_comparison:
        raise EvidenceCommonsError("impact pack comparison.json is stale or hand-edited")
    return {
        "ready": True,
        "capsule_id": capsule["capsule_id"],
        "derived_status": derive_status(capsule),
        "file_count": len(actual),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aau evidence",
        description="Bind agent, human, public-value, and reproduction evidence without a trust score.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("validate", "validate one Impact Capsule and its referenced artifacts"),
        ("compare", "show the evidence present, the visible gaps, and the next required artifact"),
    ):
        child = sub.add_parser(command, help=help_text)
        child.add_argument("capsule", type=Path)
        child.add_argument("--root", type=Path)
        child.add_argument("--json", action="store_true")
    pack = sub.add_parser("pack", help="create a portable hash-bound Impact Capsule directory")
    pack.add_argument("capsule", type=Path)
    pack.add_argument("--root", type=Path)
    pack.add_argument("--out", required=True, type=Path)
    pack.add_argument("--json", action="store_true")
    verify = sub.add_parser("verify", help="verify a portable Impact Capsule pack")
    verify.add_argument("pack", type=Path)
    verify.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "verify":
            result = verify_pack(args.pack)
        else:
            capsule_path = args.capsule.resolve()
            root = args.root.resolve() if args.root else find_repository_root(capsule_path)
            capsule = validate_capsule(_read_json(capsule_path, "impact capsule"), root)
            if args.command == "validate":
                result = {
                    "ready": True,
                    "capsule_id": capsule["capsule_id"],
                    "derived_status": derive_status(capsule),
                    "artifact_count": len(_artifact_entries(capsule)),
                }
            elif args.command == "compare":
                result = comparison(capsule)
            else:
                result = build_pack(capsule_path, root, args.out)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        elif args.command == "compare":
            print(
                f"Impact Capsule {result['capsule_id']}: {result['derived_status']}\n"
                f"Next evidence: {result['next_evidence']}"
            )
        else:
            print(
                f"Impact Capsule ready: {result['capsule_id']} "
                f"({result['derived_status']}, {result.get('file_count', result.get('artifact_count'))} files)"
            )
        return 0
    except (EvidenceCommonsError, OSError, ValueError) as exc:
        print(f"aau evidence: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
