"""Owned semantic HTML controls; no live web access or publisher fixture copies."""

import json
from pathlib import Path
from urllib.request import Request

import pytest

from rag_hub.acquire import digest
from rag_hub.html_acquire import Redirects, encode, immutable
from rag_hub.html_corpus import load_corpus, normalize, validation
from rag_hub.parse_html import parse_html
from rag_hub.schemas import Section, SourceManifest


def example(body, *, wrapper="main"):
    raw = f"<html><head><title>Owned source</title></head><body><nav>Noise</nav><{wrapper}>{body}</{wrapper}><footer>noise</footer></body></html>".encode()
    source = SourceManifest(
        doc_id="OWNED",
        snapshot_id="sha256-" + digest(raw),
        canonical_url="https://example.org/docs/page",
        title="Owned",
        publisher="Owned",
        source_format="html",
        raw_path=Path("data/raw/html/OWNED.html"),
        raw_sha256=digest(raw),
        rights_status="local_use_approved",
    )
    return raw, source, parse_html(raw, source)


def test_span_paragraph_boundaries_and_inline_links():
    raw, source, parsed = example(
        '<h1>Title</h1><span data-as="p">One <code>x = 2</code> &amp; <a href="../ref#x">ref</a>.</span><span data-as="p">Two.</span>'
    )
    assert [r["block"]["content"] for r in parsed["records"]] == [
        "Title",
        "One x = 2 & ref.",
        "Two.",
    ]
    assert [r["classification"] for r in parsed["records"]] == ["heading", "paragraph", "paragraph"]
    tree = parsed["records"][1]["source_tree"]
    assert (
        next(c for c in tree["children"] if c.get("tag") == "a")["attrs"]["resolved_href"]
        == "https://example.org/ref#x"
    )
    assert validation(raw, source, parsed, normalize(parsed), "utf-8")["failures"] == []


def test_code_whitespace_entities_and_fence_collision():
    content = '\nif x &lt; 2:\n    print("```")\n'
    raw, source, parsed = example(
        '<h1>Title</h1><p>Before</p><pre><code class="language-python">' + content + "</code></pre>"
    )
    code = parsed["records"][-1]["block"]
    assert code["content"] == '\nif x < 2:\n    print("```")\n'
    normalized = normalize(parsed)
    assert normalized["records"][-1]["section"]["text"].startswith("~~~~python\n\nif x < 2:")
    assert not validation(raw, source, parsed, normalized, "utf-8")["failures"]


def test_nested_lists_table_cells_and_spans_stay_structured():
    raw, source, parsed = example(
        '<h1>T</h1><ol start="3"><li>Alpha<ul><li>Beta</li></ul></li><li>Gamma</li></ol><table><thead><tr><th scope="col">Name</th><th colspan="2">Value</th></tr></thead><tbody><tr><td>A</td><td>1</td><td>2</td></tr></tbody></table>'
    )
    assert [r["classification"] for r in parsed["records"]] == ["heading", "ordered_list", "table"]
    assert parsed["records"][1]["source_tree"]["attrs"]["start"] == "3"
    report = validation(raw, source, parsed, normalize(parsed), "utf-8")
    assert report["checks"]["table_cell_source_span:pass"] == 5
    assert report["checks"]["list_nesting_source_span:pass"] == 5
    assert not report["failures"]


def test_tabs_restore_heading_scope_and_hidden_is_hold():
    _, _, parsed = example(
        '<h1>Document</h1><h2>Shared</h2><div role="tabpanel" hidden><h3>Alternative</h3><p>Hidden body.</p></div><p>Shared body.</p>'
    )
    assert parsed["records"][-1]["block"]["heading_path"] == ["Document", "Shared"]
    hidden_record = parsed["records"][-2]
    assert "hidden_or_alternative_content_unverified" in hidden_record["block"]["issues"]
    assert hidden_record["contexts"]
    assert all(r["section"]["index_status"] == "hold" for r in normalize(parsed)["records"])


def test_furniture_removal_is_dom_scoped_not_text_rewrite():
    _, _, parsed = example(
        '<h1>T<a aria-label="Navigate to header" href="#T">\u200b</a></h1><div id="in-article-cta">Ad</div><p>Actual words.</p><div class="source-links"><p>Editing controls</p></div>'
    )
    assert [r["block"]["content"] for r in parsed["records"]] == ["T", "Actual words."]
    assert len(parsed["exclusions"]) == 2
    assert not parsed["accounting"]["unassigned_body_text"]


def test_unknown_image_caption_math_and_script_are_never_eligible():
    _, _, parsed = example(
        '<h1>T</h1><div>untyped text</div><figure><img src="a.png" alt="Diagram"><figcaption>Caption</figcaption></figure><math><mi>x</mi></math><script>raise RuntimeError("execute me")</script>'
    )
    assert {r["classification"] for r in parsed["records"]} == {
        "heading",
        "unknown",
        "figure",
        "equation",
    }
    normalized = normalize(parsed)
    assert len(normalized["records"]) == len(parsed["records"])
    assert all(
        Section.model_validate(r["section"]).index_status == "hold" for r in normalized["records"]
    )
    assert "execute me" not in str(normalized)


