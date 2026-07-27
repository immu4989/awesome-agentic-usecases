"""The quickstart in harness/README.md must actually run.

Documentation that no longer executes is worse than none: a new user's first command
fails and they conclude the project is broken. This extracts the quickstart verbatim
and runs it, so the README cannot drift away from the API it documents.
"""

import os
import re
import subprocess
import sys

README = os.path.join(os.path.dirname(__file__), "..", "README.md")


def test_readme_quickstart_executes():
    md = open(README).read()
    block = re.search(r"## Quickstart.*?```python\n(.*?)```", md, re.S)
    assert block, "the README no longer has a python quickstart block"
    code = block.group(1)

    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, f"quickstart failed:\n{proc.stdout}\n{proc.stderr}"
    # it should render a results table, not merely avoid crashing
    assert "## Results" in proc.stdout and "95% CI" in proc.stdout


def test_readme_documents_the_public_api():
    """Every exported name should be findable in the README, so nothing ships undocumented."""
    import aau_harness

    md = open(README).read()
    undocumented = [n for n in aau_harness.__all__ if n not in md]
    assert not undocumented, f"exported but undocumented: {undocumented}"
