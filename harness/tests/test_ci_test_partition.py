"""Guard the repository's explicit shared-unit / per-lab CI partition."""

from pathlib import Path


def test_shared_suite_is_not_multiplied_by_the_lab_matrix():
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml").read_text()
    catalog, matrix = workflow.split("\n  use-case:\n", 1)
    assert catalog.count("pytest harness/tests -q") == 1
    assert workflow.count("pytest harness/tests") == 1
    assert "harness/tests" not in matrix
    assert "run: pytest ${{ matrix.dir }}/tests -q" in matrix
    assert "pip install -e harness[dev]" in matrix
    assert "pip install -e ${{ matrix.dir }}[dev]" in matrix
    assert 'PYTHONHASHSEED=0 ${{ matrix.cli }} generate' in matrix
    assert 'PYTHONHASHSEED=12345 ${{ matrix.cli }} generate' in matrix
    assert 'diff /tmp/scenarios_a.jsonl "$committed"' in matrix
    assert "${{ matrix.cli }} eval --backend mock --repeats 3" in matrix
