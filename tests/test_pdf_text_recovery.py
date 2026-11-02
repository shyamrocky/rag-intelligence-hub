"""Real frozen PDF scope/guard regressions; machine-authored, not human attestations."""

import copy
import json
from pathlib import Path

import pytest

from rag_hub.acquire import digest
from rag_hub.pdf_corpus import encoded, load_corpus
from rag_hub.pdf_text_handoff import (
    load_units,
    serialize_consumption_unit,
    validate_consumption_unit,
)
from rag_hub.pdf_text_recovery import (
    PdfTextDecision,
    decision_from_proof,
    fragment,
    simple_grid,
    source_text,
    verify_release,
)
from rag_hub.validation_models import ValidationPolicy, ValidationResult

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "data/validation/pdf/text-recovery-v1"


@pytest.fixture(scope="module")
def corpus():
    return load_corpus(ROOT)


@pytest.fixture(scope="module")
def selection():
    return json.loads((ROOT / "config/pdf-text-admission-publication.json").read_bytes())


@pytest.fixture(scope="module")
def views(selection):
    return load_units(ROOT, **selection)


@pytest.mark.parametrize("doc", ["C01", "C02", "C06", "C14"])
def test_all_sections_and_spans_accounted(doc, corpus):
    e = json.loads((ROOT / f"data/normalized/pdf/text-recovery-v1/{doc}.json").read_bytes())
    original = corpus["documents"][doc]
    bs = {b["block_id"]: b for b in original["blocks"]}
    assert {r["section_id"] for r in e["section_accounting"]} == {
        s["section_id"] for s in original["sections"]
    }
    assert len(e["section_accounting"]) == len(original["sections"])
    for u in e["units"]:
        assert source_text(u["source_members"], bs) == u["text"]
        assert digest(u["text"].encode()) == u["text_sha256"]
        assert (
            digest(encoded({k: v for k, v in u.items() if k != "unit_sha256"})) == u["unit_sha256"]
        )
    assert all(
        r["reason"] and r["disposition"] in {"STANDARD", "ILLUSTRATIVE", "EXCLUDED", "HOLD"}
        for r in e["section_accounting"]
    )
    assert all("unqualified_intervals" in r for r in e["section_accounting"])


@pytest.mark.parametrize("fault", ["start", "end", "hash", "bbox", "block"])
def test_source_span_corruption_rejected(corpus, fault):
    b = corpus["documents"]["C01"]["blocks"][8]
    m = fragment(b)
    bs = {b["block_id"]: b}
    if fault == "start":
        m["start"] = -1
    elif fault == "end":
        m["end"] += 1
    elif fault == "hash":
        m["span_sha256"] = "0" * 64
    elif fault == "bbox":
        m["locator"] = dict(m["locator"], bbox=[0, 0, 1, 1])
    else:
        m["block_id"] = "forged"
    with pytest.raises((ValueError, KeyError)):
        source_text([m], bs)


def test_C02_dropcap_is_source_bound_and_reversible(views):
    v = next(
        v
        for v in views
        if v["source_id"] == "C02"
        and "LARGE language models" in v["llm_context"]["source_content"][0]["text"]
    )
    assert "I. INTRODUCTION\nLARGE" in v["llm_context"]["source_content"][0]["text"]
    assert "L\nARGE" in v["audit_only"]["original_extracted_text"]


def test_tables_have_original_cells_and_no_invented_numeric_values(views):
    tables = [u for u in views if u["metadata"]["content_type"] == "table"]
    assert {u["source_id"] for u in tables} >= {"C01", "C06", "C14"}
    for u in tables:
        s = u["llm_context"]["source_content"][0]["structure"]
        assert s["headers"] and s["rows"]
        assert all(len(row) == len(s["headers"]) for row in s["rows"])
        assert not s["merged_cells_supported"]
        assert u["reference_classification"] == "ILLUSTRATIVE_REFERENCE"
    c = next(
        u
        for u in tables
        if u["source_id"] == "C14"
        and any(
            "62.9%" in c.get("text", "")
            for row in u["llm_context"]["source_content"][0]["structure"]["rows"]
            for c in row
        )
    )
    row = c["llm_context"]["source_content"][0]["structure"]["rows"][0]
    assert [x["text"] for x in row] == ["Claude-1.3", "62.9%", "58.3%", "59.7%"]


@pytest.mark.parametrize(
    "fault", ["missing_cell", "shifted_column", "wrong_baseline", "negative_sign"]
)
def test_grid_negative_controls(corpus, fault):
    d = corpus["documents"]["C14"]
    h = copy.deepcopy(d["blocks"][460])
    b = copy.deepcopy(d["blocks"][461])
    # Derive the actual native line positions from the frozen source replay.
    layout = json.loads(
        (ROOT / "workspace/pdf-text-recovery/v1/NATIVE_SOURCE_REPLAY.json").read_bytes()
    )["C14"]["native_layout"]
    layout = copy.deepcopy(layout)
    assert simple_grid(h, b, layout)
    if fault == "missing_cell":
        layout[b["block_id"]]["lines"].pop()
    elif fault == "shifted_column":
        layout[b["block_id"]]["lines"][1]["bbox"][2] += 30
    elif fault == "wrong_baseline":
        layout[b["block_id"]]["lines"][1]["bbox"][1] += 8
    else:
        # Signs are literal source values; do not strip or reinterpret them.
        b["content"] = b["content"].replace("62.9%", "-2.9%", 1)
        b["content_sha256"] = digest(b["content"].encode())
        result = simple_grid(h, b, layout)
        assert result["rows"][0][1]["text"] == "-2.9%"
        return
    assert simple_grid(h, b, layout) is None


