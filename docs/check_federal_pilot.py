#!/usr/bin/env python3
"""Verify Federal Pilot Kit schemas, examples, CLI, and browser-local desk."""

from __future__ import annotations

import importlib.util
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "federal-pilot-kit"
DOCS = ROOT / "docs"


def fail(message: str) -> None:
    raise SystemExit(f"Federal Pilot Kit check failed: {message}")


def main() -> None:
    spec = importlib.util.spec_from_file_location("aau_pilot", KIT / "aau_pilot.py")
    if not spec or not spec.loader:
        fail("cannot load aau_pilot.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = json.loads((DOCS / "federal-pilot-data.json").read_text())
    prompts = json.loads((KIT / "acquisition-review-prompts.json").read_text())
    examples = []
    for directory in sorted((KIT / "examples").iterdir()):
        agency = json.loads((directory / "agency-intake.json").read_text())
        vendor = json.loads((directory / "vendor-response.json").read_text())
        tests = json.loads((directory / "acceptance-tests.json").read_text())
        errors = module.cross_validate(agency, vendor, tests)
        if errors:
            fail(f"{directory.name} is invalid: {'; '.join(errors)}")
        assessment = module.assess_exchange(agency, vendor, tests)
        if assessment["boundary"]["vendor_ranked"] is not False:
            fail(f"{directory.name} violates non-ranking boundary")
        if assessment["boundary"]["award_recommendation_made"] is not False:
            fail(f"{directory.name} violates non-award boundary")
        examples.append((directory, agency, vendor, tests, assessment))
    if len(examples) != 3:
        fail("exactly three reference exchanges must ship in v0.4")
    if len(data["examples"]) != len(examples):
        fail("browser data and canonical reference exchange counts differ")
    for generated, canonical in zip(data["examples"], examples, strict=True):
        directory, agency, vendor, tests, assessment = canonical
        if generated["slug"] != directory.name:
            fail("browser examples are not sorted by canonical directory")
        for name, value in (("agency", agency), ("vendor", vendor), ("tests", tests), ("assessment", assessment)):
            if generated[name] != value:
                fail(f"browser {directory.name} {name} differs from canonical source")
    if data["pack_files"] != list(module.PACK_NAMES):
        fail("browser and CLI pack contracts differ")
    if data["review_prompts"] != prompts:
        fail("browser review prompts differ from the canonical source")

    source_ledger = json.loads((KIT / "lessons" / "source-ledger.json").read_text())
    source_errors = module.validate_source_ledger(source_ledger)
    if source_errors:
        fail("lesson source ledger is invalid: " + "; ".join(source_errors))
    as_of = date.fromisoformat(data["lesson_exchange"]["as_of"])
    lessons = []
    for path in sorted((KIT / "lessons" / "examples").glob("*.json")):
        lesson = json.loads(path.read_text())
        errors = module.validate_lesson(lesson)
        if errors:
            fail(f"{path.name} is invalid: {'; '.join(errors)}")
        scan = module.scan_sensitive(lesson)
        if not scan["safe_to_package"]:
            fail(f"{path.name} fails the public scan: {scan['findings']}")
        drift = module.policy_drift_report(lesson, source_ledger, as_of)
        if drift["summary"]["missing"] or drift["summary"]["review_due"]:
            fail(f"{path.name} has missing or stale policy dependencies")
        lessons.append((path, lesson, scan, drift))
    if len(lessons) != 4:
        fail("exactly four public lessons must ship in v0.4")
    if sum(item[1]["outcome"]["result"] == "stopped" for item in lessons) != 1:
        fail("v0.4 must publish exactly one deliberately stopped lesson")
    if len(data["lesson_exchange"]["lessons"]) != len(lessons):
        fail("browser and canonical lesson counts differ")
    for generated, canonical in zip(data["lesson_exchange"]["lessons"], lessons, strict=True):
        path, lesson, scan, drift = canonical
        if generated != {
            "slug": path.stem,
            "path": f"federal-pilot-kit/lessons/examples/{path.name}",
            "record": lesson,
            "scan": scan,
            "drift": drift,
        }:
            fail(f"browser lesson differs from canonical source: {path.name}")
    reference_lessons = {
        item[1]["origin"]["exchange_path"].rsplit("/", 1)[-1]: item[1]
        for item in lessons
        if item[1]["origin"]["kind"] == "reference_exchange"
    }
    if set(reference_lessons) != {item[0].name for item in examples}:
        fail("each reference exchange must have one linked public lesson")
    for directory, agency, vendor, tests, _ in examples:
        errors = module.cross_validate_lesson(
            reference_lessons[directory.name], agency, vendor, tests, source_ledger
        )
        if errors:
            fail(f"{directory.name} lesson does not close its source exchange: {'; '.join(errors)}")

    schema_map = {
        "agency-intake.schema.json": ("federal-pilot-agency.schema.json", module.AGENCY_VERSION),
        "vendor-evidence-response.schema.json": ("federal-pilot-vendor.schema.json", module.VENDOR_VERSION),
        "acceptance-test-manifest.schema.json": ("federal-pilot-tests.schema.json", module.TEST_VERSION),
        "lesson-record.schema.json": ("federal-ai-lesson.schema.json", module.LESSON_VERSION),
    }
    for source_name, (published_name, version) in schema_map.items():
        source = (KIT / source_name).read_text()
        if (DOCS / published_name).read_text() != source:
            fail(f"published {published_name} differs from canonical schema")
        schema = json.loads(source)
        if schema["properties"]["profile_version"]["const"] != version:
            fail(f"{source_name} and validator versions differ")

    allowed_domains = {
        "www.whitehouse.gov", "www.gao.gov", "www.gsa.gov", "www.nist.gov",
        "www.justice.gov", "www.ecfr.gov", "www.acquisition.gov",
    }
    urls = [source["url"] for source in prompts["sources"]]
    urls.extend(source["url"] for source in source_ledger["sources"])
    for _, _, _, tests, _ in examples:
        urls.extend(source["url"] for source in tests["sources"])
    for url in urls:
        if urlparse(url).hostname not in allowed_domains:
            fail(f"official source is not on an allowlisted domain: {url}")
    if prompts["review_due"] <= prompts["last_verified"]:
        fail("review prompt review_due must follow last_verified")
    if "not solicitation language" not in prompts["boundary"].lower():
        fail("review prompts must preserve the non-clause boundary")

    public_corpus = json.dumps(data)
    forbidden = {
        "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
        "SSN pattern": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "private key": re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
    }
    for label, pattern in forbidden.items():
        if pattern.search(public_corpus):
            fail(f"public browser data contains a likely {label}")

    html = (DOCS / "index.html").read_text()
    css = (DOCS / "federal-pilot.css").read_text()
    js = (DOCS / "federal-pilot.js").read_text()
    for token in (
        'id="federal-pilot"', 'id="pilot-desk"', 'id="pilot-example-cards"',
        'data-pilot-file="agency"', 'data-pilot-file="vendor"',
        'data-pilot-file="tests"', 'id="pilot-download-assessment"',
        "Files stay in this browser tab", 'class="pilot-trust"',
        "Verify the tool before it verifies a claim", 'id="lessons-exchange"',
        'id="lesson-results"', 'id="lesson-search"', 'id="lesson-result-filter"',
        'id="lesson-category-filter"', 'id="lesson-source-list"',
    ):
        if token not in html and token not in js:
            fail(f"public interface is missing {token!r}")
    for token in (
        "federal-pilot-data.json", "aau-federal-pilot-assessment/0.2", "aau-federal-ai-lesson/0.4", "JSON_LIMITS",
        "vendor_ranked: false", "award_recommendation_made: false", "URL.createObjectURL",
        "renderLessons", "renderLessonSources",
    ):
        if token not in js:
            fail(f"browser inspector is missing {token!r}")
    if "localStorage" in js or "sessionStorage" in js:
        fail("Federal Pilot Desk must not persist exchange contents")
    if "innerHTML" in js or "insertAdjacentHTML" in js:
        fail("Federal Pilot Desk must render uploaded values as text, never HTML")
    if "http://" in js or "https://" in js:
        fail("Federal Pilot Desk JavaScript must not call a remote endpoint")
    if "fetch(" not in js or js.count("fetch(") != 1:
        fail("Federal Pilot Desk must have exactly one local data fetch")
    if "@media (prefers-reduced-motion: reduce)" not in css:
        fail("Federal Pilot Desk needs a reduced-motion mode")

    totals = {
        "pilots": len(examples),
        "requirements": sum(item[4]["summary"]["requirements"] for item in examples),
        "cases": sum(item[4]["summary"]["cases"] for item in examples),
        "gaps": sum(item[4]["summary"]["visible_gaps"] for item in examples),
    }
    asset = (DOCS / "assets" / "federal-pilot.svg").read_text()
    for value in totals.values():
        if f">{value}</text>" not in asset:
            fail(f"Federal Pilot visual proof is stale: missing {value}")
    lesson_asset = (DOCS / "assets" / "lessons-exchange.svg").read_text()
    lesson_stats = data["lesson_exchange"]["stats"]
    for value in (
        lesson_stats["lessons"],
        lesson_stats["stopped"],
        lesson_stats["policy_dependencies"],
        lesson_stats["bounded_practices"],
    ):
        if f">{value}</text>" not in lesson_asset:
            fail(f"Lessons Exchange visual proof is stale: missing {value}")
    print(
        "Federal Pilot Kit verified: "
        f"{totals['pilots']} pilots, {totals['requirements']} gates, "
        f"{totals['cases']} cases, {totals['gaps']} visible gaps, "
        f"{lesson_stats['lessons']} public lessons"
    )


if __name__ == "__main__":
    main()
