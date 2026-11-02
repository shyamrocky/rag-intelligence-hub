"""Final successor consumer-boundary controls on real frozen source evidence."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from rag_hub.acquire import digest
from rag_hub.pdf_corpus import encoded
from rag_hub.pdf_text_handoff import load_units

ROOT = Path(__file__).resolve().parents[1]


def selection():
    return json.loads((ROOT / "config/pdf-text-admission-publication-v1-1.json").read_bytes())


def test_loading_requires_no_pdf_parser_or_model(monkeypatch):
    import pymupdf

    monkeypatch.setattr(
        pymupdf, "open", lambda *a, **kw: pytest.fail("consumer attempted PDF parsing")
    )
    units = load_units(ROOT, **selection())
    assert len(units) == 246
    assert len({sid for u in units for sid in u["required_section_ids"]}) == 1892


@pytest.mark.parametrize("fault", ["decision", "text", "context", "unit_omitted"])
def test_rehashed_forged_publication_still_rejected(monkeypatch, fault):
    s = selection()
    m = json.loads((ROOT / s["manifest_path"]).read_bytes())
    ref = m["publications"][0]
    p = json.loads((ROOT / ref["path"]).read_bytes())
    qa = p["qa"]
    u = next(u for u in qa["pdf_text_support"]["units"] if u["required_context"])
    if fault == "decision":
        next(d for d in qa["quality_decisions"] if d["status"] == "approved_for_index")[
            "status"
        ] = "hold"
    elif fault == "text":
        u["text"] += " forged sentence"
    elif fault == "context":
        u["required_context"] = []
    else:
        qa["pdf_text_support"]["units"].pop()
    altered = encoded(p)
    ref["sha256"] = digest(altered)
    mr = encoded(m)
    s["expected_manifest_sha256"] = digest(mr)
    original = Path.read_bytes

    def read(path):
        if path == ROOT / ref["path"]:
            return altered
        if path == ROOT / s["manifest_path"]:
            return mr
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(ValueError, match="forged_pdf_QA"):
        load_units(ROOT, **s)


def test_expiration_is_warning_not_read_failure(monkeypatch):
    import rag_hub.pdf_publication as publication

    monkeypatch.setattr(
        publication,
        "utc_now",
        lambda: datetime.fromisoformat("2026-10-23T06:12:23.097104+00:00") + timedelta(days=1),
    )
    units = load_units(ROOT, **selection())
    old = [u for u in units if u["metadata"]["content_type"] == "historical_reviewed_paragraph"]
    assert len(old) == 8 and len({s for u in old for s in u["required_section_ids"]}) == 19
    assert all(
        u["publication_expiration"]["retrieval_allowed"]
        and u["publication_expiration"]["status"] == "EXPIRED"
        for u in old
    )
    assert all(
        any(
            x["issue_id"] == "PDF_PUBLICATION_EXPIRED" and x["display_to_user_when_used"]
            for x in u["llm_context"]["qa_observations"]
        )
        for u in old
    )


def test_all_prior_parent_text_and_context_preserved():
    units = load_units(ROOT, **selection())
    old = [u for u in units if u["metadata"]["content_type"] == "historical_reviewed_paragraph"]
    assert len(old) == 8
    for u in old:
        p = u["audit_only"]["historical_passage"]
        assert u["llm_context"]["source_content"][0]["text"] == p["text"]
        ctx = next(
            c
            for c in u["llm_context"]["required_context"]
            if c.get("role") == "mandatory_historical_reviewed_context"
        )
        assert {k: v for k, v in ctx.items() if k != "role"} == p["retrieval_context"]
        assert p["parent_sha256"] and p["owner_receipt_sha256"]


def test_earlier_text_publication_is_exactly_readable():
    s = json.loads((ROOT / "config/pdf-text-admission-publication.json").read_bytes())
    old = load_units(ROOT, **s)
    new = load_units(ROOT, **selection())
    assert {u["unit_id"] for u in old} == {u["unit_id"] for u in new}
    assert {s for u in old for s in u["required_section_ids"]} == {
        s for u in new for s in u["required_section_ids"]
    }
    assert all(
        u["publication_identity"]["qa_release_sha256"]
        != new[0]["publication_identity"]["qa_release_sha256"]
        for u in old
    )
