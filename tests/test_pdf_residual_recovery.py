"""Frozen-source residual qualification controls, not new human attestations."""

import copy
import json
from pathlib import Path

import pytest

from rag_hub.acquire import digest
from rag_hub.pdf_corpus import encoded, load_corpus
from rag_hub.pdf_residual_recovery import baseline_grid, browser_row, supplement
from rag_hub.pdf_text_handoff import load_units, validate_consumption_unit
from rag_hub.pdf_text_recovery import line_rows, source_text

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "data/validation/pdf/residual-recovery-v1"


def read(path):
    return json.loads((ROOT / path).read_bytes())


@pytest.fixture(scope="module")
def corpus():
    return load_corpus(ROOT)


@pytest.fixture(scope="module")
def selection():
    return read("config/pdf-residual-admission-publication-v1.json")


@pytest.fixture(scope="module")
def views(selection):
    return load_units(ROOT, **selection)


@pytest.mark.parametrize("doc", ["C01", "C02", "C06", "C14"])
def test_exact_source_spans_and_predecessor_scopes(doc, corpus):
    prior = read(f"data/normalized/pdf/text-recovery-v1/{doc}.json")
    current = read(f"data/normalized/pdf/residual-recovery-v1/{doc}.json")
    new = {u["id"]: u for u in current["units"]}
    assert all(new[u["id"]] == u for u in prior["units"])
    bs = {b["block_id"]: b for b in corpus["documents"][doc]["blocks"]}
    for u in current["units"]:
        assert source_text(u["source_members"], bs) == u["text"]
        assert (
            digest(encoded({k: v for k, v in u.items() if k != "unit_sha256"})) == u["unit_sha256"]
        )
    old_rows = {r["section_id"]: r for r in prior["section_accounting"]}
    assert set(old_rows) == {r["section_id"] for r in current["section_accounting"]}
    for row in current["section_accounting"]:
        old = old_rows[row["section_id"]]
        if old["disposition"] != "HOLD":
            assert row["disposition"] == old["disposition"]
            assert set(old["unit_ids"]) <= set(row["unit_ids"])
        else:
            assert row["recovery_role"] in {
                "fully_recovered_into_complete_unit",
                "scope_limited_projection",
                "required_context_only",
                "intentional_non_knowledge_exclusion",
                "retained_HOLD",
            }
        for bid, intervals in row["unqualified_intervals"].items():
            for a, z in intervals:
                assert not any(
                    m["block_id"] == bid and a < m["end"] and m["start"] < z
                    for u in current["units"]
                    for m in u["source_members"]
                )


def test_real_489_accounting_and_authoritative_loaded_scope(views):
    all_rows = [
        r
        for d in ["C01", "C02", "C06", "C14"]
        for r in read(f"data/normalized/pdf/residual-recovery-v1/{d}.json")["section_accounting"]
    ]
    residual = [r for r in all_rows if r.get("predecessor_disposition") == "HOLD"]
    assert len(all_rows) == len({r["section_id"] for r in all_rows}) == 2425
    assert len(residual) == 489
    assert sum(r["disposition"] in {"STANDARD", "ILLUSTRATIVE"} for r in residual) == 99
    assert sum(r["disposition"] == "EXCLUDED" for r in residual) == 32
    assert sum(r["disposition"] == "HOLD" for r in residual) == 358
    assert len(views) == 309
    admitted = {
        r["section_id"] for r in all_rows if r["disposition"] in {"STANDARD", "ILLUSTRATIVE"}
    }
    assert len(admitted) == 1991
    assert {sid for u in views for sid in u["required_section_ids"]} == admitted


def test_decoding_excerpts_withhold_unsupported_formula_parts(views):
    u = next(
        u
        for u in views
        if u["metadata"]["content_type"] == "residual_prose_projection"
        and "Thorough Decoding" in u["llm_context"]["source_content"][0]["text"]
    )
    text = u["llm_context"]["source_content"][0]["text"]
    assert "Fast Decoding" in text and "pθ" not in text and "pη" not in text
    assert u["llm_context"]["source_content"][0]["structure"]["non_contiguous_excerpts"]
    assert any(
        "intervening formula-bearing sentences" in x
        for x in u["llm_context"]["qualification"]["limitations"]
    )
    assert u["reference_classification"] == "ILLUSTRATIVE_REFERENCE"


