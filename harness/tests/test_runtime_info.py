import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError
from aau_harness.catalog_cli import main
from aau_harness.runtime_info import runtime_info
import aau_harness.runtime_info as runtime_module


def package(root):
    root.mkdir()
    (root / "__init__.py").write_bytes(b"# synthetic package\n")
    (root / "score.py").write_bytes(b"value = 1\n")
    return root


def test_inventory_is_location_independent_and_detects_same_version_source_change(tmp_path):
    first, second = package(tmp_path / "first"), package(tmp_path / "second")
    initial = runtime_info(first)
    assert initial == runtime_info(second)
    assert str(tmp_path) not in json.dumps(initial)
    (second / "score.py").write_bytes(b"value = 2\n")
    changed = runtime_info(second)
    assert changed["distribution_version"] == initial["distribution_version"]
    assert changed["source_tree_sha256"] != initial["source_tree_sha256"]
    (first / "new.py").write_bytes(b"# added module\n")
    assert runtime_info(first)["source_tree_sha256"] != initial["source_tree_sha256"]


def test_cache_and_non_python_resources_are_explicitly_outside_scope(tmp_path):
    root = package(tmp_path / "pkg")
    initial = runtime_info(root)
    (root / "__pycache__").mkdir()
    (root / "__pycache__/ignored.py").write_text("not inventoried")
    (root / "config.json").write_text("private config is not collected")
    assert runtime_info(root) == initial
    assert "resources" in initial["boundary"]


@pytest.mark.parametrize("defect", ["empty", "file-link", "dir-link", "root-link", "oversized"])
def test_unavailable_or_ambiguous_source_trees_are_rejected(tmp_path, defect):
    root = package(tmp_path / "pkg")
    if defect == "empty":
        (root / "__init__.py").unlink()
    elif defect == "file-link":
        (root / "alias.py").symlink_to(root / "score.py")
    elif defect == "dir-link":
        (root / "alias").symlink_to(root, target_is_directory=True)
    elif defect == "root-link":
        (tmp_path / "alias").symlink_to(root, target_is_directory=True)
        root = tmp_path / "alias"
    else:
        (root / "score.py").write_bytes(b"x" * 2_000_001)
    with pytest.raises(AgentBomError):
        runtime_info(root)


def test_cli_outside_checkout_emits_no_paths_or_environment_and_refuses_tampering(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PRIVATE_EXAMPLE", "MUST_NOT_BE_COLLECTED")
    assert main(["runtime-info"]) == 0
    text = capsys.readouterr().out
    report = json.loads(text)
    assert "runtime_info.py" in report["source_files"]
    assert "MUST_NOT_BE_COLLECTED" not in text
    assert str(Path(__file__).parent) not in text
    assert main(["runtime-info", "--out", "runtime.json"]) == 0
    assert main(["runtime-info", "--verify", "runtime.json"]) == 0
    assert main(["runtime-info", "--out", "runtime.json"]) == 2
    report["source_tree_sha256"] = "0" * 64
    (tmp_path / "runtime.json").write_text(json.dumps(report))
    assert main(["runtime-info", "--verify", "runtime.json"]) == 2


def test_metadata_is_not_used_as_a_substitute_for_source_identity(tmp_path, monkeypatch):
    root = package(tmp_path / "pkg")
    initial = runtime_info(root)
    monkeypatch.setattr(runtime_module, "version", lambda name: "0.0.0+different.metadata")
    changed = runtime_info(root)
    assert changed["source_tree_sha256"] == initial["source_tree_sha256"]
    assert changed["distribution_version"] != initial["distribution_version"]
    def missing(name):
        raise runtime_module.PackageNotFoundError(name)
    monkeypatch.setattr(runtime_module, "version", missing)
    assert runtime_info(root)["distribution_version"] is None


def test_unreadable_walk_does_not_silently_emit_partial_inventory(tmp_path, monkeypatch):
    root = package(tmp_path / "pkg")
    def failed_walk(*args, **kwargs):
        kwargs["onerror"](PermissionError("private local path"))
    monkeypatch.setattr(runtime_module.os, "walk", failed_walk)
    with pytest.raises(AgentBomError, match="fully inspected"):
        runtime_info(root)


@pytest.mark.parametrize("limit", ["count", "total"])
def test_inventory_limits_reject_instead_of_truncating(tmp_path, limit):
    root = package(tmp_path / "pkg")
    count, content = (500, b"# small\n") if limit == "count" else (11, b"x" * 1_900_000)
    for index in range(count):
        (root / f"module_{index}.py").write_bytes(content)
    with pytest.raises(AgentBomError, match="limits"):
        runtime_info(root)
