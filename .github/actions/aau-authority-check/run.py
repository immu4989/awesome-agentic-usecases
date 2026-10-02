"""Repository-pinned Action entrypoint; no harness download or report upload."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "harness" / "src"))

from aau_harness.agent_bom import AgentBomError, load_json  # noqa: E402
from aau_harness.authority_check import check_authority, verify_check  # noqa: E402


def workspace_path(workspace: Path, raw: str) -> Path:
    path = Path(raw)
    if not raw.strip() or path.is_absolute() or ".." in path.parts:
        raise AgentBomError("Action paths must be nonempty workspace-relative paths without '..'")
    resolved = (workspace / path).resolve()
    if resolved == workspace or not resolved.is_relative_to(workspace):
        raise AgentBomError("Action path must remain inside the workspace")
    return workspace / path


def main() -> int:
    try:
        workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve(strict=True)
        inventory = workspace_path(workspace, os.environ["AAU_AUTHORITY_INVENTORY"])
        adapter = workspace_path(workspace, os.environ["AAU_AUTHORITY_ARTIFACT"])
        output = workspace_path(workspace, os.environ["AAU_AUTHORITY_OUTPUT"])
        timeout = float(os.environ.get("AAU_AUTHORITY_TIMEOUT", "10"))
        # Give relative adapter arguments the same interpretation as local CLI runs.
        os.chdir(workspace)
        report = check_authority(load_json(inventory), os.environ["AAU_AUTHORITY_COMMAND"],
                                 adapter, workspace, output, timeout)
        verified = verify_check(output, adapter, workspace)
        if report != verified:
            raise AgentBomError("saved reports differ from the evaluated evidence")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write("## AAU staging authority check\n\n"
                             f"Verified synthetic cases: {report['exact_count']}/{report['case_count']} exact.\n\n"
                             "Reports preserved as JSON, offline HTML, and JUnit XML. "
                             "This is not production authorization or certification.\n")
        return 0 if report["status"] == "evidence_passed" else 1
    except (AgentBomError, OSError, ValueError, KeyError) as exc:
        print(f"AAU authority Action: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
