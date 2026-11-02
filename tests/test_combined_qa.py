"""Combined dispatch regressions; no owner receipt or content admission execution."""

import inspect
import json
import os
from pathlib import Path

import pytest

from rag_hub.acquire import digest
from rag_hub.content_validation import ValidationInput
from rag_hub.pdf_prose_review import verify_release
from rag_hub.shared.qa import assess

ROOT = Path(__file__).resolve().parents[1]
RELEASE = os.environ.get("RAG_TEST_QA_RELEASE", "config/combined-qa-successor.json")


def test_combined_owner_preserves_PDF_and_HTML_interfaces():
    arguments = inspect.signature(assess).parameters
    assert {"pdf_prose_admission", "pdf_replay", "html_evidence"} <= arguments.keys()
    assert all(
        arguments[k].default is None for k in ("pdf_prose_admission", "pdf_replay", "html_evidence")
    )
    assert ValidationInput.__dataclass_fields__["html_evidence"].default is None


def test_combined_release_is_explicit_and_complete():
    path = ROOT / RELEASE
    if not path.exists():
        pytest.skip("combined private evidence not present")
    value = verify_release(ROOT, RELEASE, digest(path.read_bytes()))
    assert value["version"] == "combined-scoped-qa-1.0"
    assert {"src/rag_hub/html_validation.py", "src/rag_hub/pdf_prose_review.py"} <= value[
        "files"
    ].keys()
    predecessor = ROOT / "config/pdf-prose-qa-successor.json"
    assert digest(predecessor.read_bytes()) == value["predecessor_qa_release_sha256"]
    # An earlier identity must not silently describe the combined code.
    with pytest.raises(ValueError, match="fingerprint_mismatch"):
        verify_release(ROOT, str(predecessor.relative_to(ROOT)), digest(predecessor.read_bytes()))


def test_HTML_evidence_cannot_activate_PDF_admission(tmp_path):
    from test_html_validation import example

    from rag_hub.html_validation import check_document, fidelity
    from rag_hub.schemas import ParsedBlock, Section
    from rag_hub.shared.registry import Adapter

    document = example()
    document["section_checks"] = check_document(document)
    arguments = (
        tmp_path,
        document["source"],
        document["raw"],
        [ParsedBlock.model_validate(r["block"]) for r in document["parsed"]["records"]],
        [Section.model_validate(r["section"]) for r in document["normalized"]["records"]],
        document["normalized"]["audit"],
        Adapter("owned-html", "html", "test", None, fidelity, None),
        "owned",
        {},
    )
    baseline = assess(*arguments, html_evidence={"OWNED": document})
    assert baseline["source_fidelity"] == "manual_required"
    assert all(r["status"] == "hold" for r in baseline["quality_decisions"])
    assert "scoped_pdf_support" not in baseline
    with pytest.raises(TypeError):
        assess(*arguments, html_evidence={"OWNED": document}, pdf_prose_admission={})


def test_legacy_ledger_not_republished_or_promoted():
    path = (
        ROOT
        / "data/validation/bf9ec63f85912861a86677647d2056a6e23a7e0758315682cec29d78c0fe4580/decisions.jsonl"
    )
    if not path.exists():
        pytest.skip("private historical decisions not present")
    assert (
        digest(path.read_bytes())
        == "3dec07fdd049d9e0a43ff84b78dddcc97d5ae8aef6ab146ea02c9f475f259064"
    )
    rows = [json.loads(s) for s in path.read_text().splitlines()]
    approved = [r for r in rows if r["status"] == "approved_for_index"]
    assert len(approved) == 40 and {r["doc_id"] for r in approved} == {"C04"}
    assert len(rows) - len(approved) == 1634
