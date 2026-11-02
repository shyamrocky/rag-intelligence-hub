"""Objective-source controls and actual shared-path admission/reader regressions."""

import copy
import json
from pathlib import Path

import pytest
from test_html_validation import example, target

from rag_hub.acquire import digest
from rag_hub.html_acquire import encode
from rag_hub.html_handoff import load_units
from rag_hub.html_qa_execution import assess_document
from rag_hub.html_qualification import evaluate, verify_release
from rag_hub.html_validation import load_documents

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "workspace/html-qa-closure/v1"


def test_complete_prose_and_lead_in_list_remain_one_scope():
    doc = example(
        "<h1>Owned</h1><p>The workflow has two steps:</p><ol><li>Load.</li><li>Validate.</li></ol>"
    )
    value = evaluate(doc)
    assert len(value["units"]) == 1
    unit = value["units"][0]
    assert len(unit["required_section_ids"]) == 3
    assert len(unit["content_section_ids"]) == 2
    assert unit["members"][-1]["source_tree"]["tag"] == "ol"
    assert unit["consumption"] == "complete_unit_only"


def test_incomplete_lead_in_cannot_pass_alone():
    value = evaluate(example("<h1>Owned</h1><p>The following instructions are:</p>"))
    assert not value["units"]
    assert (
        "incomplete_lead_in_without_verified_following_content" in value["sections"][1]["reasons"]
    )


@pytest.mark.parametrize(
    "body",
    [
        '<h1>Owned</h1><p>Read the following diagram:</p><img src="x.png">',
        "<h1>Owned</h1><div hidden><p>Hidden words.</p></div>",
        '<h1>Owned</h1><div role="tabpanel"><p>Alternative words.</p></div>',
        "<h1>Owned</h1><table><tr><td>2</td></tr></table>",
        "<h1>Owned</h1><p>Precision<sub>Ω</sub>.</p>",
        "<h1>Owned</h1><p>The score is 1/(rank + k).</p>",
        '<h1>Owned</h1><figure><img src="x.png"><figcaption>Diagram.</figcaption></figure>',
    ],
)
def test_unsupported_and_context_hazards_cannot_be_admitted(body):
    assert not evaluate(example(body))["units"]


def test_hidden_title_prevents_dependent_prose_admission():
    v = evaluate(example('<h1 style="visibility:hidden">Owned</h1><p>Ordinary complete words.</p>'))
    assert not v["units"]
    assert v["sections"][1]["reasons"] == ["heading_dependency_not_qualified"]


def test_decorative_heading_anchor_does_not_block_genuine_text():
    v = evaluate(
        example(
            '<h1>Owned<a aria-label="Navigate to header"><svg></svg></a></h1><p>Ordinary complete words.</p>'
        )
    )
    assert len(v["units"]) == 1


@pytest.mark.parametrize("mutation", ["text", "duplicate", "locator", "heading", "raw", "missing"])
def test_corrupt_source_claims_fail_closed(mutation):
    doc = example()
    record, row = target(doc)
    if mutation == "text":
        record["block"]["content"] = row["section"]["text"] = "Altered words."
        record["block"]["content_sha256"] = digest(b"Altered words.")
        row["section"]["normalized_sha256"] = digest(b"Altered words.")
    elif mutation == "duplicate":
        doc["parsed"]["records"].append(copy.deepcopy(record))
        doc["normalized"]["records"].append(copy.deepcopy(row))
    elif mutation == "locator":
        row["dom_path"] = record["dom_path"] = "/invalid"
    elif mutation == "heading":
        row["section"]["heading_path"] = record["block"]["heading_path"] = ["Wrong"]
    elif mutation == "raw":
        doc["raw"] += b" "
    elif mutation == "missing":
        record["source_tree"]["children"].clear()
        row["source_tree"] = copy.deepcopy(record["source_tree"])
    value = evaluate(doc)
    assert not value["units"]
    assert any(r["disposition"] == "Confirmed parsing defect" for r in value["sections"])


def test_c11_unicode_character_and_byte_offsets_are_explicit():
    if not (ROOT / "data/manifests/html/corpus-manifest.json").exists():
        pytest.skip("private corpus unavailable")
    doc = load_documents(ROOT)["C11"]
    value = evaluate(doc)
    assert len(value["sections"]) == 26
    bindings = [r["source_location"] for r in value["sections"]]
    assert any(r["raw_character_span"] != r["raw_byte_span"] for r in bindings)
    raw = doc["raw"]
    text = raw.decode("utf-8")
    for r in bindings:
        a, b = r["raw_character_span"]
        c, d = r["raw_byte_span"]
        assert text[a:b].encode() == raw[c:d]
        assert digest(raw[c:d]) == r["raw_fragment_sha256"]


@pytest.fixture(scope="module")
def selection():
    path = ROOT / "config/html-admission-publication.json"
    if not path.exists():
        pytest.skip("private authorized publication not executed")
    return json.loads(path.read_bytes())


def test_entire_corpus_authoritative_publication_and_complete_units(selection):
    units = load_units(ROOT, **selection)
    assert units
    admitted = {s for u in units for s in u["required_section_ids"]}
    assert len(admitted) > 12
    for doc in load_documents(ROOT).values():
        record = assess_document(ROOT, doc, None)
        assert all(d["status"] == "hold" for d in record["quality_decisions"])
    assert all(u["whole_source_ready"] is False for u in units)
    assert all(u["text_sha256"] == digest(u["text"].encode()) for u in units)


