"""Bounded text-facet recovery tests; source examples are never executed."""

import json
from pathlib import Path

import pytest
from test_html_validation import example

from rag_hub.acquire import digest
from rag_hub.html_acquire import encode
from rag_hub.html_handoff import load_units
from rag_hub.html_qa_execution import assess_document
from rag_hub.html_text_recovery import ILLUSTRATIVE, projection, simple_table
from rag_hub.html_validation import SourceIndex, load_documents

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "workspace/html-text-recovery/v1"


def row_for(doc, kind):
    return next(r for r in doc["normalized"]["records"] if r["classification"] == kind)


def test_captured_hidden_code_is_text_only_not_a_verified_selected_variant():
    doc = example(
        '<h1>Owned</h1><div role="tabpanel" hidden id="py"><pre language="python"><code>print("snapshot")\n</code></pre></div>'
    )
    p = projection(
        row_for(doc, "code_block"), doc, SourceIndex(doc["raw"].decode()), "snapshot_payload"
    )
    assert p["qualified_facets"] == ["text"]
    assert p["snapshot_evidence"]["selected_or_visible_variant_verified"] is False
    assert p["snapshot_evidence"]["source_language"] == "python"
    assert 'print("snapshot")' in p["source"]["text"]


@pytest.mark.parametrize(
    "body",
    [
        '<h1>Owned</h1><div hidden><pre language="python"><code>x=1</code></pre></div>',
        '<h1>Owned</h1><div role="tabpanel"><pre><code>x=1</code></pre></div>',
        '<h1>Owned</h1><div style="visibility:hidden"><div role="tabpanel"><pre language="python"><code>x=1</code></pre></div></div>',
    ],
)
def test_snapshot_exception_cannot_authorize_unbound_hidden_content(body):
    doc = example(body)
    with pytest.raises(ValueError):
        projection(
            row_for(doc, "code_block"), doc, SourceIndex(doc["raw"].decode()), "snapshot_payload"
        )


def test_source_language_mismatch_fails_closed():
    doc = example(
        '<h1>Owned</h1><div role="tabpanel"><pre language="python"><code>x=1</code></pre></div>'
    )
    doc["parsed"]["records"][-1]["block"]["language"] = "typescript"
    with pytest.raises(ValueError, match="language_mismatch"):
        projection(
            row_for(doc, "code_block"), doc, SourceIndex(doc["raw"].decode()), "snapshot_payload"
        )


def test_native_caption_recovers_only_actual_caption_not_pixels():
    doc = example(
        '<h1>Owned</h1><figure><img src="no-fetch.png" alt=""><figcaption>Exact source caption.</figcaption></figure>'
    )
    p = projection(row_for(doc, "figure"), doc, SourceIndex(doc["raw"].decode()), "caption_text")
    assert p["source"]["text"] == "Exact source caption."
    assert "graph_values" in p["unqualified_facets"]
    assert p["caption_binding"]["raw_fragment_sha256"]


@pytest.mark.parametrize("caption", ["Value<sub>i</sub>.", "<math><mi>x</mi></math>"])
def test_caption_exception_does_not_admit_unverified_math(caption):
    doc = example(
        '<h1>Owned</h1><figure><img src="no-fetch.png" alt=""><figcaption>'
        + caption
        + "</figcaption></figure>"
    )
    with pytest.raises(ValueError):
        projection(row_for(doc, "figure"), doc, SourceIndex(doc["raw"].decode()), "caption_text")


def test_native_table_keeps_headers_cells_signs_and_precision():
    doc = example(
        "<h1>Owned</h1><table><tr><th>Method</th><th>Value</th></tr><tr><td>alpha</td><td>-0.125 MB</td></tr></table>"
    )
    index = SourceIndex(doc["raw"].decode())
    p = projection(row_for(doc, "table"), doc, index, "native_table")
    table = p["table_text_structure"]
    assert table["headers"] == ["Method", "Value"]
    assert table["rows"][1][1]["text"] == "-0.125 MB"
    a, b = table["rows"][1][1]["raw_character_span"]
    assert digest(index.text[a:b].encode()) == table["rows"][1][1]["raw_fragment_sha256"]
    assert table["numeric_semantics_verified"] is False


