"""Bounded context correction controls. Synthetic cases are not human reviews."""

import copy
import json
from pathlib import Path

import pytest
from test_html_validation import example

from rag_hub.acquire import digest
from rag_hub.html_acquire import encode
from rag_hub.html_context_remediation import evaluate as remediate
from rag_hub.html_context_remediation import inline_api_proof, safe_row
from rag_hub.html_handoff import load_units
from rag_hub.html_qa_execution import assess_document
from rag_hub.html_qualification import binding, evaluate
from rag_hub.html_validation import SourceIndex, load_documents

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "workspace/html-qa-remediation/v1"


def overlay_fixture(body, *, projected=False):
    doc = example(body)
    rows = doc["normalized"]["records"]
    content = [r for r in rows if r["classification"] != "heading"]
    headings = [r for r in rows if r["classification"] == "heading"]
    context = [] if projected else headings
    selected = context + content
    spec = {
        "doc_id": "OWNED",
        "content_section_ids": [r["section"]["section_id"] for r in content],
        "required_context_section_ids": [r["section"]["section_id"] for r in context],
        "projected_title_ids": [r["section"]["section_id"] for r in headings] if projected else [],
        "gap_section_ids": [],
        "inline_api_section_ids": [],
        "source_bindings": [binding(r, doc) for r in selected],
        "context_resolution": "Synthetic source-supported complete unit; not owner evidence.",
    }
    overlay = {
        "source_hashes": {"OWNED": doc["source"].raw_sha256},
        "retained_units": {"OWNED": []},
        "unsupported_section_ids": spec["projected_title_ids"],
        "units": [spec],
        "hold_reasons": {},
    }
    return doc, overlay


def test_complete_static_note_keeps_label_and_body_together():
    doc, overlay = overlay_fixture(
        '<h1>Owned</h1><div role="note"><p>Note</p><p>Complete owned advice.</p></div>'
    )
    v = remediate(doc, evaluate(doc), overlay)
    assert len(v["units"]) == 1
    assert v["units"][0]["text"] == "Note\n\nComplete owned advice."
    assert v["units"][0]["relationship_evidence"][0]["kind"] == "static_note_ownership"


def test_partial_static_note_cannot_drop_its_label():
    doc, overlay = overlay_fixture(
        '<h1>Owned</h1><div role="note"><p>Note</p><p>Complete owned advice.</p></div>'
    )
    spec = overlay["units"][0]
    spec["content_section_ids"].pop(0)
    spec["source_bindings"].pop(1)
    with pytest.raises(ValueError, match="incomplete_static_container"):
        remediate(doc, evaluate(doc), overlay)


@pytest.mark.parametrize(
    "body",
    [
        '<h1>Owned</h1><div role="tabpanel"><p>Alternative words.</p></div>',
        "<h1>Owned</h1><div hidden><p>Hidden words.</p></div>",
        "<h1>Owned</h1><p>Uncertain <math><mi>x</mi></math>.</p>",
        "<h1>Owned</h1><p>Value<sub>i</sub> is not plain prose.</p>",
        "<h1>Owned</h1><p>Look at <svg><text>Unverified graph</text></svg>.</p>",
        '<h1>Owned</h1><p>Look at <svg><path d="M0 0"/></svg>.</p>',
        "<h1>Owned</h1><table><tr><td>4</td></tr></table>",
        "<h1>Owned</h1><p>The score is 1/(rank + k).</p>",
        "<h1>Owned</h1><pre><code>\\frac{x}{y}</code></pre>",
    ],
)
def test_specialized_or_dynamic_content_still_rejected(body):
    doc, overlay = overlay_fixture(body)
    with pytest.raises(ValueError):
        remediate(doc, evaluate(doc), overlay)


