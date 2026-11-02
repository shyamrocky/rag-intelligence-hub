"""Persistent-view integrity, correction inverses and numeric false-positive controls."""

import copy
import json
from pathlib import Path

import pytest
from test_pdf_nontext import fixture

from rag_hub.acquire import digest
from rag_hub.pdf_corpus import (
    approved_parents,
    citation_lookup,
    cleanup,
    encoded,
    is_folio,
    load_corpus,
    restore,
)
from rag_hub.shared.structure import parent, span


def sample(text="1", joined=True):
    _, source, originals = fixture()
    first = originals[0].model_copy(
        update={
            "content": text,
            "content_sha256": digest(text.encode()),
            "locator": originals[0].locator.model_copy(
                update={"page": 1, "bbox": (290, 760, 300, 770)}
            ),
        }
    )
    second = first.model_copy(
        update={
            "block_id": "OWNED:b00001",
            "sequence": 1,
            "content": "continued all-MiniLM-L6-v2: -17.25; Precision_Ω.",
            "content_sha256": digest("continued all-MiniLM-L6-v2: -17.25; Precision_Ω.".encode()),
            "locator": first.locator.model_copy(update={"page": 2, "bbox": (70, 70, 300, 90)}),
        }
    )
    blocks = [first, second] if joined else [first]
    parents = [
        parent(
            "original",
            "paragraph",
            [span(b) for b in blocks],
            source,
            {b.block_id: b for b in blocks},
        )
    ]
    spec = {
        "block_id": first.block_id,
        "raw_sha256": source.raw_sha256,
        "snapshot_id": source.snapshot_id,
        "block_sha256": first.content_sha256,
        "locator": first.locator.model_dump(mode="json"),
        "page_size": [595, 842],
        "operation": "separate_folio",
        "evidence_case": "machine-source-case",
        "review_status": "machine_source_reviewed_not_owner_approved",
    }
    return source, blocks, parents, spec


def test_false_join_detached_without_losing_chars_and_exact_inverse():
    source, blocks, original, spec = sample()
    before = copy.deepcopy(original)
    parents, inventory, structure = cleanup(source, blocks, original, [], [spec])
    assert original == before
    assert [p["kind"] for p in parents] == ["page_furniture_observation", "paragraph_fragment"]
    assert [p["text"] for p in parents] == [b.content for b in blocks]
    assert parents[1]["context_dependencies"] == ["needs_parent_context"]
    assert all(p["experimental_eligibility"] == "HOLD" for p in parents)
    assert structure["represented_blocks"] == 2
    assert restore(parents, inventory) == before
    assert cleanup(source, blocks, original, [], [spec]) == (parents, inventory, structure)


@pytest.mark.parametrize(
    "text", ["-1", "+1", "1.0", "1/82", "1e3", "all-MiniLM-L6-v2", "Ω", "１", "[1]"]
)
def test_numeric_signs_identifiers_and_unicode_digits_not_folios(text):
    source, blocks, parents, spec = sample(text)
    assert not is_folio(blocks[0], spec["page_size"])
    with pytest.raises(ValueError, match="substantive_number_is_not_folio"):
        cleanup(source, blocks, parents, [], [spec])


@pytest.mark.parametrize(
    "change",
    ["number", "margin", "centre", "source", "snapshot", "hash", "locator", "review", "duplicate"],
)
def test_stale_and_substantive_controls_fail_closed(change):
    source, blocks, parents, spec = sample()
    if change in ("number", "margin", "centre"):
        first = blocks[0]
        if change == "number":
            first = first.model_copy(update={"content": "2", "content_sha256": digest(b"2")})
        else:
            box = (290, 100, 300, 110) if change == "margin" else (30, 760, 40, 770)
            first = first.model_copy(
                update={"locator": first.locator.model_copy(update={"bbox": box})}
            )
        blocks[0] = first
        parents = [
            parent(
                "original",
                "paragraph",
                [span(b) for b in blocks],
                source,
                {b.block_id: b for b in blocks},
            )
        ]
        spec.update(
            block_sha256=first.content_sha256, locator=first.locator.model_dump(mode="json")
        )
    elif change in ("source", "snapshot", "hash"):
        key = {"source": "raw_sha256", "snapshot": "snapshot_id", "hash": "block_sha256"}[change]
        spec[key] = "0" * 64
    elif change == "locator":
        spec["locator"]["page"] = 9
    elif change == "review":
        spec["review_status"] = "pending"
    with pytest.raises(ValueError):
        cleanup(source, blocks, parents, [], [spec, spec] if change == "duplicate" else [spec])