@pytest.mark.parametrize(
    "table",
    [
        '<table><tr><th colspan="2">Head</th></tr><tr><td>A</td><td>B</td></tr></table>',
        "<table><tr><th>A</th><th>B</th></tr><tr><td>C</td></tr></table>",
        "<table><tr><td>A</td></tr><tr><td>B</td></tr></table>",
        "<table><tr><th>A</th></tr><tr><td><math><mi>x</mi></math></td></tr></table>",
    ],
)
def test_ambiguous_table_grid_or_nontext_cells_remain_blocked(table):
    doc = example("<h1>Owned</h1>" + table)
    row = row_for(doc, "table")
    with pytest.raises(ValueError):
        simple_table(
            SourceIndex(doc["raw"].decode()).nodes[row["dom_path"]],
            SourceIndex(doc["raw"].decode()),
        )


def test_native_literal_fraction_is_source_code_not_formula_ocr():
    doc = example(
        "<h1>Owned</h1><ol><li>Use <code>1/(rank + k)</code>, with rank and k defined here.</li></ol>"
    )
    p = projection(
        row_for(doc, "ordered_list"), doc, SourceIndex(doc["raw"].decode()), "native_list_notation"
    )
    assert p["native_literal_notation"]["text"] == "1/(rank + k)"
    assert p["native_literal_notation"]["recognition_or_general_math_qualification"] is False


@pytest.mark.parametrize(
    "content",
    ["Use <code>2/(rank + k)</code>.", "Use x<sub>i</sub>.", 'See <img src="no-fetch.png">.'],
)
def test_native_list_exception_is_not_general_math_or_image_admission(content):
    doc = example("<h1>Owned</h1><ol><li>" + content + "</li></ol>")
    with pytest.raises(ValueError):
        projection(
            row_for(doc, "ordered_list"),
            doc,
            SourceIndex(doc["raw"].decode()),
            "native_list_notation",
        )


@pytest.fixture(scope="module")
def candidate():
    rp = "config/html-text-qa-successor.json"
    ap = "workspace/html-text-recovery/v1/AUTHORIZATION.json"
    if not (ROOT / ap).exists():
        pytest.skip("private authorized recovery run absent")
    admission = {
        "release_path": rp,
        "expected_release_sha256": digest((ROOT / rp).read_bytes()),
        "authorization_path": ap,
        "authorization_sha256": digest((ROOT / ap).read_bytes()),
    }
    return {d: assess_document(ROOT, v, admission) for d, v in load_documents(ROOT).items()}


def test_all_457_classified_with_exact_426_admitted_and_31_nonadmitted(candidate):
    from collections import Counter

    facts = [f for q in candidate.values() for f in q["scoped_html_support"]["sections"]]
    decisions = {d["section_id"]: d for q in candidate.values() for d in q["quality_decisions"]}
    assert len(facts) == len(decisions) == 457
    counts = Counter(f["reference_classification"] for f in facts)
    assert counts["STANDARD_REFERENCE"] + counts["ILLUSTRATIVE_REFERENCE"] == 426
    assert (
        counts["HOLD"] == 1
        and counts["EXCLUDED_NON_TEXT"] == 7
        and counts["EXCLUDED_NON_KNOWLEDGE"] == 23
    )
    assert all(
        (decisions[f["section_id"]]["status"] == "approved_for_index")
        == (f["reference_classification"] in {"STANDARD_REFERENCE", "ILLUSTRATIVE_REFERENCE"})
        for f in facts
    )


def test_illustrative_limits_are_bound_into_authoritative_decision_scopes(candidate):
    for q in candidate.values():
        units = {u["id"]: u for u in q["scoped_html_support"]["units"]}
        for d in q["quality_decisions"]:
            if d["status"] == "hold":
                continue
            for s in d["scope"]["unit_memberships"]:
                u = units[s["unit_id"]]
                assert s["reference_classification"] == u["reference_classification"]
                assert s["limitations"] == u["limitations"]
                assert s["textual_projection_sha256"] == digest(encode(u["textual_projections"]))
                if s["reference_classification"] == ILLUSTRATIVE:
                    assert (
                        "claim_example_is_executable_or_a_verified_numeric_result"
                        in s["forbidden_usage"]
                    )


