"""Synthetic evidence exercises trust boundaries without publishing source text."""

import json

import pymupdf
import pytest
from pydantic import ValidationError

from rag_hub.acquire import Registry, acquire_sources, digest, local_path, verify_source
from rag_hub.normalize import normalize_blocks
from rag_hub.parse_markdown import parse_markdown
from rag_hub.parse_pdf import parse_pdf
from rag_hub.pipeline import ingest
from rag_hub.quality import apply_reviews
from rag_hub.schemas import Locator, ParsedBlock, ReviewReceipt, Section, SourceManifest


@pytest.fixture
def corpus(tmp_path):
    raw = tmp_path / "data/raw"
    raw.mkdir(parents=True)
    content = b'# Example\n\n<Tabs>\n<Tab title="Provider A">\n    ```python theme={x}\n    # code comment\n    def answer():\n        return 42\n    ```\n</Tab>\n<Tab title="Provider B">\n```python\nvalue = 7\n```\n</Tab>\n</Tabs>\n'
    (raw / "example.md").write_bytes(content)
    spec = {
        "doc_id": "S01",
        "file": "example.md",
        "byte_size": len(content),
        "sha256": digest(content),
        "title": "Synthetic",
        "publisher": "Tests",
        "canonical_url": "https://example.org/docs",
        "original_url": "https://example.org/docs.md",
        "source_version": None,
        "source_format": "markdown_mdx",
        "expected_pages": None,
        "language": "en",
    }
    registry = Registry(schema_version="0.1", sources=[spec])
    (tmp_path / "config").mkdir()
    (tmp_path / "config/sources.json").write_text(registry.model_dump_json())
    source = acquire_sources(tmp_path, registry, "synthetic fixture owned by project")[0]
    return tmp_path, content, registry, source


def test_hash_mismatch_no_new_snapshot(corpus):
    root, _, registry, _ = corpus
    (root / "data/raw/example.md").write_text("changed")
    with pytest.raises(ValueError, match="integrity"):
        verify_source(root, registry.sources[0])


def test_input_set_verified_before_copy(corpus):
    root, _, registry, _ = corpus
    second = registry.sources[0].model_dump() | {"doc_id": "S02", "file": "missing.md"}
    with pytest.raises(FileNotFoundError):
        acquire_sources(root, Registry(schema_version="0.1", sources=[second]), "test")
    assert not (root / "data/snapshots" / "missing.md").exists()


def test_tampered_snapshot_rejected(corpus):
    root, _, registry, source = corpus
    (root / source.snapshot_path).write_text("tampered")
    with pytest.raises(ValueError, match="snapshot was modified"):
        acquire_sources(root, registry, "test")


def test_requires_explicit_use_basis(corpus):
    root, _, registry, _ = corpus
    with pytest.raises(ValueError, match="local-use"):
        acquire_sources(root, registry, " ")


@pytest.mark.parametrize("path", ["../secret", "/tmp/secret", "data/../../secret"])
def test_reject_path_escape(corpus, path):
    with pytest.raises(ValueError):
        local_path(corpus[0], path)


def test_reject_symlinked_input(corpus):
    root, _, registry, _ = corpus
    p = root / "data/raw/example.md"
    p.unlink()
    p.symlink_to(root / "config/sources.json")
    with pytest.raises(ValueError, match="symlink"):
        verify_source(root, registry.sources[0])


def test_code_and_tabs_preserved(corpus):
    _, data, _, source = corpus
    blocks = parse_markdown(data, source)
    code = [b for b in blocks if b.block_type == "code"]
    assert len(code) == 2
    assert code[0].content == "# code comment\ndef answer():\n    return 42\n"
    assert code[0].provider_tab == "Provider A"
    assert code[1].provider_tab == "Provider B"
    assert code[0].heading_path == ("Example",)
    assert code[0].locator.line_start == 5
    assert len([b for b in blocks if b.block_type == "heading"]) == 1
    sections, audit, _ = normalize_blocks(blocks)
    s = next(s for s in sections if s.provider_tab == "Provider A")
    assert code[0].content in s.text
    assert "theme=" not in s.text
    assert audit


def test_wrapper_literals_inside_fence_are_data(corpus):
    data = b'# Example\n```python\nprint("</Tab>")\n```\n'
    blocks = parse_markdown(data, corpus[3])
    assert blocks[1].content == 'print("</Tab>")\n'