def test_duplicate_wording_is_preserved_and_raw_mutation_rejected():
    raw, source, parsed = example("<h1>T</h1><p>Same example.</p><p>Same example.</p>")
    assert len(parsed["records"]) == 3
    assert len({r["block"]["block_id"] for r in parsed["records"]}) == 3
    with pytest.raises(ValueError, match="integrity_mismatch"):
        parse_html(raw + b" ", source)


def test_primary_title_outside_selected_body():
    _, _, parsed = example(
        '<h1>Document</h1><div class="mdx-content"><span data-as="p">Body.</span><h3>Source gap</h3></div>'
    )
    assert parsed["records"][0]["block"]["content"] == "Document"
    assert parsed["records"][1]["block"]["heading_path"] == ["Document"]
    assert "source_heading_level_gap" in parsed["records"][-1]["block"]["issues"]


@pytest.mark.parametrize(
    "target", ["http://example.org/page", "https://unrelated.org/page", "file:///tmp/evil"]
)
def test_acquisition_rejects_unapproved_redirect(target):
    with pytest.raises(ValueError, match="redirect_outside"):
        Redirects("example.org").redirect_request(
            Request("https://example.org"), None, 302, "", {}, target
        )


def test_immutable_publication_rejects_overwrite(tmp_path):
    p = tmp_path / "snapshot"
    immutable(p, b"first")
    immutable(p, b"first")
    with pytest.raises(ValueError, match="immutable_artifact_changed"):
        immutable(p, b"second")
    assert p.read_bytes() == b"first"


def test_offline_loader_rejects_tampering_and_defaults_no_eligible(tmp_path):
    raw, _, parsed = example("<h1>T</h1><p>Paragraph.</p><p>Next.</p>")
    normalized = normalize(parsed)
    p = tmp_path / "data/normalized/html/OWNED.json"
    immutable(p, encode(normalized))
    config = tmp_path / "config/html-sources.json"
    immutable(config, encode({"sources": []}))
    manifest = {
        "implementation": {},
        "config_sha256": digest(config.read_bytes()),
        "sources": [
            {
                "paths": {
                    "normalized": {
                        "path": "data/normalized/html/OWNED.json",
                        "sha256": digest(p.read_bytes()),
                    }
                },
                "normalization": "persisted",
            }
        ],
    }
    manifest["corpus_identity_sha256"] = digest(encode(manifest))
    immutable(tmp_path / "data/manifests/html/corpus-manifest.json", encode(manifest))
    assert load_corpus(tmp_path) == []
    assert len(load_corpus(tmp_path, admitted_only=False)) == 3
    assert load_corpus(tmp_path, admitted_only=False, include_structure=True)[0]["source_tree"]
    p.write_bytes(raw)
    with pytest.raises(ValueError, match="artifact_integrity"):
        load_corpus(tmp_path, admitted_only=False)


def test_parser_is_deterministic():
    raw, source, parsed = example("<h1>T</h1><p>A &amp; B.</p><ul><li>One<li>Two</ul>")
    assert encode(parse_html(raw, source)) == encode(parsed)
    assert encode(normalize(parsed)) == encode(normalize(parse_html(raw, source)))


def test_callout_and_footnote_context_survive_without_prose_rewrite():
    _, _, parsed = example(
        '<h1>T</h1><div class="NOTE"><p>Exact note.</p></div><section role="doc-endnote" id="fn1"><p>Exact footnote.</p></section><details><summary>More</summary><p>Expandable.</p></details>'
    )
    assert {c["classification"] for c in parsed["containers"]} == {
        "callout",
        "footnote_or_citation",
        "expandable",
    }
    for record in parsed["records"][1:]:
        assert record["contexts"]
    assert not parsed["accounting"]["unassigned_body_text"]


def test_tab_labels_survive_control_exclusion_without_inferred_assignment():
    _, _, parsed = example(
        '<h1>T</h1><div role="tablist"><button role="tab">Python</button><button role="tab">TypeScript</button></div><div role="tabpanel"><pre>x = 1</pre></div>'
    )
    assert [c["source_label"] for c in parsed["containers"] if c["classification"] == "tab"] == [
        "Python",
        "TypeScript",
    ]
    assert all(r["block"]["content"] not in ("Python", "TypeScript") for r in parsed["records"])
    assert (
        "unverified"
        in next(c for c in parsed["containers"] if c["classification"] == "tabpanel")[
            "label_to_panel_relationship"
        ]
    )


def test_all_persisted_html_sources_offline_when_available():
    root = Path(__file__).resolve().parents[1]
    manifest = root / "data/manifests/html/corpus-manifest.json"
    if not manifest.exists():
        pytest.skip("private HTML corpus not acquired in this checkout")
    sources = json.loads(manifest.read_text())["sources"]
    assert len(sources) == 11
    assert all(s["validation"] == "PASS" for s in sources)
    assert load_corpus(root) == []
    assert len(load_corpus(root, admitted_only=False)) == sum(s["hold_count"] for s in sources)