def test_inverse_detects_changed_identifier():
    source, blocks, parents, spec = sample()
    after, inventory, _ = cleanup(source, blocks, parents, [], [spec])
    after[1]["text"] = after[1]["text"].replace("-17.25", "17.25")
    with pytest.raises(ValueError, match="inverse_binding"):
        restore(after, inventory)


def test_caption_type_only_no_figure_approval():
    source, blocks, parents, spec = sample("Figure 3: Exact value -17.25.", joined=False)
    spec["operation"] = "classify_figure_caption"
    after, inventory, _ = cleanup(source, blocks, parents, [], [spec])
    assert after[0]["text"] == blocks[0].content
    assert after[0]["kind"] == "figure_caption_observation"
    assert after[0]["caption_attachment"] == {
        "type": "caption_of",
        "target": None,
        "status": "HOLD",
    }
    assert restore(after, inventory) == parents


@pytest.mark.parametrize(
    "text", ["Figure 3 shows results.", "TABLE 3: Results.", "A Figure 3: note."]
)
def test_mentions_do_not_become_figure_captions(text):
    source, blocks, parents, spec = sample(text, joined=False)
    spec["operation"] = "classify_figure_caption"
    with pytest.raises(ValueError, match="not_explicit"):
        cleanup(source, blocks, parents, [], [spec])


def test_private_durable_corpus_load_does_not_reparse(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    if not (root / "data/normalized/pdf/four-pdf-poc-v1/manifest.json").exists():
        pytest.skip("private persisted corpus unavailable")
    import rag_hub.parse_pdf

    def forbidden(*args, **kwargs):
        raise AssertionError("loader must not reparse")

    monkeypatch.setattr(rag_hub.parse_pdf, "parse_pdf", forbidden)
    original_read = Path.read_bytes

    def data_only(path):
        if "workspace" in path.parts:
            raise AssertionError("persisted loading must not depend on workspace files")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", data_only)
    corpus = load_corpus(root)
    assert len(corpus["documents"]) == 4
    assert approved_parents(corpus) == []
    first = corpus["documents"]["C01"]["parents"][0]
    citation = citation_lookup(corpus, "C01", first["id"])
    assert citation["members"] == first["members"]
    assert citation["retrieval_eligible"] is False
    first["experimental_eligibility"] = "APPROVED"
    with pytest.raises(ValueError, match="unsupported_parent_admission"):
        approved_parents(corpus)


def test_manifest_unbound_role_rejected(tmp_path):
    manifest = {
        "schema": "persistent-pdf-corpus-1.0",
        "artifacts": {},
        "documents": {d: {"source": "unbound.json"} for d in ("C01", "C02", "C06", "C14")},
    }
    path = tmp_path / "manifest.json"
    path.write_bytes(encoded(manifest))
    with pytest.raises(ValueError, match="unbound"):
        load_corpus(tmp_path, "manifest.json")


def test_persisted_payload_tampering_rejected(tmp_path):
    (tmp_path / "source.json").write_text("corrupt")
    manifest = {
        "schema": "persistent-pdf-corpus-1.0",
        "artifacts": {"source.json": digest(b"expected")},
        "documents": {d: {"source": "source.json"} for d in ("C01", "C02", "C06", "C14")},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="hash_mismatch"):
        load_corpus(tmp_path, "manifest.json")