@pytest.mark.parametrize(
    ("payload", "allowed"),
    [
        ("Created with <code>pc.create_index(dimension=..., metric=...)</code>.", True),
        ("Use <code>$match_all</code> with <code>$match_any</code>.", True),
        ("The equation is <code>x=2</code>.", False),
        ("The formula is <code>$x+y$</code>.", False),
        ("Use <code>pc.create_index(dimension=...)</code>, then x=2.", False),
        ("The score is 1/(rank + k).", False),
    ],
)
def test_math_false_positive_resolution_is_limited_to_typed_api_syntax(payload, allowed):
    doc = example("<h1>Owned</h1><p>" + payload + "</p>")
    row = doc["normalized"]["records"][1]
    index = SourceIndex(doc["raw"].decode())
    if allowed:
        proof = inline_api_proof(row, index)
        assert proof["kind"] == "inline_code_not_mathematics"
    else:
        with pytest.raises(ValueError):
            inline_api_proof(row, index)


@pytest.mark.parametrize("mutation", ["text", "offset", "heading", "order", "duplicate", "gap"])
def test_overlay_binding_and_membership_mutations_fail_closed(mutation):
    doc, overlay = overlay_fixture("<h1>Owned</h1><p>First.</p><p>Second.</p>")
    s = overlay["units"][0]
    if mutation == "text":
        s["source_bindings"][1]["text"] = "Changed."
    elif mutation == "offset":
        s["source_bindings"][1]["raw_character_span"][0] += 1
    elif mutation == "heading":
        s["required_context_section_ids"].clear()
        s["source_bindings"].pop(0)
    elif mutation == "order":
        s["content_section_ids"].reverse()
    elif mutation == "duplicate":
        s["content_section_ids"].append(s["content_section_ids"][0])
    elif mutation == "gap":
        s["gap_section_ids"].append(s["content_section_ids"][0])
    with pytest.raises(ValueError):
        remediate(doc, evaluate(doc), overlay)


def test_real_source_failure_cannot_be_waived_by_overlay():
    doc, overlay = overlay_fixture("<h1>Owned</h1><p>Complete owned words.</p>")
    baseline = evaluate(doc)
    baseline["sections"][1]["checks"]["checks"]["raw_source_span"]["outcome"] = "FAIL"
    with pytest.raises(ValueError, match="cannot_override_failed_source_check"):
        remediate(doc, baseline, overlay)


def test_non_decorative_icon_must_not_be_waived():
    doc = example('<h1>Owned</h1><p>Words.<svg class="gb-icon size-3"><text>9.2</text></svg></p>')
    with pytest.raises(ValueError, match="non_decorative_visual"):
        safe_row(doc["normalized"]["records"][1], SourceIndex(doc["raw"].decode()))


@pytest.fixture(scope="module")
def corpus_candidate():
    if not (ROOT / "data/manifests/html/corpus-manifest.json").exists():
        pytest.skip("private frozen corpus unavailable")
    path = "workspace/html-qa-remediation/v1/AUTHORIZATION.json"
    if not (ROOT / path).exists():
        pytest.skip("explicit private execution authorization unavailable")
    admission = {
        "release_path": "config/html-context-qa-successor.json",
        "expected_release_sha256": digest(
            (ROOT / "config/html-context-qa-successor.json").read_bytes()
        ),
        "authorization_path": path,
        "authorization_sha256": digest((ROOT / path).read_bytes()),
    }
    return {d: assess_document(ROOT, v, admission) for d, v in load_documents(ROOT).items()}


def test_all_140_targets_and_78_unsupported_have_exact_dispositions(corpus_candidate):
    targets = json.loads((WORK / "TARGETS_FROZEN.json").read_bytes())
    facts = {
        f["section_id"]: f
        for q in corpus_candidate.values()
        for f in q["scoped_html_support"]["sections"]
    }
    decisions = {
        f["section_id"]: f for q in corpus_candidate.values() for f in q["quality_decisions"]
    }
    assert len(facts) == len(decisions) == 457
    assert len(targets["target_section_ids"]) == 140
    new = [
        s for s in targets["target_section_ids"] if decisions[s]["status"] == "approved_for_index"
    ]
    assert len(new) == 102
    for s in targets["unsupported_section_ids"]:
        assert facts[s]["disposition"] == "Unsupported content"
        assert decisions[s]["status"] == "hold"
    for s in targets["target_section_ids"]:
        if decisions[s]["status"] == "hold":
            assert facts[s]["disposition"] and facts[s]["reasons"]
        else:
            assert facts[s]["disposition"] is None


