"""Opt-in M0 successor: source-only, parent-bound search representations.

Does not alter ChunkInput 1.0, native projections, QA, or consumer permissions.
Source segments are never standalone evidence. No raw provenance fallback.
"""
import copy
import json

from rag_hub.chunk_inputs import SourceContent
from rag_hub.chunk_preparation import ChunkPreparation
from rag_hub.structure_chunking import heading_projection
from rag_hub.unified_bindings import BoundFiles
from rag_hub.unified_models import encode, sha

VERSION = "qualified-search-preparation-1.0"
SEARCH_ROLES = {"provider_neutral_API_explanation", "publisher_score_retrieval_example",
                "verbatim_defective_publisher_code"}
CONTEXT_ROLES = {"required_source_context", "attributed_score_output_only"}


class QualifiedPreparation:
    """Derive search inputs only from a freshly validated admitted parent."""
    def __init__(self, root, corpus):
        self.root, self.corpus = root, corpus
        self.original = ChunkPreparation(corpus)
        self.bound = BoundFiles(root)
        self._html = None

    def headings(self, record):
        values = heading_projection(record)
        if record.format != "html":
            return values
        nested = [c for c in record.required_context if "source_content" in c]
        if not nested:
            return values
        if self._html is None:
            bindings = self.corpus.binding_manifest()["files"]
            rows = {}
            # Use only normalized metadata files already bound by the accepted
            # live gateway, not an unbound acquisition manifest as authority.
            paths = [p for p in bindings if p.startswith("data/normalized/html/")
                     and p.count("/") == 3 and p.endswith(".json")]
            if not paths:
                raise ValueError("missing_bound_heading_type_metadata")
            for path in paths:
                raw = json.loads(self.bound.bind(path, bindings[path]))
                rows.update((r["section"]["section_id"], r["section"]) for r in raw["records"])
            self._html = rows
        member_ids = {m["section_id"] for m in record.memberships}
        for c in nested:
            sid, item = c.get("section_id"), c["source_content"]
            row = self._html.get(sid)
            if (sid not in member_ids or not row or row["doc_id"] != record.document_id
                    or item.get("kind") != "SOURCE_CONTENT" or row["text"] != item.get("text")):
                raise ValueError("nested_heading_identity_or_text_disagreement")
            if row["block_type"] == "heading":
                values.append({"section_id": sid, "text": item["text"],
                               "citations": copy.deepcopy(item["citations"]),
                               "native_type": "heading", "kind": "SOURCE_CONTENT"})
        self.bound.check()
        return values

    def prepare(self, uid):
        record = self.original.prepare(uid)
        if not record.qualification.get("mandatory") or not record.qualification.get("complete_unit_only"):
            raise ValueError("missing_complete_parent_qualification")
        fields = list(record.indexable_source_content)
        parent_only = []
        for protected in record.protected_consumable_projections:
            p = protected["native_source"]["restricted_projection"]
            if (record.format != "markdown" or p["schema"] != "restricted-illustrative-projection-1.0"
                    or not p["warnings"] or not p["not_executable_guidance"]
                    or not p["raw_Sections_are_provenance_only"]
                    or p["warnings"] != record.qualification["documentation_scope"]["limitations"]):
                raise ValueError("unsupported_or_unqualified_protected_projection")
            for i, segment in enumerate(p["segments"]):
                pointer = protected["source_pointer"] + f"/restricted_projection/segments/{i}/text"
                text, sid, role = segment["text"], segment["section_id"], segment["role"]
                roles = {m["role"] for m in record.memberships if m["section_id"] == sid}
                a, b = segment["chars_0based_end_exclusive"]
                if (not text or sha(text.encode()) != segment["text_sha256"]
                        or b - a != len(text) or segment["source_sha256"] != p["source_sha256"]
                        or not roles or role not in SEARCH_ROLES | CONTEXT_ROLES):
                    raise ValueError("invalid_protected_source_segment")
                if role in CONTEXT_ROLES or roles <= {"required_context", "supporting_heading"}:
                    parent_only.append({"pointer": pointer, "section_id": sid, "role": role,
                                        "text_sha256": segment["text_sha256"], "characters": len(text)})
                    continue
                # Segments are explicit native authorized quotations, not raw Sections,
                # warning text, unsupported omitted claims or reconstructed code.
                fields.append(SourceContent(source_pointer=pointer,
                    content_type="code" if "code" in role or "example" in role else "prose",
                    text=text, section_ids=[sid], source_spans=[copy.deepcopy(segment)],
                    native_source={"kind": "SOURCE_CONTENT", "text": text,
                        "segment": copy.deepcopy(segment), "restricted_projection_sha256": p["projection_sha256"],
                        "search_only": True, "complete_parent_required": True}))
        headings = self.headings(record)
        result = {"schema": VERSION, "authority": "SEARCH_DERIVATIVE_NOT_EVIDENCE",
                  "record": record.model_dump(mode="json"),
                  "search_sources": [s.model_dump(mode="json") for s in fields],
                  "parent_only_projection_segments": parent_only,
                  "headings": headings, "complete_parent_required": True}
        self.original.validate(record)
        return result

    def validate(self, candidate):
        if encode(candidate) != encode(self.prepare(candidate["record"]["unit_id"])):
            raise ValueError("altered_qualified_search_preparation")
        return True