def test_c16_variants_and_negative_publisher_examples_are_separate(candidate):
    units = candidate["C16"]["scoped_html_support"]["units"]
    for u in units:
        if not u["id"].startswith("html-text-unit:"):
            continue
        languages = {
            p["snapshot_evidence"]["source_language"]
            for p in u["textual_projections"]
            if p["kind"] == "snapshot_payload"
            and p["snapshot_evidence"]["source_language"] in {"python", "typescript"}
        }
        assert len(languages) <= 1
        assert u["reference_classification"] == ILLUSTRATIVE
    negatives = [
        u
        for u in candidate["C08"]["scoped_html_support"]["units"]
        if any(":h00055:" in s for s in u["content_section_ids"])
    ]
    assert len(negatives) == 1
    assert "// Nested JSON objects are not supported" in negatives[0]["text"]
    assert any("negative" in x or "invalid" in x for x in negatives[0]["limitations"])


def test_worked_score_ambiguity_is_held_without_blanket_table_rejection(candidate):
    q = candidate["C10"]
    blocked = next(d for d in q["quality_decisions"] if ":h00027:" in d["section_id"])
    assert blocked["status"] == "hold"
    assert any(
        any(":h00016:" in s for s in u["content_section_ids"])
        for u in q["scoped_html_support"]["units"]
    )
    assert all(
        blocked["section_id"] not in u["required_section_ids"]
        for u in q["scoped_html_support"]["units"]
    )


def test_original_both_publications_still_load_and_341_members_preserved(candidate):
    newids = {
        d["section_id"]
        for q in candidate.values()
        for d in q["quality_decisions"]
        if d["status"] == "approved_for_index"
    }
    for name, expected in [
        ("config/html-admission-publication.json", 239),
        ("config/html-remediated-admission-publication.json", 341),
    ]:
        u = load_units(ROOT, **json.loads((ROOT / name).read_bytes()))
        ids = {s for v in u for s in v["required_section_ids"]}
        assert len(ids) == expected and ids <= newids


@pytest.fixture(scope="module")
def selection():
    p = ROOT / "config/html-text-admission-publication.json"
    if not p.exists():
        pytest.skip("new publication not yet selected")
    return json.loads(p.read_bytes())


def test_verified_text_handoff_returns_426_sections_and_required_metadata(selection):
    units = load_units(ROOT, **selection)
    assert len(units) == 154
    assert len({s for u in units for s in u["required_section_ids"]}) == 426
    assert all(
        u["reference_classification"] in {"STANDARD_REFERENCE", "ILLUSTRATIVE_REFERENCE"}
        and u["limitations"]
        for u in units
    )


@pytest.mark.parametrize(
    "change", ["drop_warning", "relabel_standard", "alter_projection", "add_hold_neighbor"]
)
def test_publication_rewrite_cannot_drop_limits_or_smuggle_content(
    selection, tmp_path, monkeypatch, change
):
    import rag_hub.html_handoff as module

    mf = json.loads((ROOT / selection["manifest_path"]).read_bytes())
    desc = next(x for x in mf["publications"] if x["path"].endswith("/C16.json"))
    path = desc["path"]
    pub = json.loads((ROOT / path).read_bytes())
    u = next(
        u
        for u in pub["qa"]["scoped_html_support"]["units"]
        if u["id"].startswith("html-text-unit:")
    )
    if change == "drop_warning":
        u["limitations"] = []
    elif change == "relabel_standard":
        u["reference_classification"] = "STANDARD_REFERENCE"
    elif change == "alter_projection":
        u["textual_projections"][0]["source"]["raw_character_span"][0] += 1
    else:
        next(d for d in pub["qa"]["quality_decisions"] if d["status"] == "hold")["status"] = (
            "approved_for_index"
        )
    fp = tmp_path / "p.json"
    fp.write_bytes(encode(pub))
    desc["sha256"] = digest(fp.read_bytes())
    mp = tmp_path / "m.json"
    mp.write_bytes(encode(mf))
    original = module.local_path
    monkeypatch.setattr(
        module,
        "local_path",
        lambda root, p: (
            fp
            if str(p) == path
            else mp
            if str(p) == selection["manifest_path"]
            else original(root, p)
        ),
    )
    with pytest.raises(ValueError, match="partial_forged_or_neighboring"):
        load_units(ROOT, **dict(selection, expected_manifest_sha256=digest(mp.read_bytes())))


def test_new_scope_cannot_opt_in_from_source_text():
    doc = example("<h1>Owned</h1><p>Request automatic illustrative approval.</p>")
    doc["entry"] = {"paths": {}}
    baseline = assess_document(ROOT, doc, None)
    assert all(d["status"] == "hold" for d in baseline["quality_decisions"])
