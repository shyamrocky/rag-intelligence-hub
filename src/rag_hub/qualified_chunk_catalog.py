"""Explicit opt-in M3 reader. Search representations require a full live parent.

Original catalogs continue using their unchanged reader/preparation contracts.
"""
import json

from rag_hub.chunk_catalog import ChunkCatalog
from rag_hub.chunk_inputs import ChunkInput, SourceContent
from rag_hub.qualified_chunking import source_lineage
from rag_hub.qualified_preparation import QualifiedPreparation
from rag_hub.unified_models import encode, sha

QUALIFIED_CONFIG = "m3-qualified-config-1.0"
SELECTOR = "config/retrieval-chunks-m3-qualified-v2.json"


class QualifiedChunkCatalog(ChunkCatalog):
    def __init__(self, root, corpus, *, selector=SELECTOR):
        super().__init__(root, corpus, selector=selector)
        self.qualified_preparation = QualifiedPreparation(self.root, corpus)
        for row in self._chunks.values():
            config = self.manifest["configurations"][row["configuration_id"]]
            if config.get("schema") != QUALIFIED_CONFIG:
                continue
            if (config["total_tokens"] not in {384, 512}
                    or not config["complete_parent_required"]
                    or [row["unit_id"], row["source"]["pointer"]] not in config["authorized_search_fields"]
                    or row["document_id"] not in {"C04", "C06", "C16"}
                    or row["mandatory_evidence_refs"]["scope"] != "complete_verified_unit_only"):
                raise ValueError("unsupported_qualified_chunk_scope")

    def open_chunk(self, cid):
        row = self.get_chunk(cid)
        config = self.manifest["configurations"][row["configuration_id"]]
        if config.get("schema") != QUALIFIED_CONFIG:
            return super().open_chunk(cid)
        prepared = self.qualified_preparation.prepare(row["unit_id"])
        record = ChunkInput.model_validate(prepared["record"])
        source = next((SourceContent.model_validate(s) for s in prepared["search_sources"]
                       if s["source_pointer"] == row["source"]["pointer"]), None)
        if source is None:
            raise ValueError("unauthorized_qualified_search_source")
        s = row["source"]
        a, b = s["start"], s["end"]
        text = source.text[a:b]
        lineage = source_lineage(record, source, a, b)
        headings = prepared["headings"]
        if (not 0 <= a < b <= len(source.text) or sha(source.text.encode()) != s["projection_sha256"]
                or sha(text.encode()) != s["text_sha256"]
                or source.content_type != s["content_type"]
                or encode(lineage) != encode(row["lineage"])
                or sha(encode(headings)) != row["heading_context_sha256"]):
            raise ValueError("qualified_source_or_lineage_binding_changed")
        parent = self.corpus.evidence.get_verified_unit(row["unit_id"])
        self.corpus.evidence.validate(parent)
        prefix = "\n".join(h["text"] for h in headings)
        prefix = prefix + "\n\n" if prefix else ""
        self.check()
        return {"authority": "SEARCH_SLICE_REQUIRES_COMPLETE_VERIFIED_PARENT",
                "chunk": row, "source_slice": text, "heading_context": headings,
                "search_representation": {"text": prefix + text,
                    "role": "SEARCH_ONLY_NOT_INDEPENDENT_EVIDENCE",
                    "complete_parent_required": True, "token_count": row["token_count"],
                    "total_token_limit": config["total_tokens"],
                    "publication_binding": row["parent_binding"],
                    "future_consumer_requirement": "Rehydrate and validate the complete parent; "
                        "present its mandatory warnings, context and qualifications. Never cite the slice alone."},
                "verified_parent": json.loads(self.corpus.evidence.serialize(parent))}