def test_unknown_mdx_held(corpus):
    b = parse_markdown(b"<Unknown thing='x'>\ntext\n</Unknown>\n", corpus[3])
    sections, _, _ = normalize_blocks(b)
    assert sections and all(s.index_status == "hold" for s in sections)
    assert any("unsupported_mdx_or_html" in s.issues for s in sections)


@pytest.mark.parametrize("data", [b'<Tab title="A">\ntext\n', b"</Tab>\n"])
def test_malformed_mdx_fails(corpus, data):
    with pytest.raises(ValueError):
        parse_markdown(data, corpus[3])


def test_unclosed_fence_never_approved(corpus):
    blocks = parse_markdown(b"```python\nvalue = 4\n", corpus[3])
    sections, _, _ = normalize_blocks(blocks)
    with pytest.raises(ValueError, match="unsafe"):
        apply_reviews(sections, [receipt(sections[0])])


def receipt(section):
    return ReviewReceipt(
        section_id=section.section_id,
        normalized_sha256=section.normalized_sha256,
        raw_sha256=section.raw_sha256,
        reviewer="synthetic-reviewer",
        evidence_note="Compared exact synthetic source and normalized body",
    )


def test_review_only_exact_section_and_stale_receipts_rejected(corpus):
    blocks = parse_markdown(corpus[1], corpus[3])
    sections, _, _ = normalize_blocks(blocks)
    code = next(s for s in sections if s.block_type == "code")
    reviewed = apply_reviews(sections, [receipt(code)])
    assert sum(s.index_status == "approved_for_index" for s in reviewed) == 1
    stale = receipt(code).model_copy(update={"normalized_sha256": "b" * 64})
    with pytest.raises(ValueError, match="hashes"):
        apply_reviews(sections, [stale])
    with pytest.raises(ValueError, match="duplicate"):
        apply_reviews(sections, [receipt(code), receipt(code)])


def test_unsafe_numeric_content_never_approved(corpus):
    b = ParsedBlock(
        block_id="S01:b1",
        doc_id="S01",
        snapshot_id="test",
        sequence=0,
        block_type="table",
        content="ambiguous values",
        locator=Locator(url="https://example.org", page=1),
        raw_sha256="a" * 64,
        content_sha256=digest(b"ambiguous values"),
        parser_version="test",
        issues=("unverified_table",),
    )
    sections, _, sidecars = normalize_blocks([b])
    assert sidecars[0].verification_status == "hold"
    assert sidecars[0].rows == ()
    with pytest.raises(ValueError, match="unsafe"):
        apply_reviews(sections, [receipt(sections[0])])


def test_schema_rejects_approval_without_review(corpus):
    sections, _, _ = normalize_blocks(parse_markdown(corpus[1], corpus[3]))
    values = sections[0].model_dump() | {"index_status": "approved_for_index"}
    with pytest.raises(ValidationError, match="approval requires"):
        Section.model_validate(values)


def test_deterministic_run_and_reject_artifact_tampering(corpus):
    root, _, _, _ = corpus
    first = ingest(root, use_basis="synthetic test")
    before = {p.name: p.read_bytes() for p in (root / first["output"]).iterdir()}
    second = ingest(root, use_basis="synthetic test")
    assert first == second
    assert before == {p.name: p.read_bytes() for p in (root / second["output"]).iterdir()}
    (root / first["output"] / "report.json").write_text("tampered")
    with pytest.raises(ValueError, match="immutable run"):
        ingest(root, use_basis="synthetic test")


def test_pdf_geometry_and_fail_closed(corpus):
    with pymupdf.open() as pdf:
        p = pdf.new_page()
        p.insert_text((72, 72), "Synthetic heading", fontsize=16)
        p.insert_text((72, 100), "A synthetic paragraph.")
        p.insert_text((72, 140), "x = y + z")
        data = pdf.tobytes()
    source = SourceManifest.model_validate(corpus[3].model_dump() | {"source_format": "pdf"})
    blocks = parse_pdf(data, source, expected_pages=1)
    assert blocks and all(b.locator.page == 1 and b.locator.bbox for b in blocks)
    assert any(b.block_type == "equation" for b in blocks)
    sections, _, sidecars = normalize_blocks(blocks)
    assert all(s.index_status == "hold" for s in sections)
    assert sidecars and all(s.verified_latex_or_null is None for s in sidecars)
    with pytest.raises(ValueError, match="page count"):
        parse_pdf(data, source, expected_pages=2)
    with pytest.raises(pymupdf.FileDataError):
        parse_pdf(b"invalid PDF", source)


