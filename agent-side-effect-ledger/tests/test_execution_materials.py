import base64
import json

import pytest

from aau_execution_materials import (
    MaterialError,
    capture_materials,
    validate_materials,
)


def test_static_capture_binds_transitive_local_imports_and_exposes_unresolved(tmp_path):
    workspace = tmp_path / "workspace"
    source = workspace / "app" / "entry.py"
    source.parent.mkdir(parents=True)
    source.write_text("import helper\nprint(helper.VALUE)\n")
    (source.parent / "helper.py").write_text("import json\nfrom nested import VALUE\n")
    (source.parent / "nested.py").write_text("VALUE = 7\n")

    first = capture_materials(workspace, source, "static_local_python_imports")
    second = capture_materials(workspace, source, "static_local_python_imports")

    assert first == second
    assert set(validate_materials(first)) == {
        "app/entry.py",
        "app/helper.py",
        "app/nested.py",
    }
    assert first["unresolved_imports"] == ["json"]
    assert first["material_set_sha256"] == second["material_set_sha256"]


def test_conservative_search_captures_same_named_ancestor_candidates(tmp_path):
    workspace = tmp_path / "workspace"
    source = workspace / "app" / "examples" / "entry.py"
    source.parent.mkdir(parents=True)
    source.write_text("import helper\n")
    (source.parent / "helper.py").write_text("VALUE = 'nearest'\n")
    (workspace / "helper.py").write_text("VALUE = 'workspace'\n")

    value = capture_materials(workspace, source, "static_local_python_imports")

    assert set(validate_materials(value)) == {
        "app/examples/entry.py",
        "app/examples/helper.py",
        "helper.py",
    }


def test_relative_package_import_captures_initializers(tmp_path):
    workspace = tmp_path / "workspace"
    package = workspace / "pkg"
    package.mkdir(parents=True)
    source = package / "entry.py"
    source.write_text("from . import helper\n")
    (package / "helper.py").write_text("VALUE = 1\n")
    (package / "__init__.py").write_text("PACKAGE = True\n")

    value = capture_materials(workspace, source, "static_local_python_imports")

    assert set(validate_materials(value)) == {
        "pkg/__init__.py",
        "pkg/entry.py",
        "pkg/helper.py",
    }


@pytest.mark.parametrize(
    "source",
    [
        "__import__('helper')\n",
        "import importlib\nimportlib.import_module('helper')\n",
        "import runpy\nrunpy.run_path('helper.py')\n",
        "exec(\"import helper\")\n",
    ],
)
def test_obvious_dynamic_loading_fails_closed(tmp_path, source):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    entrypoint = workspace / "entry.py"
    entrypoint.write_text(source)

    with pytest.raises(MaterialError, match="dynamic code loading"):
        capture_materials(workspace, entrypoint, "static_local_python_imports")


def test_entrypoint_only_mode_is_explicit_and_bounded(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    entrypoint = workspace / "adapter.js"
    entrypoint.write_text("console.log('ok');\n")

    value = capture_materials(workspace, entrypoint, "entrypoint_only_non_python")

    assert list(validate_materials(value)) == ["adapter.js"]
    assert value["unresolved_imports"] == []
    assert value["materials"][0]["role"] == "entrypoint"


def test_material_tampering_and_noncanonical_base64_are_rejected(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    entrypoint = workspace / "entry.py"
    entrypoint.write_text("VALUE = 1\n")
    value = capture_materials(workspace, entrypoint, "static_local_python_imports")

    tampered = json.loads(json.dumps(value))
    tampered["materials"][0]["content_base64"] = base64.b64encode(b"changed").decode()
    with pytest.raises(MaterialError, match="size or digest"):
        validate_materials(tampered)

    malformed = json.loads(json.dumps(value))
    malformed["materials"][0]["content_base64"] += "="
    with pytest.raises(MaterialError, match="canonical base64"):
        validate_materials(malformed)


def test_material_source_symlink_is_rejected(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "target.py"
    target.write_text("VALUE = 1\n")
    link = workspace / "entry.py"
    link.symlink_to(target)

    with pytest.raises(MaterialError, match="non-symbolic-link"):
        capture_materials(workspace, link, "static_local_python_imports")
