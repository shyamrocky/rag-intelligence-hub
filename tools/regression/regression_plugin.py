"""Explicit test-only release selection; never a production/publication selector."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
QA_RELEASE = "workspace/pdf-residual-recovery/v1/qa-regression-identity.json"
FOUNDATION = ROOT / "workspace/pdf-residual-recovery/v1/regression-release"


def pytest_configure(config):
    import os

    from rag_hub.acquire import digest
    from rag_hub.pdf_prose_review import verify_release
    from rag_hub.shared import pipeline

    if os.environ.get("RAG_TEST_QA_RELEASE") != QA_RELEASE:
        raise pytest.UsageError("Use tools/regression/run.py: explicit synthetic QA identity required")
    identity = ROOT / QA_RELEASE
    verify_release(ROOT, QA_RELEASE, digest(identity.read_bytes()))
    pipeline.verify_foundation(FOUNDATION)
    pipeline.HOME = FOUNDATION  # Process-local test override only; no maintained default changes.
    config.addinivalue_line("markers", "historical_replay: exact archived implementation checks")
    config.addinivalue_line("markers", "dashboard_ui: requires the locked Streamlit environment")


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_collection_modifyitems(config, items):
    """Explicit, reported job partition; every collected test belongs to a job."""
    COLLECTED[:] = [item.nodeid for item in items]
    for item in items:
        if item.nodeid in {
            "tests/test_pdf_nontext.py::test_shared_guards_policy_and_contracts_are_reused",
            "tests/test_validation_local.py::test_actual_1665_coverage_promotion_boundaries_and_preservation",
        }:
            item.add_marker(pytest.mark.historical_replay)
        if item.nodeid.startswith("tests/test_chunk_dashboard.py::") or (
            item.nodeid.startswith("tests/test_ingestion_dashboard.py::test_streamlit_")
        ):
            item.add_marker(pytest.mark.dashboard_ui)
    yield


@pytest.fixture(scope="module", autouse=True)
def historical_crossing_fixture_clock(request):
    """Reuse the existing pre-load clock fixture, restricted to its two modules."""
    from m2_clock_regression_plugin import historical_crossing_fixture_clock as existing

    # Invoke the existing fixture function; the production clock is restored by its finally.
    yield from existing.__wrapped__(request)


def pytest_report_header(config):
    return "TEST ONLY: explicit current QA/foundation; archived replay and dashboard jobs separate"


def pytest_sessionfinish(session, exitstatus):
    """Emit exact collected/selected IDs so deliberate job boundaries remain auditable."""
    import os

    target = os.environ.get("RAG_REGRESSION_SELECTION")
    if target:
        Path(target).write_text(json.dumps({
            "collected_nodeids": COLLECTED,
            "deselected_nodeids": DESELECTED,
            "selected_nodeids": [i.nodeid for i in session.items],
            "executed_nodeids": sorted(EXECUTED),
            "call_executed_nodeids": sorted(CALL_EXECUTED),
            "phase_reports": PHASE_REPORTS,
            "collect_only": session.config.option.collectonly,
            "exitstatus": int(exitstatus),
            "outcomes": OUTCOMES,
            "qa_identity": QA_RELEASE,
            "foundation": str(FOUNDATION.relative_to(ROOT)),
            "scope": "TEST_ONLY_NOT_ADMISSION_AUTHORITY",
        }, indent=2) + "\n")


OUTCOMES = {}
COLLECTED = []
DESELECTED = []
EXECUTED = set()
CALL_EXECUTED = set()
PHASE_REPORTS = []


def pytest_deselected(items):
    DESELECTED.extend(item.nodeid for item in items)


def pytest_runtest_logreport(report):
    EXECUTED.add(report.nodeid)
    if report.when == "call":
        CALL_EXECUTED.add(report.nodeid)
    PHASE_REPORTS.append({"node_id": report.nodeid, "phase": report.when,
                          "outcome": report.outcome})
    if report.failed:
        OUTCOMES[report.nodeid] = "FAILED" if report.when == "call" else "ERROR"
    elif report.skipped:
        OUTCOMES[report.nodeid] = "SKIPPED"
    elif report.when == "call":
        OUTCOMES[report.nodeid] = "PASSED"