def test_c09_projection_does_not_approve_hidden_title_or_graphs(corpus_candidate):
    q = corpus_candidate["C09"]
    assert sum(d["status"] == "approved_for_index" for d in q["quality_decisions"]) == 55
    title = next(d for d in q["quality_decisions"] if ":h00000:" in d["section_id"])
    assert title["status"] == "hold"
    for unit in q["scoped_html_support"]["units"]:
        projection = unit["source_context_projections"][0]
        assert projection["source_visibility"] == "hidden_in_capture"
        assert projection["visibility_claim"] is False
        assert title["section_id"] not in unit["required_section_ids"]
        assert "source" in unit and unit["source"]["raw_sha256"]


def test_both_evidence_gaps_and_all_10_restrictions_are_qualified(corpus_candidate):
    exceptions = json.loads(
        (ROOT / "data/validation/html/scoped-admission-v1/EXCEPTIONS.json").read_bytes()
    )
    targeted = [
        f
        for f in exceptions
        if f["disposition"] in {"Evidence gap", "Other explicit QA restriction"}
    ]
    assert len(targeted) == 12
    decisions = {
        f["section_id"]: f for q in corpus_candidate.values() for f in q["quality_decisions"]
    }
    assert all(decisions[f["section_id"]]["status"] == "approved_for_index" for f in targeted)
    gap_units = [
        u
        for q in corpus_candidate.values()
        for u in q["scoped_html_support"]["units"]
        if any(
            s in u["content_section_ids"]
            for s in [f["section_id"] for f in targeted if f["disposition"] == "Evidence gap"]
        )
    ]
    assert len(gap_units) == 2
    sparse = next(u for u in gap_units if u["doc_id"] == "C08")
    source_list = next(
        m["source_tree"] for m in sparse["members"] if m["classification"] == "unordered_list"
    )
    items = [c for c in source_list["children"] if c.get("tag") == "li"]
    assert len(items) == 5
    assert "10,000" in json.dumps(items[3])
    assert "dotproduct" in json.dumps(items[3])
    assert "4 MB" in json.dumps(items[4])
    n8n = next(u for u in gap_units if u["doc_id"] == "C12")
    assert "https://www.anthropic.com/news/contextual-retrieval" in json.dumps(n8n["members"])


def test_previous_74_scopes_and_239_admissions_remain_exact(corpus_candidate):
    previous = json.loads((ROOT / "config/html-admission-publication.json").read_bytes())
    units = load_units(ROOT, **previous)
    assert len(units) == 74
    ids = {s for u in units for s in u["required_section_ids"]}
    assert len(ids) == 239
    new_units = {
        u["id"]: u for q in corpus_candidate.values() for u in q["scoped_html_support"]["units"]
    }
    for unit in units:
        old = {
            k: v
            for k, v in unit.items()
            if k
            not in {
                "authoritative_publication",
                "qa_release_sha256",
                "qualification_policy_sha256",
                "authorization_sha256",
                "whole_source_ready",
            }
        }
        assert new_units[unit["id"]] == old


@pytest.fixture(scope="module")
def selection():
    p = ROOT / "config/html-remediated-admission-publication.json"
    if not p.exists():
        pytest.skip("new immutable publication not yet selected")
    return json.loads(p.read_bytes())


def test_verified_remediated_handoff(selection):
    units = load_units(ROOT, **selection)
    assert len(units) == 108
    assert len({s for u in units for s in u["required_section_ids"]}) == 341
    assert all(u["whole_source_ready"] is False for u in units)