def test_c05_and_c16_context_is_not_partial(selection):
    units = load_units(ROOT, **selection)
    for doc, suffix in [("C05", "h00011"), ("C16", "h00002")]:
        unit = next(
            u
            for u in units
            if u["doc_id"] == doc
            and any(s.split(":")[2] == suffix for s in u["content_section_ids"])
        )
        assert any(
            m["classification"] in {"unordered_list", "ordered_list"} for m in unit["members"]
        )
        assert unit["heading_context"]
    code_unit = next(
        u
        for u in units
        if u["doc_id"] == "C05"
        and any(s.split(":")[2] == "h00016" for s in u["content_section_ids"])
    )
    assert code_unit["required_parent_context"]


@pytest.mark.parametrize(
    "field", ["expected_manifest_sha256", "expected_release_sha256", "authorization_sha256"]
)
def test_stale_external_bindings_rejected(selection, field):
    args = dict(selection, **{field: "0" * 64})
    with pytest.raises(ValueError):
        load_units(ROOT, **args)


@pytest.mark.parametrize("change", ["partial", "neighbor", "text", "locator", "scope"])
def test_publication_rewrite_rejected_even_if_outer_hash_recomputed(
    selection, tmp_path, monkeypatch, change
):
    import rag_hub.html_handoff as module

    manifest = json.loads((ROOT / selection["manifest_path"]).read_bytes())
    path = manifest["publications"][0]["path"]
    publication = json.loads((ROOT / path).read_bytes())
    qa = publication["qa"]
    if change == "partial":
        qa["quality_decisions"].pop()
    elif change == "neighbor":
        hold = next(d for d in qa["quality_decisions"] if d["status"] == "hold")
        hold["status"] = "approved_for_index"
    elif change == "text":
        qa["scoped_html_support"]["units"][0]["text"] += "Neighbor."
    elif change == "locator":
        qa["scoped_html_support"]["units"][0]["members"][0]["dom_path"] = "/fake"
    elif change == "scope":
        qa["scoped_html_support"]["units"][0]["required_section_ids"].pop()
    fake = tmp_path / "publication.json"
    fake.write_bytes(encode(publication))
    manifest["publications"][0]["sha256"] = digest(fake.read_bytes())
    mf = tmp_path / "manifest.json"
    mf.write_bytes(encode(manifest))
    original = module.local_path
    monkeypatch.setattr(
        module,
        "local_path",
        lambda root, p: (
            fake
            if str(p) == path
            else mf
            if str(p) == selection["manifest_path"]
            else original(root, p)
        ),
    )
    args = dict(selection, expected_manifest_sha256=digest(mf.read_bytes()))
    with pytest.raises(ValueError, match="partial_forged_or_neighboring"):
        load_units(ROOT, **args)


def test_release_old_identity_unchanged_and_no_default_auto_admission(selection):
    assert (
        digest((ROOT / "config/combined-qa-successor.json").read_bytes())
        == "3bf5e69bc3ec1b152b7a03307ba305f6ad8adeff15aef3d3d36b167ea655d5ec"
    )
    verify_release(ROOT, selection["release_path"], selection["expected_release_sha256"])


def test_existing_pdf_and_c04_scopes_survive():
    from rag_hub.markdown_corpus import load_corpus as md
    from rag_hub.pdf_prose_handoff import load_passages

    paths = list(
        (ROOT / "data/validation/pdf/scoped-prose-admission-v1/publications").glob("*/handoff.json")
    )
    if not paths:
        pytest.skip("private publications unavailable")
    handoff = json.loads(paths[0].read_bytes())
    passages = load_passages(
        ROOT,
        handoff["publications"],
        release_path=handoff["release_path"],
        expected_release_sha256=handoff["expected_release_sha256"],
    )
    assert len(passages) == 8
    assert len({s for p in passages for s in p["required_section_ids"]}) == 19
    assert len(md(ROOT)["records"]) == 40


def test_heading_level_gap_is_source_projection_not_invented_level():
    v = evaluate(example("<h1>Owned</h1><h3>Source subsection</h3><p>Complete text.</p>"))
    assert len(v["units"]) == 1
    assert v["units"][0]["heading_path"] == ["Owned", "Source subsection"]
    assert [m["source_tree"]["tag"] for m in v["units"][0]["heading_context"]] == ["h1", "h3"]


def test_code_exact_whitespace_and_identifiers_preserved_with_context():
    v = evaluate(
        example(
            '<h1>Owned</h1><p>The complete example follows.</p><pre><code class="language-python">x = -1.25\nif x &lt; 2:\n    print("all-MiniLM-L6-v2")\n</code></pre>'
        )
    )
    assert len(v["units"]) == 1
    assert '    print("all-MiniLM-L6-v2")' in v["units"][0]["text"]
    assert "-1.25" in v["units"][0]["text"]


def test_live_source_cannot_opt_in_itself():
    doc = example("<h1>Owned</h1><p>Complete ordinary text.</p>")
    doc["entry"] = {"paths": {}}
    baseline = assess_document(ROOT, doc, None)
    assert all(r["status"] == "hold" for r in baseline["quality_decisions"])
    with pytest.raises((ValueError, KeyError, FileNotFoundError)):
        assess_document(
            ROOT,
            doc,
            {
                "release_path": "config/html-auto-qa-successor.json",
                "expected_release_sha256": "0" * 64,
                "authorization_path": "source-text",
                "authorization_sha256": "0" * 64,
            },
        )
