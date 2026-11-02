"""Read-only M3 catalog. Resolve content only through the live accepted gateway.

No tokenizer, chunker, QA execution or raw normalized fallback is used by readers.
"""

import copy
import json
from pathlib import Path

from rag_hub.chunk_preparation import ChunkPreparation
from rag_hub.retrieval_chunks import RetrievalChunk, chunk_id
from rag_hub.structure_chunking import display_segments, heading_projection, mapped_lineage
from rag_hub.unified_bindings import BoundFiles
from rag_hub.unified_models import encode, sha

DEFAULT_SELECTOR = "config/retrieval-chunks-v2.json"


class ChunkCatalog:
    def __init__(self, root, corpus, *, selector=DEFAULT_SELECTOR):
        self.root = Path(root).resolve()
        self.corpus = corpus
        self.preparation = ChunkPreparation(corpus)
        self.bound = BoundFiles(self.root)
        path = self.root / selector
        selection = json.loads(self.bound.bind(selector, sha(path.read_bytes())))
        self.manifest = json.loads(self.bound.bind(
            selection["manifest_path"], selection["manifest_sha256"]))
        if self.manifest["schema"] != "retrieval-chunk-catalog-1.0":
            raise ValueError("unsupported_chunk_catalog_schema")
        for name, digest in self.manifest["components"].items():
            self.bound.bind(name, digest)
        upstream = corpus.binding_manifest()["files"]
        if self.manifest["upstream_files"] != upstream:
            raise ValueError("chunk_catalog_upstream_binding_changed")
        for name, digest in self.manifest["files"].items():
            self.bound.bind(name, digest)
        self._chunks, self._units, self._sections = {}, {}, {}
        metadata = {u["unit_id"]: u for u in corpus.catalog.list_units()}
        raw = self.bound.path(self.manifest["chunks_path"]).read_text()
        for line in raw.splitlines():
            row = RetrievalChunk.model_validate_json(line).model_dump(mode="json")
            cid, uid = row["chunk_id"], row["unit_id"]
            if cid != chunk_id(row) or cid in self._chunks or uid not in metadata:
                raise ValueError("invalid_duplicate_or_orphan_chunk")
            parent = metadata[uid]
            expected = {"native_handle": parent["native_handle"],
                        "publication_sha256": sha(encode(parent["publication_identity"])),
                        "memberships_sha256": sha(encode(parent["memberships"]))}
            config = self.manifest["configurations"].get(row["configuration_id"])
            if (row["parent_binding"] != expected or config is None
                    or row["document_id"] != parent["document_id"]
                    or row["format"] != parent["format"]
                    or row["reference_classification"] != parent["reference_classification"]
                    or row["token_count"] > config["total_tokens"]
                    or row["source"]["end"] <= row["source"]["start"]):
                raise ValueError("invalid_chunk_parent_or_configuration")
            self._chunks[cid] = row
            self._units.setdefault(uid, []).append(cid)
        self._outcomes = self.bound.json(self.manifest["units_path"])
        expected_units = {uid for uid, m in metadata.items()
                          if m["document_id"] in self.manifest["documents"]}
        if {r["unit_id"] for r in self._outcomes} != expected_units or len(
                self._outcomes) != len(expected_units):
            raise ValueError("incomplete_or_duplicated_unit_accounting")
        # Checked public pages replace thousands of repeated lease checks during
        # construction. This is metadata only; evidence still resolves live.
        sections, offset = {}, 0
        while True:
            page = corpus.catalog.list_sections(offset=offset, limit=1000)
            sections.update((s["section_id"], s) for s in page["items"])
            if page["next_offset"] is None:
                break
            offset = page["next_offset"]
        for outcome in self._outcomes:
            uid = outcome["unit_id"]
            if outcome["chunk_ids"] != self._units.get(uid, []):
                raise ValueError("chunk_unit_index_disagreement")
            for edge in corpus.catalog.get_unit_sections(uid):
                sid = edge["section_id"]
                if (sid not in sections or sections[sid]["admission_status"] != "ADMITTED"
                        or sections[sid]["document_id"] != metadata[uid]["document_id"]):
                    raise ValueError("unauthorized_chunk_membership")
                self._sections.setdefault(sid, []).append({
                    **edge, "unit_id": uid, "chunk_ids": self._units.get(uid, []),
                    "context_only_in_unit": edge["role"] in {"required_context", "supporting_heading"},
                    "relationship_scope": "published_parent_membership_not_inferred_chunk_span"})
        self.check()

    def check(self):
        self.bound.check()
        self.corpus.catalog.get_corpus_summary()

    def list_chunks(self, document_id=None, *, unit_id=None, section_id=None, offset=0, limit=100):
        self.check()
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("invalid_chunk_pagination")
        ids = None
        if section_id:
            # Validate metadata identity even if HOLD/excluded has no chunk links.
            self.corpus.catalog.get_section(section_id)
            ids = {c for r in self._sections.get(section_id, []) for c in r["chunk_ids"]}
        rows = [r for r in self._chunks.values()
                if (not document_id or r["document_id"] == document_id)
                and (not unit_id or r["unit_id"] == unit_id)
                and (ids is None or r["chunk_id"] in ids)]
        return {"total": len(rows), "items": copy.deepcopy(rows[offset:offset + limit])}

    def get_chunk(self, cid):
        self.check()
        if cid not in self._chunks:
            raise ValueError("unknown_chunk_id")
        return copy.deepcopy(self._chunks[cid])

    def get_unit_chunks(self, uid):
        self.check()
        self.corpus.catalog.get_unit_sections(uid)
        return copy.deepcopy(self._units.get(uid, []))

    def get_section_chunks(self, sid):
        self.check()
        self.corpus.catalog.get_section(sid)
        return copy.deepcopy(self._sections.get(sid, []))

    def get_chunk_sections(self, cid):
        row = self.get_chunk(cid)
        return [{**edge,
                 "context_only_in_unit": edge["role"] in {"required_context", "supporting_heading"},
                 "span_relation": "exact_intersection" if (
                     row["lineage"]["precision"] == "HASH_VERIFIED_DISPLAY_TO_ORIGINAL_SOURCE_SLICES"
                     and edge["section_id"] in row["lineage"]["section_ids"])
                 else "parent_membership_only; exact partial allocation not claimed"}
                for edge in self.corpus.catalog.get_unit_sections(row["unit_id"])]

    def outcomes(self):
        self.check()
        return copy.deepcopy(self._outcomes)

    def open_chunk(self, cid):
        """Inspection projection plus unchanged complete verified parent, never bare evidence."""
        row = self.get_chunk(cid)
        record = self.preparation.prepare(row["unit_id"])
        source = next((s for s in record.indexable_source_content
                       if s.source_pointer == row["source"]["pointer"]), None)
        if source is None:
            raise ValueError("non_indexable_or_missing_chunk_source")
        s = row["source"]
        a, b = s["start"], s["end"]
        text = source.text[a:b]
        lineage = mapped_lineage(record, source, display_segments(source), a, b)
        headings = heading_projection(record)
        if (b > len(source.text) or sha(source.text.encode()) != s["projection_sha256"]
                or sha(text.encode()) != s["text_sha256"]
                or s["content_type"] != source.content_type
                or encode(lineage) != encode(row["lineage"])
                or sha(encode(headings)) != row["heading_context_sha256"]):
            raise ValueError("chunk_source_or_lineage_binding_changed")
        parent = self.corpus.evidence.get_verified_unit(row["unit_id"])
        self.corpus.evidence.validate(parent)
        self.check()
        return {"authority": "INSPECTION_SLICE_REQUIRES_COMPLETE_VERIFIED_PARENT",
                "chunk": row, "source_slice": text, "heading_context": headings,
                "verified_parent": json.loads(self.corpus.evidence.serialize(parent))}

    def validate_view(self, view):
        expected = self.open_chunk(view["chunk"]["chunk_id"])
        if encode(view) != encode(expected):
            raise ValueError("altered_stale_or_warning_stripped_chunk_view")
        return True