def test_cross_column_footnote_separate_and_scalar_minus_preserved(views):
    u = next(
        u
        for u in views
        if u["metadata"]["content_type"] == "residual_prose"
        and {m["block_id"] for m in u["audit_only"]["source_members"]}
        == {"C14:b00038", "C14:b00040"}
    )
    assert "k −1" in u["llm_context"]["source_content"][0]["text"]
    assert "C14:b00039" not in {m["block_id"] for m in u["audit_only"]["source_members"]}


def test_subscript_attachment_inverse_and_math_stays_scoped(views):
    us = [u for u in views if u["metadata"]["content_type"] == "residual_inline_notation_prose"]
    assert len(us) == 2
    for u in us:
        s = u["llm_context"]["source_content"][0]
        assert s["text"].count("Precision_Ω") == 1
        assert s["structure"]["relationships"][0]["type"] == "inline_subscript"
        assert u["known_limitations"]
        assert not any(
            m["block_id"] in {"C06:b00285", "C06:b00291"} for m in u["audit_only"]["source_members"]
        )


def test_entropy_excerpt_omits_incomplete_variable_definitions(views):
    u = next(
        u
        for u in views
        if u["metadata"]["content_type"] == "residual_prose"
        and u["llm_context"]["source_content"][0]["text"].startswith(
            "We observe that in general, token entropy"
        )
    )
    assert u["audit_only"]["source_members"][0]["start"] > 0
    assert "probability assigned to token" not in u["llm_context"]["source_content"][0]["text"]


def test_table82_hidden_navigation_never_enters_cells(views):
    units = [
        u
        for u in views
        if u["source_id"] == "C06"
        and u["metadata"]["content_type"] == "table"
        and any(m["block_id"] == "C06:b01265" for m in u["audit_only"]["source_members"])
    ]
    assert len(units) == 1
    u = units[0]
    assert not {m["block_id"] for m in u["audit_only"]["source_members"]} & {
        f"C06:b{n:05}" for n in range(1241, 1263)
    }
    assert [c["text"] for c in u["llm_context"]["source_content"][0]["structure"]["rows"][0]] == [
        "TokenText",
        "200",
        "0",
        "10",
        "90.8 ±\n26.5",
        "2.5 ± 1.6",
        "20.5 ± 10.2",
        "2.5 ±\n1.6",
    ]
    assert u["required_context"][-1]["text"] == "Wikitext, all-MiniLM-L6-v2"


def test_hierarchical_table_headers_are_explicit(views):
    u = next(
        u
        for u in views
        if u["source_id"] == "C14"
        and u["metadata"]["content_type"] == "table"
        and "C14:b00445" in {m["block_id"] for m in u["audit_only"]["source_members"]}
    )
    s = u["llm_context"]["source_content"][0]["structure"]
    assert [x["leaf_column_indices"] for x in s["column_groups"]] == [[1, 2], [3, 4]]
    assert [x["text"] for x in s["rows"][0]] == [
        "LongChat-13B (16K)",
        "55.6 ± 2.7",
        "70",
        "219.7 ± 48.5",
        "588",
    ]


@pytest.mark.parametrize(
    "fault", ["missing_cell", "wrong_column", "wrong_header", "extra_label", "negative_sign"]
)
def test_native_browser_row_negative_and_protected_values(corpus, fault):
    d = corpus["documents"]["C06"]
    bs = {b["block_id"]: b for b in d["blocks"]}
    layout = read("workspace/pdf-residual-recovery/v1/NATIVE_LAYOUT.json")["C06"]
    hs = copy.deepcopy(line_rows(bs["C06:b00793"], layout))
    body = copy.deepcopy(line_rows(bs["C06:b00794"], layout))
    assert browser_row(hs, body)
    if fault == "missing_cell":
        body.pop(1)
    elif fault == "wrong_column":
        body[1]["bbox"][0] += 200
        body[1]["bbox"][2] += 200
    elif fault == "wrong_header":
        hs[4]["text"] = "Precision"
    elif fault == "extra_label":
        body.append(dict(body[3], text="Legal"))
    else:
        body[5]["text"] = "-27.5"
        assert browser_row(hs, body)[4]["text"] == "91.5 ±\n-27.5"
        return
    assert browser_row(hs, body) is None