def test_unknown_capture_date_and_utc(corpus):
    assert corpus[3].captured_at is None
    values = corpus[3].model_dump() | {"captured_at": "2026-10-18T01:00:00-07:00"}
    assert SourceManifest.model_validate(values).captured_at.hour == 8


def test_source_registry_rejects_traversal_and_duplicates(corpus):
    spec = corpus[2].sources[0].model_dump()
    with pytest.raises(ValidationError):
        Registry(schema_version="0.1", sources=[spec | {"file": "../private"}])
    with pytest.raises(ValidationError, match="duplicate"):
        Registry(schema_version="0.1", sources=[spec, spec])


def test_local_run_never_connects_to_network(corpus, monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        raise AssertionError("ingestion must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    assert ingest(corpus[0], use_basis="synthetic test")["sources"] == 1


def test_only_exact_print_margin_artifact_removed(corpus):
    source = corpus[3]
    contents = [
        ("https://www.trychroma.com/research/evaluating-chunking?utm_source=example\n2/82", 588),
        ("Important content near bottom margin", 588),
    ]
    blocks = [
        ParsedBlock(
            block_id=f"C06:b{i}",
            doc_id="C06",
            snapshot_id=source.snapshot_id,
            sequence=i,
            block_type="prose",
            content=text,
            locator=Locator(url=source.canonical_url, page=2, bbox=(24, y, 700, y + 10)),
            content_sha256=digest(text.encode()),
            raw_sha256=source.raw_sha256,
            parser_version="synthetic",
            issues=("pdf_layout_and_reading_order_unreviewed",),
        )
        for i, (text, y) in enumerate(contents)
    ]
    sections, audit, _ = normalize_blocks(blocks)
    assert len(sections) == 1 and sections[0].text == contents[1][0]
    assert audit[0]["before"] == contents[0][0]
    assert audit[0]["block_id"] == "C06:b0"


def test_canonical_code_is_idempotent(corpus):
    initial = parse_markdown(corpus[1], corpus[3])
    sections, _, _ = normalize_blocks(initial)
    for section in sections:
        if section.block_type == "code":
            again, _, _ = normalize_blocks(parse_markdown(section.text.encode(), corpus[3]))
            assert again[0].text == section.text


def test_review_receipts_persist_and_change_run_identity(corpus):
    root, data, _, source = corpus
    sections, _, _ = normalize_blocks(parse_markdown(data, source))
    (root / "workspace").mkdir()
    reviews = [receipt(next(s for s in sections if s.block_type == "code"))]
    path = root / "workspace/reviews.json"
    path.write_text(json.dumps([r.model_dump() for r in reviews]))
    first = ingest(root, use_basis="test")
    reviewed = ingest(root, use_basis="test", reviews_path="workspace/reviews.json")
    assert first["run_id"] != reviewed["run_id"]
    assert reviewed["approved_sections"] == 1
    assert ingest(root, use_basis="test", reviews_path="workspace/reviews.json") == reviewed


def test_reject_bad_source_and_normalized_hash(corpus):
    block = parse_markdown(corpus[1], corpus[3])[0]
    with pytest.raises(ValidationError, match="content hash"):
        ParsedBlock.model_validate(block.model_dump() | {"content": "tampered"})
    sections, _, _ = normalize_blocks([block])
    with pytest.raises(ValidationError, match="normalized text hash"):
        Section.model_validate(sections[0].model_dump() | {"text": "tampered"})


def test_unparsed_markdown_lines_are_preserved_and_held(corpus):
    data = b"# Example\n\n[ref]: https://example.org/target\n\n---\n"
    blocks = parse_markdown(data, corpus[3])
    assert any("https://example.org/target" in b.content for b in blocks)
    assert any("markdown_unparsed_line_requires_review" in b.issues for b in blocks)
    assert [b.locator.line_start for b in blocks] == sorted(b.locator.line_start for b in blocks)
    assert len({b.block_id for b in blocks}) == len(blocks)
