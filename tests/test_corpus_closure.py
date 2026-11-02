"""Bounded offline metadata/MDX persistence controls; no third-party fixture text."""

import json
from pathlib import Path

import pytest

from rag_hub.acquire import digest
from rag_hub.html_acquire import encode, immutable
from rag_hub.html_corpus import source_from_receipt
from rag_hub.markdown_corpus import MANIFEST, QA_RUN, load_corpus, structure
from rag_hub.parse_markdown import parse_markdown
from rag_hub.schemas import Section, SourceManifest

ROOT = Path(__file__).resolve().parents[1]


def owned_source(raw):
    return SourceManifest(
        doc_id="C04",
        snapshot_id="owned-snapshot",
        title="Owned",
        publisher="Owned",
        canonical_url="https://example.org/owned",
        source_format="markdown_mdx",
        raw_path=Path("data/raw/owned.md"),
        raw_sha256=digest(raw),
        rights_status="local_use_approved",
    )


def test_publisher_metadata_comes_from_corrected_spec_without_source_mutation():
    receipt = {
        "raw_sha256": "a" * 64,
        "final_url": "https://docs.pinecone.io/guides/assistant/overview",
        "retrieved_at": "2026-10-21T12:00:00Z",
        "byte_size": 123,
    }
    spec = {
        "doc_id": "C13",
        "publisher": "Pinecone",
        "title": "Pinecone Assistant Overview",
        "canonical_url": receipt["final_url"],
        "source_version": None,
    }
    source = source_from_receipt(spec, receipt)
    assert source.publisher == "Pinecone"
    assert source.raw_sha256 == receipt["raw_sha256"]
    assert str(source.canonical_url) == spec["canonical_url"]


def test_syntax_retains_list_quote_inline_and_mdx_boundaries_without_execution():
    raw = (
        b"# Owned\n\nA `value` and [link](/ref).\n\n"
        b"* First\n  * Child\n\n> Quoted.\n\n"
        b'<Tabs>\n<Tab title="Provider">\n```python\n'
        b'raise RuntimeError("do not execute")\n```\n</Tab>\n</Tabs>\n'
        b"<Dynamic run={dangerous()} />\n"
    )
    result = structure(raw, parse_markdown(raw, owned_source(raw)))
    assert len(result["mdx_containers"]) == 2
    assert result["mdx_containers"][1]["label"] == "Provider"
    assert result["unsupported_regions"]
    types = {t["type"] for t in result["markdown_syntax"]}
    children = {c["type"] for t in result["markdown_syntax"] for c in t["children"]}
    assert {"bullet_list_open", "list_item_open", "blockquote_open"} <= types
    assert {"code_inline", "link_open"} <= children
    assert not result["unaccounted_nonblank_source_lines"]


def test_utf8_offsets_reconstruct_raw_fences_and_original_glyphs():
    raw = '# Café\n\n<Tabs>\n<Tab title="Ω">\n  ```python theme={x}\n  x = "é"\n  ```\n</Tab>\n</Tabs>\n'.encode()
    result = structure(raw, parse_markdown(raw, owned_source(raw)))
    for record in result["records"]:
        span = record["source_span"]
        a, b = span["bytes_0based_end_exclusive"]
        c, d = span["chars_0based_end_exclusive"]
        assert raw[a:b].decode() == raw.decode()[c:d]
        assert digest(raw[a:b]) == span["raw_fragment_sha256"]
    code = next(r for r in result["records"] if r["block"]["block_type"] == "code")
    assert code["block"]["content"] == 'x = "é"\n'