@pytest.mark.parametrize("fault", ["source", "block"])
def test_source_plan_does_not_authorize_wrong_snapshot_or_text(corpus, fault):
    d = corpus["documents"]["C01"]
    p = copy.deepcopy(
        read("data/validation/pdf/residual-recovery-v1/SOURCE_RECOVERY_PLAN.json")["documents"][
            "C01"
        ]
    )
    if fault == "source":
        p["source_sha256"] = "0" * 64
    else:
        p["block_bindings"][next(iter(p["block_bindings"]))] = "0" * 64
    with pytest.raises(ValueError, match="residual_plan"):
        supplement(d, {}, {}, p)


@pytest.mark.parametrize(
    "field",
    [
        "required_context",
        "known_limitations",
        "llm_context",
        "publication_identity",
        "required_section_ids",
        "citation_locators",
    ],
)
def test_restricted_consumer_cannot_strip_qualifications(views, selection, monkeypatch, field):
    import rag_hub.pdf_text_handoff as reader

    monkeypatch.setattr(reader, "load_units", lambda *a, **k: views)
    u = copy.deepcopy(
        next(u for u in views if u["metadata"]["content_type"] == "residual_inline_notation_prose")
    )
    u[field] = [] if isinstance(u[field], list) else {}
    with pytest.raises(ValueError, match="altered_unapproved"):
        validate_consumption_unit(ROOT, u, selection=selection)


@pytest.mark.parametrize(
    "fault", ["source", "publication", "manifest", "policy", "overlay", "component"]
)
def test_current_integrity_paths_fail_closed(selection, corpus, monkeypatch, fault):
    m = read(selection["manifest_path"])
    paths = {
        "source": corpus["documents"]["C06"]["source"]["snapshot_path"],
        "publication": m["publications"][0]["path"],
        "manifest": selection["manifest_path"],
        "policy": "config/pdf-residual-qualification-policy-v1.json",
        "overlay": "data/normalized/pdf/residual-recovery-v1/C06.json",
        "component": "src/rag_hub/pdf_residual_recovery.py",
    }
    target = ROOT / paths[fault]
    original = Path.read_bytes
    monkeypatch.setattr(
        Path, "read_bytes", lambda p: original(p) + b" " if p == target else original(p)
    )
    with pytest.raises(ValueError):
        load_units(ROOT, **selection)


def test_owner_acceptance_preserves_inspection_only_closure():
    base = ROOT / "data/validation/html-markdown-qa-closure/v1"
    a = json.loads((base / "OWNER_ACCEPTANCE.json").read_bytes())
    assert a["status"] == "ACCEPTED" and a["acceptance_date"] == "2026-10-22"
    assert a["closure_index_authority"] == "INSPECTION_ONLY"
    for p, h in a["technical_closure_bindings"].items():
        assert digest((base / p).read_bytes()) == h


def test_reader_does_not_reparse_pdf(selection, monkeypatch):
    import pymupdf

    monkeypatch.setattr(pymupdf, "open", lambda *a, **k: pytest.fail("consumer reparsed PDF"))
    assert len(load_units(ROOT, **selection)) == 309


def test_no_grid_for_crossing_or_merged_cells(corpus):
    d = corpus["documents"]["C14"]
    blocks = {b["block_id"]: b for b in d["blocks"]}
    layout = read("workspace/pdf-residual-recovery/v1/NATIVE_LAYOUT.json")["C14"]
    header = line_rows(blocks["C14:b00446"], layout)
    body = copy.deepcopy(line_rows(blocks["C14:b00447"], layout))
    assert baseline_grid(header, body)
    # A numeric cell crossing its neighboring column must never be guessed
    # into a merged/header relationship merely because other rows align.
    body[1]["bbox"][2] = body[2]["bbox"][2] + 5
    assert baseline_grid(header, body) is None
