import importlib
import json
import subprocess
import sys

import pytest
from pydantic import ValidationError

from rag_hub.config import Settings
from rag_hub.schemas import Chunk, Section, SourceManifest


def test_smoke_subprocess():
    result = subprocess.run(
        [sys.executable, "-m", "rag_hub.cli", "smoke"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout)["pipeline_implemented"] is False


@pytest.mark.parametrize(
    "module",
    [
        "ingestion",
        "normalization",
        "chunking",
        "embedding",
        "retrieval",
        "generation",
        "evaluation",
        "ui",
    ],
)
def test_interface_imports(module):
    importlib.import_module(f"rag_hub.{module}")


@pytest.mark.parametrize(
    "values", [{"max_chars": 120, "overlap_chars": 120}, {"top_k": 0}, {"unknown_setting": True}]
)
def test_settings_reject_invalid_configuration(values):
    with pytest.raises(ValidationError):
        Settings(**values)


def test_evidence_defaults_to_hold():
    section = Section(
        section_id="synthetic:s1",
        doc_id="synthetic",
        snapshot_id="test",
        heading_path=("Example",),
        block_ids=("b1",),
        text="Synthetic text",
        locators=({"url": "https://example.org", "page": 1},),
    )
    assert section.index_status == "hold"
    assert section.verification_status == "unreviewed"
    chunk = Chunk(
        chunk_id="test",
        doc_id="synthetic",
        snapshot_id="test",
        strategy="fixed",
        strategy_version="test",
        text="Synthetic text",
        source_spans=({"section_id": "synthetic:s1", "start_char": 0, "end_char": 14},),
    )
    assert chunk.index_status == "hold"


def test_manifest_requires_integrity_and_timezone():
    source = {
        "doc_id": "synthetic",
        "snapshot_id": "test",
        "canonical_url": "https://example.org",
        "title": "Synthetic",
        "publisher": "Test",
        "source_format": "html",
        "captured_at": "2026-10-18T00:00:00Z",
        "raw_path": "data/raw/synthetic.html",
        "raw_sha256": "a" * 64,
        "rights_status": "review_pending",
    }
    assert SourceManifest(**source).rights_status == "review_pending"
    for field, value in [("raw_sha256", "short"), ("captured_at", "2026-10-18T00:00:00")]:
        with pytest.raises(ValidationError):
            SourceManifest(**(source | {field: value}))