def stored_example(root):
    raw = b"# Owned\n"
    source = owned_source(raw).model_dump(mode="json")
    section = Section(
        section_id="owned-section",
        doc_id="C04",
        snapshot_id=source["snapshot_id"],
        heading_path=("Owned",),
        block_ids=("C04:b00000",),
        text="# Owned\n",
        locators=({"url": source["canonical_url"], "line_start": 1, "line_end": 1},),
        raw_sha256=digest(raw),
        normalized_sha256=digest(raw),
        block_type="heading",
    )
    decision = {
        "section_id": section.section_id,
        "doc_id": "C04",
        "status": "hold",
        "raw_sha256": digest(raw),
        "normalized_sha256": digest(raw),
    }
    payloads = {
        "data/raw/owned.md": raw,
        "data/parsed/markdown/C04.json": encode({"source": source}),
        "data/normalized/markdown/C04.json": encode(
            {
                "source": source,
                "records": [
                    {"section": section.model_dump(mode="json"), "historical_qa_decision": decision}
                ],
            }
        ),
        f"data/validation/{QA_RUN}/approved_manifest.json": encode({"approved": []}),
        f"data/validation/{QA_RUN}/decisions.jsonl": encode(decision).replace(b"\n", b"") + b"\n",
    }
    for name, data in payloads.items():
        immutable(root / name, data)
    manifest = {
        "schema": "markdown-corpus-1.0",
        "documents": ["C04"],
        "source": source,
        "historical_qa_run": QA_RUN,
        "implementation": {},
        "artifacts": {name: digest(data) for name, data in payloads.items()},
    }
    manifest["identity_sha256"] = digest(encode(manifest))
    immutable(root / MANIFEST, encode(manifest))


def test_offline_loader_excludes_hold_and_rejects_raw_tampering(tmp_path):
    stored_example(tmp_path)
    assert load_corpus(tmp_path)["records"] == []
    assert len(load_corpus(tmp_path, admitted_only=False)["records"]) == 1
    (tmp_path / "data/raw/owned.md").write_bytes(b"changed")
    with pytest.raises(ValueError, match="artifact_integrity"):
        load_corpus(tmp_path)


def test_manifest_tampering_fails_before_loading(tmp_path):
    stored_example(tmp_path)
    manifest = json.loads((tmp_path / MANIFEST).read_bytes())
    manifest["historical_qa_run"] = "foreign"
    (tmp_path / MANIFEST).write_bytes(encode(manifest))
    with pytest.raises(ValueError, match="manifest_integrity"):
        load_corpus(tmp_path)


@pytest.mark.skipif(not (ROOT / MANIFEST).exists(), reason="private C04 store not provided")
def test_actual_store_reuses_exact_historical_records_and_decisions_offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("offline loading must not parse or acquire")

    monkeypatch.setattr("rag_hub.markdown_corpus.parse_markdown", forbidden)
    all_rows = load_corpus(ROOT, admitted_only=False)
    admitted = load_corpus(ROOT)["records"]
    assert len(all_rows["records"]) == 158
    assert len(admitted) == 40
    assert all(r["section"].block_type == "code" for r in admitted)
    assert (
        sum(r["historical_qa_decision"]["basis"] == "original_manual_receipt" for r in admitted)
        == 2
    )
    run = json.loads((ROOT / "config/validation-policy.json").read_bytes())["input_run_id"]
    original = {
        s["section_id"]: s
        for s in map(
            json.loads, (ROOT / f"data/ingestion/{run}/sections.jsonl").read_text().splitlines()
        )
        if s["doc_id"] == "C04"
    }
    assert {
        r["section"].section_id: r["section"].model_dump(mode="json") for r in all_rows["records"]
    } == original


@pytest.mark.skipif(
    not (ROOT / "data/raw/html/C13.html").exists(), reason="private HTML not provided"
)
def test_actual_html_metadata_and_offline_closure(monkeypatch):
    from rag_hub import html_corpus

    def forbidden(*args, **kwargs):
        raise AssertionError("offline loading must not parse or acquire")

    monkeypatch.setattr(html_corpus, "parse_html", forbidden)
    rows = html_corpus.load_corpus(ROOT, admitted_only=False)
    manifest = json.loads((ROOT / html_corpus.MANIFEST).read_bytes())
    assert len(rows) == 457
    assert len(manifest["sources"]) == 11
    entry = next(s for s in manifest["sources"] if s["doc_id"] == "C13")
    assert entry["publisher"] == "Pinecone"
    source = json.loads((ROOT / entry["paths"]["source"]["path"]).read_bytes())
    assert source["publisher"] == "Pinecone"
    assert html_corpus.load_corpus(ROOT) == []