def test_only_five_owner_verified_formula_references_are_reused(views):
    fs = [u for u in views if u["metadata"]["content_type"] == "mathematical_reference"]
    assert len(fs) == 5
    assert {
        u["llm_context"]["source_content"][0]["structure"]["reference_case_id"] for u in fs
    } == {f"MQ-S0{i}" for i in range(1, 6)}
    assert all(
        u["reference_classification"] == "ILLUSTRATIVE_REFERENCE" and u["known_limitations"]
        for u in fs
    )
    assert all(not u["llm_context"]["source_content"][0]["text"].startswith("\\\\") for u in fs)


def test_caption_does_not_certify_visual_interpretation(views):
    cs = [u for u in views if u["metadata"]["content_type"] == "caption"]
    assert {u["source_id"] for u in cs} == {"C01", "C02", "C06", "C14"}
    assert all(
        "do not infer unseen values" in u["llm_context"]["qualification"]["limitations"][0]
        for u in cs
    )


def test_C06_bibtex_numbers_are_presentation_not_payload(views):
    u = next(
        u
        for u in views
        if u["source_id"] == "C06"
        and u["metadata"]["content_type"] == "code_example"
        and "@techreport{" in u["llm_context"]["source_content"][0]["text"]
    )
    payload = u["llm_context"]["source_content"][0]["text"]
    assert len(payload.splitlines()) == 8
    assert not any(line.isdigit() for line in payload.splitlines())
    assert "  title =" in payload and "  author =" in payload
    assert len(u["audit_only"]["presentation_evidence"]["printed_line_numbers"]) == 8


@pytest.mark.parametrize(
    "field",
    [
        "known_limitations",
        "required_context",
        "llm_context",
        "required_section_ids",
        "publication_identity",
        "citation_locators",
    ],
)
def test_qualified_unit_cannot_be_stripped_or_forged(selection, views, monkeypatch, field):
    u = copy.deepcopy(next(u for u in views if u["required_context"] and u["known_limitations"]))
    u[field] = [] if isinstance(u[field], list) else {}
    # Reuse an already fully verified load to isolate whole-envelope validation.
    import rag_hub.pdf_text_handoff as reader

    monkeypatch.setattr(reader, "load_units", lambda *a, **kw: views)
    with pytest.raises(ValueError, match="altered_unapproved"):
        validate_consumption_unit(ROOT, u, selection=selection)


def test_unknown_and_partial_unit_rejected(selection, views, monkeypatch):
    import rag_hub.pdf_text_handoff as reader

    monkeypatch.setattr(reader, "load_units", lambda *a, **kw: views)
    u = copy.deepcopy(views[0])
    u["unit_id"] = "not-admitted"
    with pytest.raises(ValueError):
        validate_consumption_unit(ROOT, u, selection=selection)
    u = copy.deepcopy(next(v for v in views if len(v["required_section_ids"]) > 1))
    u["required_section_ids"].pop()
    with pytest.raises(ValueError):
        serialize_consumption_unit(ROOT, u, selection=selection)


@pytest.mark.parametrize(
    "target", ["source", "publication", "manifest", "component", "authorization", "evidence"]
)
def test_integrity_failures_fail_closed(selection, monkeypatch, target):
    manifest = json.loads((ROOT / selection["manifest_path"]).read_bytes())
    release = json.loads((ROOT / selection["release_path"]).read_bytes())
    paths = {
        "source": json.loads(
            (ROOT / "data/parsed/pdf/four-pdf-poc-v1/C01/source.json").read_bytes()
        )["snapshot_path"],
        "publication": manifest["publications"][0]["path"],
        "manifest": selection["manifest_path"],
        "component": "src/rag_hub/pdf_text_recovery.py",
        "authorization": manifest["admission"]["authorization_path"],
        "evidence": "data/normalized/pdf/text-recovery-v1/C01.json",
    }
    assert release["files"]
    original = Path.read_bytes
    p = ROOT / paths[target]
    monkeypatch.setattr(
        Path, "read_bytes", lambda self: original(self) + b" " if self == p else original(self)
    )
    with pytest.raises(ValueError):
        load_units(ROOT, **selection)


def test_new_release_explicit_and_failed_checks_never_waived(selection):
    release = verify_release(ROOT, selection["release_path"], selection["expected_release_sha256"])
    assert release["version"] == "combined-pdf-text-qa-1.0"
    manifest = json.loads((ROOT / selection["manifest_path"]).read_bytes())
    qa = json.loads((ROOT / manifest["publications"][0]["path"]).read_bytes())["qa"]
    r = ValidationResult.model_validate_json(
        qa["pdf_text_fingerprint_inputs"]["validation_json"][0]
    )
    p = ValidationPolicy.model_validate_json(qa["pdf_text_fingerprint_inputs"]["policy_json"])
    bad = r.model_copy(update={"blocking_integrity": True})
    with pytest.raises(ValueError):
        decision_from_proof(bad, p, {"resolved_restrictions": dict.fromkeys(r.reasons, "review")})
    with pytest.raises(ValueError):
        PdfTextDecision.model_validate(dict(qa["quality_decisions"][0], scope={}))
