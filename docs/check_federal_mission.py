"""Verify the Federal Mission Assurance Profile, local builder, and source bindings."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "federal-mission-assurance"
DOCS = ROOT / "docs"


def fail(message: str) -> None:
    raise SystemExit(f"Federal Mission Assurance check failed: {message}")


def main() -> None:
    spec = importlib.util.spec_from_file_location("aau_federal", PROFILE_DIR / "aau_federal.py")
    if not spec or not spec.loader:
        fail("cannot load aau_federal.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    schema = json.loads((PROFILE_DIR / "federal-profile.schema.json").read_text())
    example = json.loads((PROFILE_DIR / "example-acquisition-profile.json").read_text())
    policy = json.loads((PROFILE_DIR / "policy-sources.json").read_text())
    data = json.loads((DOCS / "federal-mission-data.json").read_text())
    errors = module.validate_profile(example)
    if errors:
        fail("worked profile is invalid: " + "; ".join(errors))
    if schema["properties"]["profile_version"]["const"] != module.VERSION:
        fail("schema and validator profile versions differ")
    if (DOCS / "federal-profile.schema.json").read_text() != (PROFILE_DIR / "federal-profile.schema.json").read_text():
        fail("published profile schema differs from the canonical contract")
    if data["profile_schema"] != "federal-profile.schema.json":
        fail("browser data does not reference the published schema")
    if data["profile_version"] != module.VERSION or data["example"] != example:
        fail("browser data and canonical example differ")
    if data["sources"] != policy["sources"] or data["controls"] != policy["controls"]:
        fail("browser source/control data is not bound to the canonical policy snapshot")
    if data["pack_files"] != list(module.PACK_NAMES):
        fail("browser and CLI pack file contracts differ")
    asset = (DOCS / "assets" / "federal-mission.svg").read_text()
    for token in (f">{len(data['controls'])}</text>", f">{len(data['sources'])}</text>", f">{len(data['pack_files'])}</text>"):
        if token not in asset:
            fail(f"Federal Mission visual proof is stale: missing {token!r}")

    source_ids = {item["source_id"] for item in policy["sources"]}
    if len(source_ids) != len(policy["sources"]):
        fail("policy source IDs must be unique")
    allowed_domains = {"www.whitehouse.gov", "www.nist.gov", "airc.nist.gov", "www.gao.gov"}
    for source in policy["sources"]:
        if urlparse(source["url"]).hostname not in allowed_domains:
            fail(f"source is not on an allowlisted official domain: {source['url']}")
        if source["review_due"] <= source["last_verified"]:
            fail(f"source review date is not later than verification: {source['source_id']}")
    for control in policy["controls"]:
        unknown = set(control["source_ids"]) - source_ids
        if unknown:
            fail(f"{control['control_id']} references unknown source IDs: {sorted(unknown)}")

    html = (DOCS / "index.html").read_text()
    css = (DOCS / "federal-mission.css").read_text()
    js = (DOCS / "federal-mission.js").read_text()
    for token in (
        'id="federal-mission"',
        'id="federal-download-pack"',
        'id="federal-readiness-list"',
        'id="federal-source-list"',
        "Form contents stay in this browser tab",
    ):
        if token not in html and token not in js:
            fail(f"public interface is missing {token!r}")
    for token in ("AAUBoundaryZip.archive", "crypto.subtle.digest", "federal-mission-data.json"):
        if token not in js:
            fail(f"browser pack builder is missing {token!r}")
    if "localStorage" in js or "sessionStorage" in js:
        fail("Federal Mission Studio must not persist profile contents")
    if "http://" in js or "https://" in js:
        fail("Federal Mission Studio JavaScript must not call a remote endpoint")
    if "@media (prefers-reduced-motion: reduce)" not in css:
        fail("Federal Mission Studio needs a reduced-motion mode")

    lab = ROOT / data["featured_lab"]["path"]
    if not lab.is_dir() or not (lab / "README.md").is_file():
        fail("featured acquisition lab is missing")
    print(
        "Federal Mission Assurance verified: "
        f"{len(policy['controls'])} controls, {len(policy['sources'])} official sources, "
        f"{len(data['pack_files'])} browser-local pack files"
    )


if __name__ == "__main__":
    main()
