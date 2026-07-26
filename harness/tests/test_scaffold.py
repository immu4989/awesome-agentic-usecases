"""The scaffold must keep emitting a use case that clears the bar.

A generator that silently rots is worse than no generator: a contributor's first command
fails and they leave. These checks are cheap and catch template drift without paying for a
pip install.
"""

import ast
import os
import tempfile

import pytest

from aau_harness.scaffold import build, slugify


@pytest.fixture(scope="module")
def generated():
    with tempfile.TemporaryDirectory() as root:
        yield build("healthcare", "prior-auth-triage-agent", 41, root), root


def test_emits_every_file_the_bar_requires(generated):
    dest, _ = generated
    for rel in ("pyproject.toml", "README.md", "FAILURE_MODES.md",
                "src/prior_auth_triage_agent/world.py",
                "src/prior_auth_triage_agent/tools.py",
                "src/prior_auth_triage_agent/agent.py",
                "src/prior_auth_triage_agent/evaluate.py",
                "src/prior_auth_triage_agent/cli.py",
                "tests/test_prior_auth_triage_agent.py",
                "evals/.gitkeep", "results/.gitkeep"):
        assert os.path.exists(os.path.join(dest, rel)), rel


def test_every_placeholder_was_substituted(generated):
    """An unreplaced __TOKEN__ ships broken code that looks fine until it is imported."""
    dest, _ = generated
    for dirpath, _d, files in os.walk(dest):
        for fn in files:
            body = open(os.path.join(dirpath, fn)).read()
            assert "__PKG__" not in body and "__CLI__" not in body, fn
            assert "__SEED__" not in body and "__TITLE__" not in body, fn


def test_generated_python_parses(generated):
    dest, _ = generated
    for dirpath, _d, files in os.walk(dest):
        for fn in files:
            if fn.endswith(".py"):
                p = os.path.join(dirpath, fn)
                ast.parse(open(p).read(), filename=p)


def test_generated_world_has_a_deception_and_shared_gold(generated):
    """The two properties that separate a measurement from a demo."""
    dest, _ = generated
    src = open(os.path.join(dest, "src/prior_auth_triage_agent/world.py")).read()
    assert "BENIGN_LOOKALIKE" in src
    assert "def gold_decision" in src
    assert "gold_decision(case_type, record, context)" in src   # generator uses it too


def test_scaffold_refuses_to_clobber(generated):
    dest, root = generated
    with pytest.raises(SystemExit):
        build("healthcare", "prior-auth-triage-agent", 41, root)


def test_slugify():
    assert slugify("Prior Auth Triage Agent") == "prior-auth-triage-agent"
    assert slugify("Legal & Compliance") == "legal-compliance"
