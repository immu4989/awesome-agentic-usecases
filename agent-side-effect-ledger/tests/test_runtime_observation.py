import hashlib
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from aau_runtime_observation import (
    ObservationError,
    capture_observation,
    capture_release_snapshot,
    instrumentation_environment,
    prepare_observer,
    unobserved_non_python,
    validate_observation,
    validate_release_snapshot,
)


def _run(
    workspace: Path, observer: Path, trace: Path, adapter: Path
) -> tuple[dict, bytes]:
    _sitecustomize, observer_payload = prepare_observer(observer)
    environment = instrumentation_environment(workspace, trace, observer)
    completed = subprocess.run(
        [sys.executable, str(adapter)],
        cwd=workspace,
        env=environment,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert completed.returncode == 0, completed.stderr.decode()
    static = {adapter.relative_to(workspace).as_posix(): adapter.read_bytes()}
    return (
        capture_observation(workspace, trace, 1, static, observer_payload),
        observer_payload,
    )


def test_observer_captures_runtime_only_read_without_embedding_content(tmp_path):
    workspace = tmp_path / "workspace"
    observer = tmp_path / "observer"
    trace = tmp_path / "trace"
    workspace.mkdir()
    trace.mkdir()
    config = workspace / "service-policy.json"
    config.write_text('{"route":"synthetic"}\n')
    adapter = workspace / "adapter.py"
    adapter.write_text(
        "from pathlib import Path\n"
        "Path('service-policy.json').read_text()\n"
        "print('ok')\n"
    )

    observation, _observer_payload = _run(workspace, observer, trace, adapter)

    assert observation["expected_session_count"] == 1
    assert observation["observed_session_count"] == 1
    assert observation["runtime_only_paths"] == ["service-policy.json"]
    assert observation["unobserved_static_paths"] == []
    assert [row["path"] for row in observation["materials"]] == [
        "adapter.py",
        "service-policy.json",
    ]
    assert all("content" not in row and "base64" not in row for row in observation["materials"])
    assert validate_observation(observation, {"adapter.py"})

    snapshot = capture_release_snapshot(workspace, observation)
    assert snapshot["all_materials_match"] is True
    validate_release_snapshot(snapshot, observation)

    config.write_text('{"route":"changed"}\n')
    changed = capture_release_snapshot(workspace, observation)
    assert changed["all_materials_match"] is False
    assert [row["path"] for row in changed["materials"] if not row["matches_tested"]] == [
        "service-policy.json"
    ]
    validate_release_snapshot(changed, observation)


def test_observer_rejects_workspace_write(tmp_path):
    workspace = tmp_path / "workspace"
    observer = tmp_path / "observer"
    trace = tmp_path / "trace"
    workspace.mkdir()
    trace.mkdir()
    adapter = workspace / "adapter.py"
    adapter.write_text("from pathlib import Path\nPath('created.txt').write_text('unsafe')\n")

    _sitecustomize, observer_payload = prepare_observer(observer)
    environment = instrumentation_environment(workspace, trace, observer)
    subprocess.run(
        shlex.split(shlex.join([sys.executable, str(adapter)])),
        cwd=workspace,
        env=environment,
        check=True,
    )

    with pytest.raises(ObservationError, match="workspace_write_attempt"):
        capture_observation(
            workspace,
            trace,
            1,
            {"adapter.py": adapter.read_bytes()},
            observer_payload,
        )


def test_observation_detects_tampered_digest(tmp_path):
    workspace = tmp_path / "workspace"
    observer = tmp_path / "observer"
    trace = tmp_path / "trace"
    workspace.mkdir()
    trace.mkdir()
    adapter = workspace / "adapter.py"
    adapter.write_text("print('ok')\n")
    observation, _observer_payload = _run(workspace, observer, trace, adapter)
    observation["materials"][0]["sha256"] = "0" * 64
    with pytest.raises(ObservationError, match="digest mismatch"):
        validate_observation(observation)


def test_observation_requires_every_expected_process(tmp_path):
    workspace = tmp_path / "workspace"
    observer = tmp_path / "observer"
    trace = tmp_path / "trace"
    workspace.mkdir()
    trace.mkdir()
    adapter = workspace / "adapter.py"
    adapter.write_text("print('ok')\n")
    _sitecustomize, observer_payload = prepare_observer(observer)
    environment = instrumentation_environment(workspace, trace, observer)
    subprocess.run([sys.executable, str(adapter)], env=environment, check=True)
    with pytest.raises(ObservationError, match="expected 2"):
        capture_observation(
            workspace,
            trace,
            2,
            {"adapter.py": adapter.read_bytes()},
            observer_payload,
        )


def test_snapshot_rejects_false_match_claim(tmp_path):
    workspace = tmp_path / "workspace"
    observer = tmp_path / "observer"
    trace = tmp_path / "trace"
    workspace.mkdir()
    trace.mkdir()
    adapter = workspace / "adapter.py"
    adapter.write_text("print('ok')\n")
    observation, _observer_payload = _run(workspace, observer, trace, adapter)
    snapshot = capture_release_snapshot(workspace, observation)
    snapshot["materials"][0]["matches_tested"] = False
    snapshot_without_digest = dict(snapshot)
    snapshot_without_digest.pop("snapshot_sha256")
    snapshot["snapshot_sha256"] = hashlib.sha256(
        json.dumps(
            snapshot_without_digest, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    with pytest.raises(ObservationError, match="material match is invalid"):
        validate_release_snapshot(snapshot, observation)


def test_non_python_observation_is_explicit(tmp_path):
    observer = tmp_path / "observer"
    _sitecustomize, observer_payload = prepare_observer(observer)
    value = unobserved_non_python({"adapter.sh": b"#!/bin/sh\n"}, observer_payload)
    assert value["capture_mode"] == "not_observed_non_python"
    assert value["expected_session_count"] == 0
    assert value["observed_session_count"] == 0
    assert value["materials"] == []
    assert value["unobserved_static_paths"] == ["adapter.sh"]
    assert validate_observation(value, {"adapter.sh"}) == {}


def test_observer_rejects_workspace_symlink_read(tmp_path):
    workspace = tmp_path / "workspace"
    observer = tmp_path / "observer"
    trace = tmp_path / "trace"
    workspace.mkdir()
    trace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    (workspace / "linked.txt").symlink_to(outside)
    adapter = workspace / "adapter.py"
    adapter.write_text("from pathlib import Path\nPath('linked.txt').read_text()\n")
    _sitecustomize, observer_payload = prepare_observer(observer)
    environment = instrumentation_environment(workspace, trace, observer)
    subprocess.run(
        [sys.executable, str(adapter)],
        cwd=workspace,
        env=environment,
        check=True,
    )
    with pytest.raises(ObservationError, match="symbolic_link_path"):
        capture_observation(
            workspace,
            trace,
            1,
            {"adapter.py": adapter.read_bytes()},
            observer_payload,
        )