@pytest.mark.parametrize("mutation", ["partial", "neighbor", "projection", "context", "text"])
def test_remediated_publication_forgery_rejected(selection, tmp_path, monkeypatch, mutation):
    import rag_hub.html_handoff as module

    manifest = json.loads((ROOT / selection["manifest_path"]).read_bytes())
    descriptor = next(x for x in manifest["publications"] if x["path"].endswith("/C09.json"))
    original_path = descriptor["path"]
    pub = json.loads((ROOT / original_path).read_bytes())
    q = pub["qa"]
    unit = q["scoped_html_support"]["units"][0]
    if mutation == "partial":
        unit["required_section_ids"].pop()
    elif mutation == "neighbor":
        next(d for d in q["quality_decisions"] if d["status"] == "hold")["status"] = (
            "approved_for_index"
        )
    elif mutation == "projection":
        unit["source_context_projections"][0]["visibility_claim"] = True
    elif mutation == "context":
        unit["context_section_ids"].append("foreign-section")
    elif mutation == "text":
        unit["text"] += " Unauthorized neighboring words."
    fake = tmp_path / "pub.json"
    fake.write_bytes(encode(pub))
    descriptor["sha256"] = digest(fake.read_bytes())
    mf = tmp_path / "manifest.json"
    mf.write_bytes(encode(manifest))
    original = module.local_path
    monkeypatch.setattr(
        module,
        "local_path",
        lambda root, p: (
            fake
            if str(p) == original_path
            else mf
            if str(p) == selection["manifest_path"]
            else original(root, p)
        ),
    )
    with pytest.raises(ValueError, match="partial_forged_or_neighboring"):
        load_units(ROOT, **dict(selection, expected_manifest_sha256=digest(mf.read_bytes())))


def test_overlay_wrong_snapshot_and_retained_hash_rejected():
    doc, overlay = overlay_fixture("<h1>Owned</h1><p>Complete.</p>")
    wrong = copy.deepcopy(overlay)
    wrong["source_hashes"]["OWNED"] = "0" * 64
    with pytest.raises(ValueError, match="source_snapshot_mismatch"):
        remediate(doc, evaluate(doc), wrong)
    wrong = copy.deepcopy(overlay)
    wrong["retained_units"]["OWNED"] = [{"id": "forged", "unit_sha256": "0" * 64}]
    with pytest.raises(ValueError, match="prior_unit_changed"):
        remediate(doc, evaluate(doc), wrong)


def test_title_projection_is_metadata_not_visible_or_eligible_content():
    doc, overlay = overlay_fixture(
        '<article><header style="visibility:hidden"><h1>Owned</h1></header>'
        '<div data-article-body="true"><p>Visible complete source prose.</p></div></article>',
        projected=True,
    )
    v = remediate(doc, evaluate(doc), overlay)
    unit = v["units"][0]
    projection = unit["source_context_projections"][0]
    assert projection["visibility_claim"] is False
    assert projection["binding"]["section_id"] not in unit["required_section_ids"]
    assert projection["role"] == "context_metadata_only_not_admitted_Section"


@pytest.mark.parametrize("defect", ["two_titles", "wrong_article", "hidden_body"])
def test_ambiguous_or_unrelated_title_projection_is_rejected(defect):
    title = '<header style="visibility:hidden"><h1>Owned</h1></header>'
    prose = '<div data-article-body="true"><p>Visible complete source prose.</p></div>'
    if defect == "two_titles":
        body = "<article>" + title + "<h1>Other</h1>" + prose + "</article>"
    elif defect == "wrong_article":
        body = "<article>" + title + "</article><article>" + prose + "</article>"
    else:
        body = "<article>" + title + "<div hidden>" + prose + "</div></article>"
    doc, overlay = overlay_fixture(body, projected=True)
    with pytest.raises(ValueError):
        remediate(doc, evaluate(doc), overlay)
