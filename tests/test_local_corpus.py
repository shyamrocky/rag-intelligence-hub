"""Optional private integration check; repository ships no copyrighted test fixtures."""

import json
from pathlib import Path

import pytest

from rag_hub.acquire import acquire_sources, load_registry, verify_source
from rag_hub.normalize import normalize_blocks
from rag_hub.parse_markdown import parse_markdown
from rag_hub.parse_pdf import parse_pdf

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    not all(
        (ROOT / "data/raw" / name).exists()
        for name in (
            "C01—Original-RAG-paper.pdf",
            "C04—LangChain-documentation.md",
            "C06—Chroma-research.pdf",
        )
    ),
    reason="private original inputs not provided",
)
def test_original_snapshots_and_required_holds():
    registry = load_registry(ROOT)
    historical = (
        ROOT / "workspace/Project-KickOff-Docs/RAG_Normalization_Input_Manifest_Experiment04.json"
    )
    if historical.exists():
        manifest = json.loads(historical.read_text())
        assert [(s.doc_id, s.sha256, s.byte_size) for s in registry.sources] == [
            (s["doc_id"], s["sha256"], s["bytes"]) for s in manifest["snapshot_inputs"]
        ]
    sources = acquire_sources(
        ROOT, registry, "user-authorized private local experiment verification"
    )
    for source, spec in zip(sources, registry.sources, strict=True):
        data = verify_source(ROOT, spec)
        if source.doc_id == "C04":
            blocks = parse_markdown(data, source)
            assert sum(b.block_type == "code" for b in blocks) == 75
            assert len({b.provider_tab for b in blocks if b.provider_tab}) == 25
            assert all(
                not b.content.startswith("# Below") for b in blocks if b.block_type == "heading"
            )
            code = [b for b in blocks if b.block_type == "code"]
            assert any(
                "chunk_size=1000" in b.content and "chunk_overlap=200" in b.content for b in code
            )
            assert any(
                'metadata={"source"' in b.content or 'metadata={"' in b.content for b in code
            )
        else:
            blocks = parse_pdf(data, source, spec.expected_pages)
            assert max(b.locator.page for b in blocks) == spec.expected_pages
        sections, audit, sidecars = normalize_blocks(blocks)
        assert all(s.index_status == "hold" for s in sections)
        if source.doc_id == "C01":
            assert any(s.kind == "equation" and s.source_locator.page == 3 for s in sidecars)
        if source.doc_id == "C06":
            assert any(s.kind == "equation" and s.source_locator.page == 14 for s in sidecars)
            assert any(s.kind == "table" and s.source_locator.page == 26 for s in sidecars)
            assert any(s.context_block_ids for s in sidecars if s.kind == "table")
            assert sum(a["action"] == "remove_verified_print_margin_artifact" for a in audit) == 164
